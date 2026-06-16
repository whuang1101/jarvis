from __future__ import annotations

import subprocess
from pathlib import Path

from .client import JarvisClient
from .context import ContextManager, UsageTracker
from .formatter import print_command_output, print_system, print_error, console

_HELP_TEXT = """
[bold cyan]Available commands:[/bold cyan]

  [cyan]/help[/cyan]          Show this help message
  [cyan]/clear[/cyan]         Clear conversation history
  [cyan]/compact[/cyan]       Summarize and compress conversation history
  [cyan]/usage[/cyan]         Show token usage for this session
  [cyan]/file <path>[/cyan]   Load a file into context
  [cyan]/run <cmd>[/cyan]     Run a shell command and add output to context
  [cyan]/init[/cyan]          Create a JARVIS.md project context file here
  [cyan]/exit[/cyan]          Exit Jarvis
  [cyan]/quit[/cyan]          Exit Jarvis
"""

_JARVIS_MD_TEMPLATE = """\
# Project Context

## Stack
<!-- e.g. Python 3.12, FastAPI, PostgreSQL, React -->

## Architecture
<!-- How is the project organised? Key directories and what they contain. -->

## Conventions
<!-- Naming conventions, code style, patterns to follow or avoid. -->

## Key files
<!-- Important files Jarvis should know about upfront. -->

## Common commands
<!-- How to run, test, lint, and deploy. -->
```
npm run dev        # start dev server
pytest             # run tests
```

## Notes
<!-- Anything else Jarvis should keep in mind. -->
"""

_EXIT_SENTINEL = "__EXIT__"


def handle_command(
    raw: str,
    client: JarvisClient,
    context: ContextManager,
    tracker: UsageTracker,
) -> str | None:
    """Handle a slash command. Returns _EXIT_SENTINEL to signal exit, None otherwise."""
    parts = raw.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/exit", "/quit"):
        print_system("Goodbye.")
        return _EXIT_SENTINEL

    if cmd == "/help":
        console.print(_HELP_TEXT)
        return None

    if cmd == "/clear":
        context.clear()
        print_system("History cleared.")
        return None

    if cmd == "/compact":
        print_system("Compacting conversation history...")
        summary = context.compact(client, tracker)
        print_system(f"Compacted. Summary:\n{summary}")
        return None

    if cmd == "/usage":
        msgs = context.message_count()
        console.print(
            f"\n[bold cyan]Session token usage[/bold cyan]\n"
            f"  Prompt tokens:      [cyan]{tracker.prompt_tokens:>10,}[/cyan]\n"
            f"  Completion tokens:  [cyan]{tracker.completion_tokens:>10,}[/cyan]\n"
            f"  Total tokens:       [bold cyan]{tracker.total_tokens:>10,}[/bold cyan]\n"
            f"\n[dim]Context window: {msgs} messages[/dim]"
        )
        return None

    if cmd == "/file":
        if not arg:
            print_error("/file requires a path argument")
            return None
        try:
            with open(arg, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            context.append({"role": "user", "content": f"[File: {arg}]\n```\n{content}\n```"})
            print_system(f"Loaded {arg} into context ({len(content)} chars).")
        except FileNotFoundError:
            print_error(f"File not found: {arg}")
        except OSError as e:
            print_error(f"Could not read {arg}: {e}")
        return None

    if cmd == "/run":
        if not arg:
            print_error("/run requires a command argument")
            return None
        try:
            result = subprocess.run(arg, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout + (f"\n[stderr]\n{result.stderr}" if result.stderr else "")
            context.append({"role": "user", "content": f"[Command: {arg}]\n```\n{output}\n```"})
            print_command_output(output or "(no output)")
        except subprocess.TimeoutExpired:
            print_error("Command timed out after 30s")
        except Exception as e:
            print_error(f"Error running command: {e}")
        return None

    if cmd == "/init":
        target = Path.cwd() / "JARVIS.md"
        if target.exists():
            print_error(f"JARVIS.md already exists at {target}")
            return None
        target.write_text(_JARVIS_MD_TEMPLATE, encoding="utf-8")
        print_system(f"Created {target} — fill it in to give Jarvis project context.")
        return None

    print_error(f"Unknown command: {cmd}  (type /help for available commands)")
    return None
