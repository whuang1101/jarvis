from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import JarvisClient

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
    for key, price in _PRICING.items():
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
    "You are Jarvis, an AI coding assistant running in the user's terminal. "
    "You have access to their filesystem and can run commands. "
    "Be concise and direct. When editing files, prefer edit_file over write_file for targeted changes. "
    "When something fails, explain why and suggest fixes. "
    "Prefer small, focused changes over large rewrites. "
    "IMPORTANT: You are on a low token quota. Read only the specific files you need — never bulk-read "
    "an entire repo. Use search_files or find_symbol to locate what you need first, then read only "
    "those files. Keep your responses short. If context is growing large, tell the user to run /compact."
)

_COMPACT_PROMPT = (
    "Summarize this conversation in 3-4 sentences focusing on what was discussed and decided."
)


class ContextManager:
    def __init__(self, project_context: str | None = None) -> None:
        self._history: list[dict[str, Any]] = []
        self._project_context = project_context

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
        return {"role": "system", "content": content}

    def set_project_context(self, text: str) -> None:
        self._project_context = text

    def messages(self) -> list[dict[str, Any]]:
        return [self.system_message] + self._history

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
            tracker.record(result.prompt_tokens, result.completion_tokens)
        self._history = [{"role": "assistant", "content": f"[Summary of previous conversation]\n{result.text}"}]
        return result.text
