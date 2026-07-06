from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import JarvisClient

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _image_data_url(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    mime = "jpeg" if ext == "jpg" else ext
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"


def build_multimodal_content(text: str) -> str | list[dict[str, Any]]:
    """Scan whitespace-separated tokens in `text` for existing image file paths
    and turn them into OpenAI vision content parts alongside the text. Returns
    `text` unchanged if none of its tokens are image paths that exist on disk.
    Trailing sentence punctuation (e.g. ``what's in shot.png?``) is stripped
    before the path is tested so the token still resolves to a real file."""
    image_paths = [
        candidate
        for word in text.split()
        for candidate in (word.rstrip("?.,!:;)"),)
        if Path(candidate).suffix.lower() in _IMAGE_EXTENSIONS and Path(candidate).is_file()
    ]
    if not image_paths:
        return text
    parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for image_path in image_paths:
        parts.append({
            "type": "image_url",
            "image_url": {"url": _image_data_url(Path(image_path))},
        })
    return parts

# Price per 1M tokens in USD (input, output)
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o":       (2.50,  10.00),
    "gpt-4o-mini":  (0.15,   0.60),
    "gpt-4-turbo":  (10.00, 30.00),
    "gpt-4":        (30.00, 60.00),
    "gpt-35-turbo": (0.50,   1.50),
    "o1":           (15.00, 60.00),
    "o1-mini":      (3.00,  12.00),
}


def _lookup_price(deployment: str) -> tuple[float, float]:
    dl = deployment.lower()
    # Longest key first so a specific variant (e.g. "gpt-4o-mini") is matched
    # before its prefix ("gpt-4o"), which would otherwise misprice -mini models.
    for key, price in sorted(_PRICING.items(), key=lambda kv: len(kv[0]), reverse=True):
        if key in dl:
            return price
    return (2.50, 10.00)


class UsageTracker:
    def __init__(self) -> None:
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def record(self, prompt: int, completion: int, deployment: str = "") -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        if deployment:
            inp, out = _lookup_price(deployment)
            self.cost_usd += (prompt * inp + completion * out) / 1_000_000


_SYSTEM_PROMPT = (
    "You are Jarvis, an AI coding assistant running in the user's terminal. You have access to "
    "their filesystem and can run commands.\n\n"
    "Be concise and direct — this is a terminal, not a chat window. Skip preamble and restating "
    "the task; answer or act first. Short answers for simple questions, more detail only when the "
    "task warrants it.\n\n"
    "Search before you read, read before you edit. Use search_files or find_symbol to locate the "
    "relevant code first — never bulk-read a whole repo hoping to find something. Once you know "
    "which file and region matter, read_file that region before editing it; don't guess at "
    "surrounding context. Never fabricate file contents, line numbers, or command output — if you "
    "haven't read it or run it, say so instead of inventing what it probably looks like.\n\n"
    "Prefer edit_file over write_file for targeted changes so only the diff you intend is touched. "
    "Prefer small, focused changes over large rewrites — don't refactor or add abstractions beyond "
    "what was asked. After editing, verify: re-read the changed region or run the relevant tests to "
    "confirm the edit did what you intended, rather than assuming success.\n\n"
    "When something fails, explain why before suggesting fixes. For multi-step work, use the "
    "todo_write tool to keep a visible task list: create it up front with one task in_progress, "
    "and update it (passing the full list) as you complete each step. Skip it for single-step tasks.\n\n"
    "Ask before destructive or hard-to-reverse actions — deleting files, force-pushing, dropping "
    "data, overwriting uncommitted changes — even if a command would technically let you proceed "
    "without confirmation.\n\n"
    "You are on a low token quota: read only the specific files a task needs, and keep your own "
    "responses short. If context is growing large, tell the user to run /compact."
)

_PLAN_MODE_PROMPT = """
## Plan Mode is ACTIVE

Do NOT call write_file, edit_file, or run_command yet. First, research with
read_file / search_files / find_symbol as needed, then output a numbered plan
and STOP.

Format:
**Plan: <title>**
1. <file> — <what changes>
2. <file> — <what changes>

After the plan, end with: "Type `/go` to execute or `/cancel` to abort." Then
wait — do not make any changes until the user runs /go. If they run /cancel,
abandon the plan. (To execute without review, the user turns plan mode off and
uses auto mode instead.)
"""

