from __future__ import annotations

from pathlib import Path


def build_default_status(cwd: Path, tokens: int, plan: bool, auto: bool, danger: bool) -> str:
    try:
        short = "~" / cwd.relative_to(Path.home())
    except ValueError:
        short = cwd
    status = f"{short} · {tokens / 1000:.1f}k tokens"
    if plan:
        status += " · PLAN"
    if auto:
        status += " · AUTO"
    if danger:
        status += " · DANGER"
    return status
