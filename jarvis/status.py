from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .settings import Settings


def render_status(
    settings: Settings, cwd: Path, tokens: int, plan: bool, auto: bool, danger: bool
) -> str:
    if not settings.statusline:
        return build_default_status(cwd, tokens, plan, auto, danger)
    payload = json.dumps(
        {"cwd": str(cwd), "tokens": tokens, "plan": plan, "auto": auto, "danger": danger}
    )
    try:
        result = subprocess.run(
            settings.statusline,
            shell=True,
            input=payload,
            capture_output=True,
            text=True,
            timeout=settings.tool_timeout_secs,
        )
    except Exception:
        return build_default_status(cwd, tokens, plan, auto, danger)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.splitlines()[0].strip()
    return build_default_status(cwd, tokens, plan, auto, danger)


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
