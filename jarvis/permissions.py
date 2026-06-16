from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from rich.syntax import Syntax

from .formatter import console

_DESTRUCTIVE_RE = re.compile(
    r"\brm\s|rmdir\b|sudo\s|kill\s|pkill\b|killall\b"
    r"|git\s+(?:reset\s+--hard|clean\s+-[fdx])"
    r"|\bDROP\s+(?:TABLE|DATABASE)\b"
    r"|\bTRUNCATE\b"
    r"|mkfs\b|fdisk\b",
    re.IGNORECASE,
)

# Auto mode: skip approval for file writes/edits; destructive commands always blocked.
_auto_mode: bool = False


def is_auto_mode() -> bool:
    return _auto_mode


def set_auto_mode(enabled: bool) -> None:
    global _auto_mode
    _auto_mode = enabled


def needs_permission(tool_name: str, args: dict[str, Any]) -> bool:
    if tool_name == "run_command":
        # Destructive commands always require approval regardless of auto mode
        return bool(_DESTRUCTIVE_RE.search(args.get("command", "")))
    if tool_name in ("write_file", "edit_file"):
        return not _auto_mode
    return False


def _write_diff(path: str, new_content: str) -> str | None:
    try:
        old_content = Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None  # new file — handled separately

    if old_content == new_content:
        return ""  # no changes

    lines = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    ))
    return "\n".join(lines)


def _edit_diff(path: str, old_string: str, new_string: str) -> str | None:
    """Returns diff string, or None on error (caller should read error from None + separate check)."""
    try:
        original = Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None

    if old_string not in original:
        return None

    new_content = original.replace(old_string, new_string, 1)
    lines = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    ))
    return "\n".join(lines)


def _show_diff(tool_name: str, args: dict[str, Any]) -> str | None:
    """Render the diff/preview. Returns None on success or an error string."""
    if tool_name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        diff = _write_diff(path, content)
        if diff is None:
            n = content.count("\n") + 1
            console.print(f"  [bold]New file:[/bold] {path} ({n} lines)")
        elif diff == "":
            return ""  # sentinel: no changes
        else:
            console.print(f"  [bold]Write {path}[/bold]")
            console.print(Syntax(diff, "diff", theme="ansi_dark", padding=(0, 4)))

    elif tool_name == "edit_file":
        path = args.get("path", "")
        diff = _edit_diff(path, args.get("old_string", ""), args.get("new_string", ""))
        if diff is None:
            return f"Error: could not compute diff for {path}"
        if diff == "":
            return ""  # sentinel: no changes
        console.print(f"  [bold]Edit {path}[/bold]")
        console.print(Syntax(diff, "diff", theme="ansi_dark", padding=(0, 4)))

    return None


def request_permission(tool_name: str, args: dict[str, Any]) -> str | None:
    """
    Show a preview and prompt the user for approval.
    In auto mode, file writes/edits are approved automatically (diff still shown).
    Destructive commands always require explicit approval.
    Returns None if approved, or a refusal string to return as the tool result.
    """
    console.print()

    if tool_name in ("write_file", "edit_file"):
        result = _show_diff(tool_name, args)
        if result == "":
            # No changes — auto-approve silently
            console.print(f"  [dim]No changes to {args.get('path', '')}[/dim]")
            return None
        if result is not None:
            return result  # error string
        if _auto_mode:
            console.print("  [dim green]✓ Auto-applied[/dim green]")
            return None

    elif tool_name == "run_command":
        # Destructive commands always go through the prompt, even in auto mode
        cmd = args.get("command", "")
        console.print(f"  [yellow bold]⚠ Destructive command:[/yellow bold] {cmd}")

    try:
        answer = console.input("  [bold]Apply? [y/N][/bold] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        answer = "n"

    if answer == "y":
        return None  # approved

    console.print("  [dim]✗ Skipped[/dim]")
    return "Operation cancelled — user did not approve. Let the user know what you were trying to do and ask how they'd like to proceed."
