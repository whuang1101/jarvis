from __future__ import annotations

import difflib
import fnmatch
import re
import sys
import termios
import tty
from pathlib import Path
from typing import Any

from rich.syntax import Syntax

from .formatter import console
from .settings import Settings

_DESTRUCTIVE_RE = re.compile(
    r"\brm\s|rmdir\b|sudo\s|kill\s|pkill\b|killall\b"
    r"|git\s+(?:reset\s+--hard|clean\s+-[fdx])"
    r"|\bDROP\s+(?:TABLE|DATABASE)\b"
    r"|\bTRUNCATE\b"
    r"|mkfs\b|fdisk\b",
    re.IGNORECASE,
)

_settings: Settings = Settings.load()

# Auto mode: skip approval for file writes/edits; destructive commands always blocked.
_auto_mode: bool = _settings.auto_mode


def is_auto_mode() -> bool:
    return _auto_mode


def set_auto_mode(enabled: bool) -> None:
    global _auto_mode
    _auto_mode = enabled


def _invocation_string(tool_name: str, args: dict[str, Any]) -> str:
    """Render a tool call as `tool_name(args)` for matching against allow/deny patterns."""
    if tool_name == "run_command":
        arg_repr = args.get("command", "")
    elif tool_name in ("write_file", "edit_file"):
        arg_repr = args.get("path", "")
    else:
        arg_repr = ", ".join(str(v) for v in args.values())
    return f"{tool_name}({arg_repr})"


def _matches_any(invocation: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(invocation, pattern) for pattern in patterns)


def needs_permission(tool_name: str, args: dict[str, Any], settings: Settings | None = None) -> bool:
    s = settings if settings is not None else _settings
    invocation = _invocation_string(tool_name, args)

    # Deny rules force the permission gate even for tools that wouldn't otherwise
    # trigger it. Allow rules skip the gate even for tools that always would.
    # Deny is checked first so it wins over an overlapping allow pattern.
    if _matches_any(invocation, s.permission_deny):
        return True
    if _matches_any(invocation, s.permission_allow):
        return False

    if tool_name == "run_command":
        return bool(_DESTRUCTIVE_RE.search(args.get("command", "")))
    if tool_name in ("write_file", "edit_file"):
        # Always route file ops through request_permission so the diff is shown.
        # In auto mode request_permission renders the diff then auto-applies;
        # otherwise it prompts for approval.
        return True
    return False


# ANSI codes used only for the interactive selector (bypasses Rich to allow \r overwriting)
_R = "\033[0m"       # reset
_HL = "\033[1;30;47m"  # bold black-on-white (selected)
_DIM = "\033[2m"     # dim (unselected)
_CLR = "\033[2K"     # clear line


def _arrow_confirm() -> bool:
    """
    Interactive Yes / No selector.
    Arrow keys (left/right/up/down) switch selection. Enter confirms. y/n jump directly.
    Returns True if Yes was chosen.
    """
    selected = 1  # 0 = Yes, 1 = No (default No is the safer choice)

    def _render() -> None:
        yes = f"{_HL} Yes {_R}" if selected == 0 else f"{_DIM} Yes {_R}"
        no  = f"{_HL} No  {_R}" if selected == 1 else f"{_DIM} No  {_R}"
        sys.stdout.write(f"\r{_CLR}  {yes}   {no}  ")
        sys.stdout.flush()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        _render()
        while True:
            ch = sys.stdin.buffer.read(1)
            if ch == b"\x1b":
                ch2 = sys.stdin.buffer.read(1)
                ch3 = sys.stdin.buffer.read(1)
                if ch2 == b"[" and ch3 in (b"A", b"B", b"C", b"D"):
                    # any arrow key toggles
                    selected = 1 - selected
                    _render()
            elif ch in (b"\r", b"\n"):
                break
            elif ch in (b"y", b"Y"):
                selected = 0
                break
            elif ch in (b"n", b"N"):
                selected = 1
                break
            elif ch == b"\x03":  # Ctrl+C
                selected = 1
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    label = "Yes" if selected == 0 else "No"
    sys.stdout.write(f"\r{_CLR}  {label}\n")
    sys.stdout.flush()
    return selected == 0


def _write_diff(path: str, new_content: str) -> str | None:
    try:
        old_content = Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None

    if old_content == new_content:
        return ""

    lines = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    ))
    return "\n".join(lines)


class _DiffError(str):
    """A diff-computation error message (distinct from a real diff string)."""


def _edit_diff(path: str, old_string: str, new_string: str) -> str | None:
    try:
        original = Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return _DiffError(f"Error: {path} not found")

    # Mirror EditFileTool's rules so the preview never shows a diff the tool will reject.
    count = original.count(old_string)
    if count == 0:
        return _DiffError(
            f"Error: old_string not found in {path}. Make sure the text matches "
            "exactly, including whitespace and indentation."
        )
    if count > 1:
        return _DiffError(
            f"Error: old_string appears {count} times in {path}. Add more "
            "surrounding context to make it unique."
        )

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
    """Render the diff/preview. Returns '' if no changes, error string on failure, None on success."""
    if tool_name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        diff = _write_diff(path, content)
        if diff is None:
            n = content.count("\n") + 1
            console.print(f"  [bold]New file:[/bold] {path} ({n} lines)")
        elif diff == "":
            return ""
        else:
            console.print(f"  [bold]Write {path}[/bold]")
            console.print(Syntax(diff, "diff", theme="ansi_dark", padding=(0, 4)))

    elif tool_name == "edit_file":
        path = args.get("path", "")
        diff = _edit_diff(path, args.get("old_string", ""), args.get("new_string", ""))
        if isinstance(diff, _DiffError):
            return str(diff)  # forward edit_file's exact rejection message
        if diff == "":
            return ""
        console.print(f"  [bold]Edit {path}[/bold]")
        console.print(Syntax(diff, "diff", theme="ansi_dark", padding=(0, 4)))

    return None


def request_permission(tool_name: str, args: dict[str, Any]) -> str | None:
    """
    Show a preview and prompt with an arrow-key Yes/No selector.
    In auto mode, file writes/edits are approved automatically (diff still shown).
    Destructive commands always require explicit approval.
    Returns None if approved, or a cancellation string if denied.
    """
    console.print()

    if tool_name in ("write_file", "edit_file"):
        result = _show_diff(tool_name, args)
        if result == "":
            console.print(f"  [dim]No changes to {args.get('path', '')}[/dim]")
            return None
        if result is not None:
            return result
        if _auto_mode:
            console.print("  [dim green]✓ Auto-applied[/dim green]")
            return None

    elif tool_name == "run_command":
        cmd = args.get("command", "")
        console.print(f"  [yellow bold]⚠ Destructive command:[/yellow bold] {cmd}")

    approved = _arrow_confirm()

    if approved:
        return None

    console.print("  [dim]✗ Skipped[/dim]")
    return "Operation cancelled — user did not approve. Let the user know what you were trying to do and ask how they'd like to proceed."
