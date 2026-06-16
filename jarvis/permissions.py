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


def needs_permission(tool_name: str, args: dict[str, Any]) -> bool:
    if tool_name in ("write_file", "edit_file"):
        return True
    if tool_name == "run_command":
        return bool(_DESTRUCTIVE_RE.search(args.get("command", "")))
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


def request_permission(tool_name: str, args: dict[str, Any]) -> str | None:
    """
    Show a preview and prompt the user for approval.
    Returns None if approved, or a refusal string to return as the tool result.
    """
    console.print()

    if tool_name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        diff = _write_diff(path, content)
        if diff is None:
            n = content.count("\n") + 1
            console.print(f"  [bold]New file:[/bold] {path} ({n} lines)")
        elif diff == "":
            console.print(f"  [dim]No changes to {path}[/dim]")
            return None  # nothing to approve
        else:
            console.print(f"  [bold]Write {path}[/bold]")
            console.print(Syntax(diff, "diff", theme="ansi_dark", padding=(0, 4)))

    elif tool_name == "edit_file":
        path = args.get("path", "")
        diff = _edit_diff(path, args.get("old_string", ""), args.get("new_string", ""))
        if diff is None:
            return f"Error: could not compute diff for {path}"
        if diff == "":
            console.print(f"  [dim]No changes to {path}[/dim]")
            return None
        console.print(f"  [bold]Edit {path}[/bold]")
        console.print(Syntax(diff, "diff", theme="ansi_dark", padding=(0, 4)))

    elif tool_name == "run_command":
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
