from __future__ import annotations

import json
import random
import string
from datetime import datetime
from pathlib import Path
from typing import Any

_SESSIONS_DIR = Path.home() / ".jarvis" / "sessions"


def _new_session_id() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{suffix}"


class SessionStore:
    """Persists the running conversation history to disk on every turn.

    Separate from SessionLogger's JSONL event log: this holds the raw
    ContextManager history so a session can be reloaded and continued.
    """

    def __init__(self, cwd: str, first_message: str | None = None, session_id: str | None = None) -> None:
        self.session_id = session_id or _new_session_id()
        self.cwd = cwd
        self.first_message = first_message

    @property
    def path(self) -> Path:
        return _SESSIONS_DIR / f"{self.session_id}.json"

    def save(self, history: list[dict[str, Any]]) -> None:
        if self.first_message is None:
            for m in history:
                if m.get("role") == "user":
                    self.first_message = m.get("content")
                    break
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "cwd": self.cwd,
            "first_message": self.first_message,
            "history": history,
        }
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, session_id: str) -> tuple["SessionStore", list[dict[str, Any]]]:
        path = _SESSIONS_DIR / f"{session_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        store = cls(cwd=data["cwd"], first_message=data.get("first_message"), session_id=data["session_id"])
        return store, data.get("history", [])
