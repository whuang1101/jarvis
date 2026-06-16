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
  [cyan]/usage[/cyan]         Show token usage and estimated cost for this session
  [cyan]/model [name][/cyan]  Show or switch the current model
  [cyan]/file <path>[/cyan]   Load a file into context
  [cyan]/run <cmd>[/cyan]     Run a shell command and add output to context
  [cyan]/fix[/cyan]           Send clipboard contents as an error to fix
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
_RUN_AGENT_PREFIX = "__RUN__:"


def _get_clipboard() -> str | None:
    for cmd in (["pbpaste"], ["xclip", "-o"], ["wl-paste"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def handle_command(
    raw: str,
    client: JarvisClient,
    context: ContextManager,
    tracker: UsageTracker,
) -> str | None:
    """
    Handle a slash command.
    Returns:
      None             → nothing to do
      _EXIT_SENTINEL   → exit the REPL
      _RUN_AGENT_PREFIX + message → run this message through the agent
    """
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
        cost = tracker.cost_usd
        console.print(
            f"\n[bold cyan]Session usage[/bold cyan]\n"
            f"  Model:              [cyan]{client.current_deployment()}[/cyan]\n"
            f"  Prompt tokens:      [cyan]{tracker.prompt_tokens:>10,}[/cyan]\n"
            f"  Completion tokens:  [cyan]{tracker.completion_tokens:>10,}[/cyan]\n"
            f"  Total tokens:       [bold cyan]{tracker.total_tokens:>10,}[/bold cyan]\n"
            f"  Estimated cost:     [bold cyan]${cost:>10.4f}[/bold cyan]\n"
            f"\n[dim]Context window: {msgs} messages[/dim]"
        )
        return None

    if cmd == "/model":
        if not arg:
            print_command_output(f"Current model: {client.current_deployment()}")
        else:
            client.set_deployment(arg)
            print_system(f"Switched to {arg}")
        return None

    if cmd == "/fix":
        text = arg or _get_clipboard()
        if not text:
            # Fall back to manual paste
            console.print("[dim]Paste the error then press Ctrl+D:[/dim]")
            lines: list[str] = []
            try:
                while True:
                    lines.append(console.input(""))
            except EOFError:
                text = "\n".join(lines).strip()
        if not text:
            print_error("No error text to fix.")
            return None
        # Show what we're sending
        preview = text[:300] + ("..." if len(text) > 300 else "")
        console.print(f"[dim]{preview}[/dim]")
        message = f"I got this error:\n```\n{text}\n```\nPlease diagnose and fix it."
        return f"{_RUN_AGENT_PREFIX}{message}"

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
