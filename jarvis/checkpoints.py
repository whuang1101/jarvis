from __future__ import annotations

from datetime import datetime
from typing import Any

_CHECKPOINTS: list[dict[str, Any]] = []
_MAX_CHECKPOINTS = 30


def create(history: list[dict], label: str = "", file_stash: str | None = None) -> int:
    _CHECKPOINTS.append(
        {
            "label": label[:80],
            "history": [dict(m) for m in history],
            "file_stash": file_stash,
            "time": datetime.now().astimezone().isoformat(),
        }
    )
    del _CHECKPOINTS[:-_MAX_CHECKPOINTS]
    return len(_CHECKPOINTS)


def list_checkpoints() -> list[dict]:
    return [
        {
            "label": c["label"],
            "time": c["time"],
            "has_files": c["file_stash"] is not None,
        }
        for c in _CHECKPOINTS
    ]


def get(index: int) -> dict | None:
    if index < 1 or index > len(_CHECKPOINTS):
        return None
    checkpoint = _CHECKPOINTS[index - 1]
    result = dict(checkpoint)
    result["history"] = [dict(m) for m in checkpoint["history"]]
    return result


def clear() -> None:
    _CHECKPOINTS.clear()


def summary() -> str:
    if not _CHECKPOINTS:
        return ""
    return f"{len(_CHECKPOINTS)} checkpoints"