_COMPACT_PROMPT = (
    "Summarize this conversation in 3-4 sentences focusing on what was discussed and decided."
)


_plan_mode: bool = False


def is_plan_mode() -> bool:
    return _plan_mode


def set_plan_mode(enabled: bool) -> None:
    global _plan_mode
    _plan_mode = enabled


class ContextManager:
    def __init__(self, project_context: str | None = None) -> None:
        self._history: list[dict[str, Any]] = []
        self._project_context = project_context
        self._pinned: list[str] = []

    @property
    def system_message(self) -> dict[str, Any]:
        content = _SYSTEM_PROMPT
        if self._project_context:
            content += f"\n\n## Project Context (JARVIS.md)\n\n{self._project_context}"
        memory_path = Path.home() / '.jarvis/memory.md'
        if memory_path.is_file():
            with open(memory_path, 'r') as f:
                memory_content = f.read()
                content += f"\n\n## Persistent Memory\n\n{memory_content}"
        if self._pinned:
            content += "\n\n## Pinned\n\n" + "\n".join(f"- {p}" for p in self._pinned)
        if _plan_mode:
            content += _PLAN_MODE_PROMPT
        return {"role": "system", "content": content}

    def pin(self, text: str) -> None:
        """Pin a note into the system prompt. Pinned notes survive `clear()` and
        `compact()` — they live outside `_history` — so use them for instructions
        that must not get summarized away or wiped."""
        self._pinned.append(text)

    @property
    def pinned(self) -> list[str]:
        return list(self._pinned)

    def unpin(self, index: int) -> bool:
        """Remove the pinned note at 1-based `index`. Returns False if out of range."""
        if not (1 <= index <= len(self._pinned)):
            return False
        del self._pinned[index - 1]
        return True

    def set_project_context(self, text: str) -> None:
        self._project_context = text

    def messages(self) -> list[dict[str, Any]]:
        return [self.system_message] + self._clean_history()

    def _clean_history(self) -> list[dict[str, Any]]:
        """Drop assistant tool_call messages missing results, and orphaned tool messages.

        The API rejects a request where an assistant tool_calls message lacks a
        matching tool result, OR where a role:tool message references a tool_call_id
        that no surviving assistant message declared. Both can happen when a
        multi-tool turn is interrupted, so we prune both directions.
        """
        # tool_call_ids that actually received a response
        responded = {
            m["tool_call_id"]
            for m in self._history
            if m.get("role") == "tool" and "tool_call_id" in m
        }
        # tool_call_ids declared by assistant messages we will KEEP
        kept_call_ids: set[str] = set()
        for m in self._history:
            if m.get("role") == "assistant" and m.get("tool_calls"):
                ids = {tc["id"] for tc in m["tool_calls"]}
                if ids.issubset(responded):
                    kept_call_ids |= ids

        cleaned = []
        for m in self._history:
            if m.get("role") == "assistant" and m.get("tool_calls"):
                ids = {tc["id"] for tc in m["tool_calls"]}
                if not ids.issubset(responded):
                    continue  # drop orphaned tool_call message
            elif m.get("role") == "tool":
                if m.get("tool_call_id") not in kept_call_ids:
                    continue  # drop orphaned tool result
            cleaned.append(m)
        return cleaned

    def append(self, message: dict[str, Any]) -> None:
        self._history.append(message)

    def token_estimate(self) -> int:
        total_chars = sum(
            len(str(m.get("content") or "")) for m in self._history
        )
        return total_chars // 4

    def message_count(self) -> int:
        return len(self._history)

    def clear(self) -> None:
        self._history = []

    def load_history(self, history: list[dict[str, Any]]) -> None:
        self._history = history

    def compact(self, client: "JarvisClient", tracker: "UsageTracker | None" = None) -> str:
        if not self._history:
            return "Nothing to compact."
        history_text = "\n".join(
            f"{m['role']}: {m.get('content', '')}" for m in self._history
        )
        result = client.complete([
            {"role": "user", "content": f"{_COMPACT_PROMPT}\n\n{history_text}"},
        ])
        if tracker:
            tracker.record(result.prompt_tokens, result.completion_tokens, client.current_deployment())
        self._history = [{"role": "assistant", "content": f"[Summary of previous conversation]\n{result.text}"}]
        return result.text
