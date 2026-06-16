from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOG_DIR = Path.home() / ".jarvis" / "logs"


def _log_path() -> Path:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SessionLogger:
    def __init__(self, cwd: str) -> None:
        self.session_id = uuid.uuid4().hex[:8]
        self._path = _log_path()
        self._write({"type": "session_start", "cwd": cwd})

    def _write(self, data: dict[str, Any]) -> None:
        entry = {"ts": _now(), "session": self.session_id, **data}
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def user(self, content: str) -> None:
        self._write({"type": "user", "content": content})

    def assistant(self, content: str) -> None:
        self._write({"type": "assistant", "content": content})

    def tool_call(self, tool: str, args: dict[str, Any]) -> None:
        self._write({"type": "tool_call", "tool": tool, "args": args})

    def tool_result(self, tool: str, result: str) -> None:
        self._write({"type": "tool_result", "tool": tool, "result": result[:500]})

    def error(self, message: str) -> None:
        self._write({"type": "error", "message": message})

    def end(self, prompt_tokens: int, completion_tokens: int) -> None:
        self._write({
            "type": "session_end",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        })

    @property
    def path(self) -> Path:
        return self._path
