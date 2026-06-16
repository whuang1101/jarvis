from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import JarvisClient


class UsageTracker:
    def __init__(self) -> None:
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def record(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion

_SYSTEM_PROMPT = (
    "You are Jarvis, an AI coding assistant running in the user's terminal. "
    "You have access to their filesystem and can run commands. "
    "Be concise and direct. When editing files, prefer edit_file over write_file for targeted changes. "
    "When something fails, explain why and suggest fixes. "
    "Prefer small, focused changes over large rewrites."
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
