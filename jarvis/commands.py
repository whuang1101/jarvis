from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import fields
from pathlib import Path

from .client import JarvisClient
from .context import ContextManager, UsageTracker, is_plan_mode, set_plan_mode
from .formatter import print_command_output, print_system, print_error, console
from .permissions import (
    is_auto_mode,
    is_dangerously_skip_permissions,
    set_auto_mode,
    set_dangerously_skip_permissions,
)
from .sessions import SessionStore, list_sessions
from .settings import Settings, persist_setting

_HELP_TEXT = """
[bold cyan]Available commands:[/bold cyan]

  [cyan]/help[/cyan]          Show this help message
  [cyan]/history[/cyan]       Show the last 10 exchanges
  [cyan]/retry[/cyan]         Retry the last user message
  [cyan]/undo[/cyan]          Undo the last exchange (user + assistant)
  [cyan]/clear[/cyan]         Clear conversation history
  [cyan]/compact[/cyan]       Summarize and compress conversation history
  [cyan]/usage[/cyan]         Show token usage and estimated cost for this session
  [cyan]/model [name][/cyan]  Show or switch the current model
  [cyan]/file <path>[/cyan]   Load a file into context
  [cyan]/run <cmd>[/cyan]     Run a shell command and add output to context
  [cyan]/plan[/cyan]          Toggle plan mode (Jarvis drafts a plan before making changes)
  [cyan]/go[/cyan]            Approve the current plan and execute it
  [cyan]/cancel[/cyan]        Cancel the current plan
  [cyan]/restart[/cyan]       Reinstall and restart Jarvis in place
  [cyan]/auto[/cyan]          Toggle auto mode (approve file edits without prompting)
  [cyan]/dangerously-skip-permissions[/cyan]
                  Toggle Claude-style permission bypass for all tool calls
  [cyan]/fix[/cyan]           Send clipboard contents as an error to fix
  [cyan]/copy[/cyan]          Copy the last assistant response to the clipboard
  [cyan]/config[/cyan]        Show effective settings and their source
  [cyan]/config <key> <value>[/cyan]
                  Write a setting to the global config
  [cyan]/save <file>[/cyan]   Save conversation history to a markdown file.
  [cyan]/sessions[/cyan]      List the last 10 saved sessions (date, cwd, first message)
  [cyan]/resume <n>[/cyan]    Load a session from /sessions into this conversation
  [cyan]/memory[/cyan]        Manage persistent memory (`~/.jarvis/memory.md`)
  [cyan]/init[/cyan]          Create a JARVIS.md project context file here
  [cyan]/selftest[/cyan]      Run Jarvis's own test suite (pytest)
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


def _copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    for tool, cmd in (
        ("pbcopy", ["pbcopy"]),
        ("xclip", ["xclip", "-selection", "clipboard"]),
        ("wl-copy", ["wl-copy"]),
    ):
        if shutil.which(tool):
            subprocess.run(cmd, input=text, text=True, check=True)
            return True
    return False


def _format_session_date(session_id: str) -> str:
    """session_id is '<YYYYMMDD-HHMMSS>-<suffix>'; render the timestamp part."""
    from datetime import datetime

    timestamp = session_id.rsplit("-", 1)[0]
    try:
        return datetime.strptime(timestamp, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return timestamp


def handle_command(
    raw: str,
    client: JarvisClient,
    context: ContextManager,
    tracker: UsageTracker,
    session: SessionStore | None = None,
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

    if cmd == "/help" or cmd == "/":
        if not arg:
            commands_list = [
                "/help",
                "/history",
                "/retry",
                "/undo",
                "/clear",
                "/compact",
                "/usage",
                "/model",
                "/config",
                "/file",
                "/run",
                "/plan",
                "/go",
                "/cancel",
                "/restart",
                "/auto",
                "/dangerously-skip-permissions",
                "/fix",
                "/copy",
                "/save",
                "/sessions",
                "/resume",
                "/memory",
                "/init",
                "/selftest",
                "/exit",
                "/quit",
            ]

            print("\n[bold cyan]Available commands:[/bold cyan]")
            for cmd in commands_list:
                print(f"  [cyan]{cmd}[/cyan]")
            return None
        console.print(_HELP_TEXT)
        return None

    if cmd == "/history":
        if context._history:
            console.print("\n[bold cyan]Conversation History:[/bold cyan]")
            for i, turn in enumerate(context._history[-10:]):
                role = turn["role"].capitalize()
                content = turn["content"]
                console.print(f"[dim]{i + 1}: {role}[/dim]\n{content}\n")
        else:
            print_error("No history available.")
        return None

    if cmd == "/retry":
        # Find the most recent user message — a backward scan is required because a
        # tool-using turn leaves assistant(tool_calls)/tool/assistant entries after it,
        # so the last user message is not reliably at history[-2].
        last_message = next(
            (m["content"] for m in reversed(context._history)
             if m.get("role") == "user" and m.get("content")),
            None,
        )
        if last_message:
            print_system("Retrying last user message...")
            return f"{_RUN_AGENT_PREFIX}{last_message}"
        print_error("No user message to retry.")
        return None

    if cmd == "/undo":
        # Pop back to and including the most recent user message. A tool-using turn
        # appends assistant/tool/assistant entries, so popping a fixed two would
        # corrupt history (or raise IndexError when only one entry exists).
        if not context._history:
            print_error("No history to undo.")
            return None
        while context._history:
            m = context._history.pop()
            if m.get("role") == "user":
                break
        print_system("Last exchange undone.")
        return None

    if cmd == "/memory":
        memory_path = Path("~/.jarvis/memory.md").expanduser()

        if arg.startswith("show"):
            if memory_path.exists():
                console.print(memory_path.read_text(encoding="utf-8"))
            else:
                print_error("No memory file found.")
            return None

        if arg.startswith("add "):
            text_to_add = arg[4:].strip()
            try:
                memory_path.parent.mkdir(parents=True, exist_ok=True)
                with memory_path.open("a", encoding="utf-8") as f:
                    f.write(text_to_add + "\n")
                print_system("Memory updated.")
            except Exception as e:
                print_error(f"Failed to add to memory: {e}")
            return None

        if arg.startswith("clear"):
            try:
                memory_path.write_text("", encoding="utf-8")
                print_system("Memory cleared.")
            except Exception as e:
                print_error(f"Failed to clear memory: {e}")
            return None

        print_error("Invalid /memory command. Use show, add <text>, or clear.")
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

    if cmd == "/config":
        if not arg:
            settings, sources = Settings.load_with_sources()
            console.print("\n[bold cyan]Effective settings:[/bold cyan]")
            for f in fields(Settings):
                console.print(f"  [cyan]{f.name:<28}[/cyan] {getattr(settings, f.name)!r:<20} [dim]({sources[f.name]})[/dim]")
            return None

        key_value = arg.split(None, 1)
        if len(key_value) != 2:
            print_error("Usage: /config <key> <value>")
            return None
        key, value = key_value
        try:
            persist_setting(key, value)
            print_system(f"Set {key} = {value} in {Path.home() / '.jarvis' / 'config.toml'}")
        except ValueError as e:
            print_error(str(e))
        return None

    if cmd == "/restart":
        print_system("Reinstalling...")
        try:
            subprocess.run(["python3", "-m", "pipx", "reinstall", "jarvis"], check=True)
        except subprocess.CalledProcessError as e:
            print_error(f"Reinstall failed: {e}")
            return None
        jarvis_bin = shutil.which("jarvis")
        if not jarvis_bin:
            print_error("Could not find jarvis binary after reinstall.")
            return None
        print_system("Restarting...")
        os.execv(jarvis_bin, [jarvis_bin])
        return None  # never reached

    if cmd == "/plan":
        new_state = not is_plan_mode()
        set_plan_mode(new_state)
        if new_state:
            print_system("Plan mode ON — Jarvis will draft a plan and wait for /go before making any changes.")
        else:
            print_system("Plan mode OFF — Jarvis will implement directly.")
        return None

    if cmd == "/go":
        return f"{_RUN_AGENT_PREFIX}The plan is approved. Execute each step in order now."

    if cmd == "/cancel":
        return f"{_RUN_AGENT_PREFIX}The plan is cancelled. Do not implement anything. Ask the user what they'd like to do instead."

    if cmd == "/auto":
        new_state = not is_auto_mode()
        set_auto_mode(new_state)
        if new_state:
            print_system("Auto mode ON — file edits apply without prompting. Destructive commands still require approval.")
        else:
            print_system("Auto mode OFF — all changes require approval.")
        return None

    if cmd == "/dangerously-skip-permissions":
        new_state = not is_dangerously_skip_permissions()
        set_dangerously_skip_permissions(new_state)
        if new_state:
            print_system("Dangerously skip permissions ON — all tool permission prompts are bypassed.")
        else:
            print_system("Dangerously skip permissions OFF — normal permission gates restored.")
        return None

    if cmd == "/save":
        if not arg:
            print_error("/save requires a file path argument")
            return None
        try:
            history_text = "\n\n".join(
                f"## {turn['role'].capitalize()}\n{turn['content']}" for turn in context._history
            )
            Path(arg).write_text(f"# Conversation History\n\n{history_text}", encoding="utf-8")
            print_system(f"Conversation saved to {arg}.")
        except Exception as e:
            print_error(f"Failed to save: {e}")
        return None

    if cmd == "/sessions":
        sessions = list_sessions(limit=10)
        if not sessions:
            print_error("No saved sessions found.")
            return None
        console.print("\n[bold cyan]Recent sessions:[/bold cyan]")
        for i, s in enumerate(sessions, start=1):
            date = _format_session_date(s["session_id"])
            preview = (s["first_message"] or "(no messages)")[:60]
            console.print(f"  [cyan]{i:>2}[/cyan]  {date}  [dim]{s['cwd']}[/dim]  {preview}")
        return None

    if cmd == "/resume":
        if not arg:
            print_error("Usage: /resume <n>  (see /sessions for the list)")
            return None
        try:
            n = int(arg)
        except ValueError:
            print_error("Usage: /resume <n>")
            return None
        sessions = list_sessions(limit=10)
        if not (1 <= n <= len(sessions)):
            print_error(f"No session #{n}. Run /sessions to see the list.")
            return None
        loaded_store, history = SessionStore.load(sessions[n - 1]["session_id"])
        context.load_history(history)
        if session is not None:
            session.session_id = loaded_store.session_id
            session.cwd = loaded_store.cwd
            session.first_message = loaded_store.first_message
        print_system(f"Resumed session {loaded_store.session_id} ({len(history)} messages).")
        return None

    if cmd == "/copy":
        if not context._history or context._history[-1]["role"] != "assistant":
            print_error("No assistant response to copy.")
            return None
        response = context._history[-1]["content"]
        try:
            if _copy_to_clipboard(response):
                print_system("Copied last assistant response to clipboard.")
            else:
                print_error("No compatible clipboard utility found on this system.")
        except Exception as e:
            print_error(f"Failed to copy: {e}")
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

    if cmd == "/selftest":
        import sys
        tests_dir = Path(__file__).parent / "tests"
        if not tests_dir.is_dir():
            print_error(f"Test directory not found: {tests_dir}")
            return None
        print_system("Running test suite...")
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", str(tests_dir), "-q"],
                capture_output=True, text=True, timeout=120,
            )
            print_command_output(r.stdout.strip() or r.stderr.strip())
            if r.returncode == 0:
                print_system("✓ All tests passed.")
            else:
                print_error("✗ Tests failed — fix before reinstalling.")
        except FileNotFoundError:
            print_error("pytest is not installed in this environment (pip install pytest).")
        except subprocess.TimeoutExpired:
            print_error("Test run timed out after 120s.")
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
