from __future__ import annotations

import subprocess
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .context import ContextManager

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


def checkpoint_turn(context: "ContextManager", message: str) -> int:
    # Snapshots history before the new user message is appended, so a rewind
    # lands on the pre-turn state rather than replaying the turn that was undone.
    return create(context._history, label=message, file_stash=snapshot_files())


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


def snapshot_files(cwd: str | None = None) -> str | None:
    # git stash create only captures tracked-file modifications; untracked files are ignored.
    try:
        result = subprocess.run(
            ["git", "stash", "create"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except Exception:
        return None
    sha = result.stdout.strip()
    return sha or None


def restore_files(sha: str, cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git", "stash", "apply", sha],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode == 0:
        return "Files restored from checkpoint."
    return f"Error: could not restore files: {result.stderr.strip()}"
