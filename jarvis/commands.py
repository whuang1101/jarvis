from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import fields
from pathlib import Path

from . import checkpoints, doctor, todos
from .skills import discover_skills
from .client import JarvisClient
from .context import ContextManager, UsageTracker, is_plan_mode, set_plan_mode
from .formatter import (
    console,
    get_code_theme,
    print_command_output,
    print_error,
    print_system,
    print_todo_list,
    set_code_theme,
)
from .mcp_manager import get_active_manager
from .permissions import (
    is_auto_mode,
    is_dangerously_skip_permissions,
    is_sandbox,
    set_auto_mode,
    set_dangerously_skip_permissions,
    set_sandbox,
)
from .sessions import SessionStore, list_sessions
from .settings import Settings, persist_setting
from .tools import register_tool, unregister_tool

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
  [cyan]/theme [name][/cyan]  Show or switch the Rich syntax highlighting theme
  [cyan]/vim [on|off][/cyan]  Show or toggle Vim editing mode for the input bar
  [cyan]/statusline [cmd][/cyan]
                  Show, set, or `/statusline off` to reset the statusline command
  [cyan]/diff[/cyan]          Show uncommitted changes (git diff HEAD)
  [cyan]/pin [text][/cyan]    Pin a note into the system prompt (survives /compact and /clear); no arg lists pins
  [cyan]/file <path>[/cyan]   Load a file into context (or inline @path in any message to pull it in without the command)
  [cyan]/run <cmd>[/cyan]     Run a shell command and add output to context
  [cyan]/plan[/cyan]          Toggle plan mode (Jarvis drafts a plan before making changes)
  [cyan]/go[/cyan]            Approve the current plan and execute it
  [cyan]/cancel[/cyan]        Cancel the current plan
  [cyan]/restart[/cyan]       Reinstall and restart Jarvis in place
  [cyan]/auto[/cyan]          Toggle auto mode (approve file edits without prompting)
  [cyan]/dangerously-skip-permissions[/cyan]
                  Toggle Claude-style permission bypass for all tool calls
  [cyan]/sandbox [on|off|status][/cyan]
                  Show or toggle sandboxed command execution
  [cyan]/fix[/cyan]           Send clipboard contents as an error to fix
  [cyan]/copy[/cyan]          Copy the last assistant response to the clipboard
  [cyan]/config[/cyan]        Show effective settings and their source
  [cyan]/config <key> <value>[/cyan]
                  Write a setting to the global config
  [cyan]/save <file>[/cyan]   Save conversation history to a markdown file.
  [cyan]/sessions[/cyan]      List the last 10 saved sessions (date, cwd, first message)
  [cyan]/resume <n>[/cyan]    Load a session from /sessions into this conversation
  [cyan]/rewind [n][/cyan]    List checkpoints, restore checkpoint n, or `/rewind clear` to clear them
  [cyan]/mcp[/cyan]           List connected MCP servers, `/mcp add <name> <command> [args...]`, or `/mcp remove <name>`
  [cyan]/memory[/cyan]        Manage persistent memory (`~/.jarvis/memory.md`)
  [cyan]/todos[/cyan]         Show the maintained todo list (`/todos clear` to clear it)
  [cyan]/skills[/cyan]        List discovered skills (name and description)
  [cyan]#text[/cyan]          Shortcut: append `text` to memory without sending it to the agent
  [cyan]/init[/cyan]          Create a JARVIS.md project context file here
  [cyan]/selftest[/cyan]      Run Jarvis's own test suite (pytest) and type-check it (mypy)
  [cyan]/doctor[/cyan]        Run environment self-diagnostics (Azure creds, MCP, tooling)
  [cyan]/commit[/cyan]        Stage changes and have Jarvis write and make the commit
  [cyan]/review [pr#][/cyan]  Review the diff against main, or a PR's diff if given
  [cyan]/pr[/cyan]            Have Jarvis write a title/body and open a PR for this branch
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
_CUSTOM_COMMANDS_GLOBAL_DIR = Path.home() / ".jarvis" / "commands"
_CUSTOM_COMMANDS_PROJECT_DIRNAME = Path(".jarvis") / "commands"

_BUILTIN_COMMANDS = (
    "/help",
    "/history",
    "/retry",
    "/undo",
    "/clear",
    "/compact",
    "/usage",
    "/model",
    "/theme",
    "/vim",
    "/diff",
    "/pin",
    "/config",
    "/file",
    "/run",
    "/plan",
    "/go",
    "/cancel",
    "/restart",
    "/auto",
    "/dangerously-skip-permissions",
    "/sandbox",
    "/fix",
    "/copy",
    "/save",
    "/sessions",
    "/resume",
    "/rewind",
    "/mcp",
    "/memory",
    "/todos",
    "/skills",
    "/init",
    "/selftest",
    "/doctor",
    "/commit",
    "/review",
    "/pr",
    "/exit",
    "/quit",
)


def _custom_command_dirs() -> tuple[Path, Path]:
    return (_CUSTOM_COMMANDS_GLOBAL_DIR, Path.cwd() / _CUSTOM_COMMANDS_PROJECT_DIRNAME)


def _load_custom_command(name: str) -> str | None:
    """Look up a user-defined slash command template: global dir first, then project dir."""
    for base in _custom_command_dirs():
        path = base / f"{name}.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


def _discover_custom_commands() -> list[str]:
    names: set[str] = set()
    for base in _custom_command_dirs():
        if base.is_dir():
            names.update(p.stem for p in base.glob("*.md"))
    return sorted(names)


def all_command_names() -> list[str]:
    """All known slash command names: built-ins plus discovered custom commands."""
    return list(_BUILTIN_COMMANDS) + [f"/{name}" for name in _discover_custom_commands()]


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


def append_memory(text: str) -> str:
    memory_path = Path("~/.jarvis/memory.md").expanduser()
    try:
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        with memory_path.open("a", encoding="utf-8") as f:
            f.write(text.strip() + "\n")
        return "Memory updated."
    except Exception as e:
        return f"Error: failed to add to memory: {e}"


def _pr_context() -> tuple[str | None, str | None]:
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        subjects = subprocess.run(
            ["git", "log", "main..HEAD", "--pretty=format:%s"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        diff = subprocess.run(
            ["git", "diff", "main...HEAD"], capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        return None, "Building the PR context timed out."
    except Exception as e:
        return None, f"Failed to build PR context: {e}"

    if branch == "main":
        return None, "You are on main — check out a feature branch before opening a PR."
    if not diff:
        return None, "No commits on this branch to open a PR for."

    context = (
        f"Branch: {branch}\n"
        f"Commits:\n{subjects}\n"
        f"Diff:\n```diff\n{diff}\n```"
    )
    return context, None


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
            print("\n[bold cyan]Available commands:[/bold cyan]")
            for cmd in all_command_names():
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
            result = append_memory(text_to_add)
            if result.startswith("Error"):
                print_error(result)
            else:
                print_system(result)
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
        pct = round(100 * tracker.cached_tokens / tracker.prompt_tokens) if tracker.prompt_tokens else 0
        console.print(
            f"\n[bold cyan]Session usage[/bold cyan]\n"
            f"  Model:              [cyan]{client.current_deployment()}[/cyan]\n"
            f"  Prompt tokens:      [cyan]{tracker.prompt_tokens:>10,}[/cyan]\n"
            f"  Cached (of prompt): [cyan]{tracker.cached_tokens:>10,}[/cyan]  [dim]({pct}% hit)[/dim]\n"
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

    if cmd == "/theme":
        if not arg:
            print_command_output(f"Current theme: {get_code_theme()}")
            return None
        set_code_theme(arg)
        try:
            persist_setting("theme", arg)
            print_system(f"Theme set to {arg}.")
        except ValueError as e:
            print_error(str(e))
        return None

    if cmd == "/vim":
        sub = arg.strip().lower()
        if sub not in ("", "on", "off"):
            print_error("Usage: /vim [on|off]")
            return None
        current = Settings.load().vi_mode
        new_state = (not current) if sub == "" else (sub == "on")
        persist_setting("vi_mode", "on" if new_state else "off")
        from .cli import _reset_prompt_session

        _reset_prompt_session()
        print_system(f"Vim mode: {'on' if new_state else 'off'}")
        return None

    if cmd == "/statusline":
        if not arg:
            current = Settings.load().statusline
            print_command_output(f"Current statusline: {current or '(default)'}")
            return None
        if arg == "off":
            persist_setting("statusline", "")
            print_system("Statusline reset to default.")
            return None
        try:
            persist_setting("statusline", arg)
            print_system(f"Statusline set to {arg}.")
        except ValueError as e:
            print_error(str(e))
        return None

    if cmd == "/diff":
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD"], capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            print_error("git diff timed out.")
            return None
        except Exception as e:
            print_error(f"Failed to get diff: {e}")
            return None
        if result.returncode != 0:
            print_error(f"git diff failed: {result.stderr.strip()}")
            return None
        diff_output = result.stdout.strip()
        if not diff_output:
            print_system("No uncommitted changes.")
            return None
        print_command_output(diff_output)
        return None

    if cmd == "/pin":
        if context is None:
            print_error("No active context to pin into.")
            return None
        if not arg:
            if context.pinned:
                console.print("\n[bold cyan]Pinned notes:[/bold cyan]")
                for i, p in enumerate(context.pinned, start=1):
                    console.print(f"  [cyan]{i}[/cyan]  {p}")
            else:
                print_error("No pinned notes. Usage: /pin <text>")
            return None
        context.pin(arg)
        print_system("Pinned — this note survives /compact and /clear.")
        return None

    if cmd == "/config":
        if not arg:
            settings, sources = Settings.load_with_sources()
            console.print("\n[bold cyan]Effective settings:[/bold cyan]")
            for fld in fields(Settings):
                console.print(f"  [cyan]{fld.name:<28}[/cyan] {getattr(settings, fld.name)!r:<20} [dim]({sources[fld.name]})[/dim]")
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

    if cmd == "/sandbox":
        sub = arg.strip().lower()
        if sub in ("", "status"):
            print_system(f"Sandbox is {'ON' if is_sandbox() else 'OFF'}.")
        elif sub == "on":
            set_sandbox(True)
            print_system("Sandbox ON — commands run through the sandboxed executor.")
        elif sub == "off":
            set_sandbox(False)
            print_system("Sandbox OFF — commands run without sandboxing.")
        else:
            print_error("Usage: /sandbox [on|off|status]")
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

    if cmd == "/rewind":
        if arg.strip().lower() == "clear":
            checkpoints.clear()
            print_system("Checkpoints cleared.")
            return None
        if arg.strip().isdigit() and int(arg.strip()) > 0:
            n = int(arg.strip())
            cp = checkpoints.get(n)
            if cp is None:
                print_error(f"No checkpoint {n}.")
                return None
            context.load_history(cp["history"])
            if cp["file_stash"]:
                restore_msg = checkpoints.restore_files(cp["file_stash"])
                if restore_msg.startswith("Error"):
                    print_error(restore_msg)
                else:
                    print_system(restore_msg)
            print_system(f"Rewound to checkpoint {n}.")
            return None
        listing = checkpoints.list_checkpoints()
        if not listing:
            print_system("No checkpoints yet.")
            return None
        for i, cp in enumerate(listing, start=1):
            suffix = " [files]" if cp["has_files"] else ""
            print_system(f"{i}: {cp['label']}  ({cp['time']}){suffix}")
        return None

    if cmd == "/mcp":
        tokens = arg.split()
        sub = tokens[0].lower() if tokens else "list"

        if sub == "list" or not tokens:
            mgr = get_active_manager()
            if mgr is None:
                print_error("no MCP manager active (start with --mcp)")
                return None
            servers = mgr.list_servers()
            if not servers:
                print_command_output("No MCP servers connected.")
                return None
            for server in servers:
                print_command_output(f"{server['name']} — {server['tool_count']} tools")
            return None

        if sub == "add":
            if len(tokens) < 3:
                print_error("usage: /mcp add <name> <command> [args...]")
                return None
            mgr = get_active_manager()
            if mgr is None:
                print_error("no MCP manager active (start with --mcp)")
                return None
            name, command, *command_args = tokens[1:]
            try:
                tools = mgr.connect(name=name, command=command, args=command_args, env={})
                for tool in tools:
                    register_tool(tool)
                print_command_output(f"Connected {name} ({len(tools)} tools).")
            except Exception as e:
                print_error(f"Error: could not connect {name}: {e}")
            return None

        if sub == "remove":
            if len(tokens) < 2:
                print_error("usage: /mcp remove <name>")
                return None
            mgr = get_active_manager()
            if mgr is None:
                print_error("no MCP manager active (start with --mcp)")
                return None
            name = tokens[1]
            names = mgr.disconnect(name)
            if names:
                for tool_name in names:
                    unregister_tool(tool_name)
                print_command_output(f"Removed {name} ({len(names)} tools).")
            else:
                print_error(f"Error: no MCP server named {name}.")
            return None

        print_error("usage: /mcp [list | add <name> <command> [args...] | remove <name>]")
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

        print_system("Running mypy...")
        try:
            mypy_result = subprocess.run(
                [sys.executable, "-m", "mypy", str(Path(__file__).parent)],
                capture_output=True, text=True, timeout=120,
            )
            print_command_output(mypy_result.stdout.strip() or mypy_result.stderr.strip())
            if mypy_result.returncode == 0:
                print_system("✓ mypy found no type errors.")
            else:
                print_error("✗ mypy found type errors.")
        except FileNotFoundError:
            print_error("mypy is not installed in this environment (pip install mypy).")
        except subprocess.TimeoutExpired:
            print_error("mypy run timed out after 120s.")
        return None

    if cmd == "/doctor":
        glyphs = {"ok": "✓", "warn": "!", "fail": "✗"}
        for check in doctor.run_diagnostics():
            line = f"{glyphs[check.status]} {check.name}: {check.detail}"
            if check.status == "fail":
                print_error(line)
            elif check.status == "warn":
                print_system(f"! {line}")
            else:
                print_system(line)
        return None

    if cmd == "/init":
        target = Path.cwd() / "JARVIS.md"
        if target.exists():
            print_error(f"JARVIS.md already exists at {target}")
            return None
        target.write_text(_JARVIS_MD_TEMPLATE, encoding="utf-8")
        print_system(f"Created {target} — fill it in to give Jarvis project context.")
        return None

    if cmd == "/commit":
        try:
            add = subprocess.run(["git", "add", "-A"], capture_output=True, text=True, timeout=15)
            if add.returncode != 0:
                print_error(f"git add failed: {add.stderr.strip()}")
                return None
            diff = subprocess.run(
                ["git", "diff", "--staged"], capture_output=True, text=True, timeout=15
            )
            staged_diff = diff.stdout.strip()
        except subprocess.TimeoutExpired:
            print_error("git timed out.")
            return None
        except Exception as e:
            print_error(f"Failed to stage changes: {e}")
            return None
        if not staged_diff:
            print_error("Nothing staged to commit.")
            return None
        message = (
            "Changes have been staged with `git add -A`. Here is `git diff --staged`:\n"
            f"```diff\n{staged_diff}\n```\n"
            "Write a concise commit message (why, not just what) summarizing this diff, "
            "then run `git commit -m \"<message>\"` to make the commit."
        )
        return f"{_RUN_AGENT_PREFIX}{message}"

    if cmd == "/review":
        pr = arg.strip()
        try:
            if pr:
                result = subprocess.run(
                    ["gh", "pr", "diff", pr], capture_output=True, text=True, timeout=30
                )
                source = f"PR #{pr}"
            else:
                result = subprocess.run(
                    ["git", "diff", "main"], capture_output=True, text=True, timeout=30
                )
                source = "the diff against main"
        except subprocess.TimeoutExpired:
            print_error("Fetching the diff timed out.")
            return None
        except Exception as e:
            print_error(f"Failed to fetch diff: {e}")
            return None
        if result.returncode != 0:
            print_error(f"Failed to fetch diff: {result.stderr.strip()}")
            return None
        review_diff = result.stdout.strip()
        if not review_diff:
            print_error(f"No changes found in {source}.")
            return None
        message = (
            f"Review {source}. Here is the diff:\n```diff\n{review_diff}\n```\n"
            "Point out bugs, correctness issues, and risky changes. Be concise."
        )
        return f"{_RUN_AGENT_PREFIX}{message}"

    if cmd == "/pr":
        context, error = _pr_context()
        if error:
            print_error(error)
            return None
        message = (
            f"Open a pull request for this branch. Here is the context:\n{context}\n\n"
            "Write a concise PR title and body (why, not just what), then run "
            '`gh pr create --title "<title>" --body "<body>"`.'
        )
        return f"{_RUN_AGENT_PREFIX}{message}"

    if cmd == "/todos":
        if arg.strip().lower() == "clear":
            todos.clear_todos()
            print_system("Todo list cleared.")
            return None
        print_todo_list(todos.get_todos())
        return None

    if cmd == "/skills":
        skills = discover_skills()
        if not skills:
            print_system("No skills found.")
            return None
        for skill in skills:
            print_system(f"{skill.name} — {skill.description}")
        return None

    custom_template = _load_custom_command(cmd[1:])
    if custom_template is not None:
        return f"{_RUN_AGENT_PREFIX}{custom_template.replace('$ARGUMENTS', arg)}"

    print_error(f"Unknown command: {cmd}  (type /help for available commands)")
    return None
