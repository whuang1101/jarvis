from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

_RESUME_FILE = Path.home() / ".jarvis" / "resume.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jarvis")
    parser.add_argument(
        "-p", "--print", dest="prompt", metavar="PROMPT",
        help="Run one agent turn non-interactively, print the answer, and exit.",
    )
    parser.add_argument(
        "--mcp", action="store_true",
        help="Connect configured MCP servers in one-shot mode (skipped by default for startup speed).",
    )
    parser.add_argument(
        "--continue", dest="continue_", action="store_true",
        help="Resume the most recent session for the current directory.",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Log at debug level (verbose entries in ~/.jarvis/logs/*.jsonl) instead of info.",
    )
    parser.add_argument(
        "--max-turns", dest="max_turns", type=int, default=None, metavar="N",
        help="Cap the tool-call iterations for a one-shot run; default uses the "
             "configured max_tool_iterations.",
    )
    parser.add_argument(
        "--model", dest="model", default=None, metavar="DEPLOYMENT",
        help="Override the Azure deployment name for this run.",
    )
    parser.add_argument(
        "--output-format", dest="output_format",
        choices=("text", "json", "stream-json"), default="text",
        help="Headless output format for -p mode: text (default human render), "
             "json (one result object), or stream-json (newline-delimited event "
             "objects).",
    )
    return parser.parse_args(argv)


def _find_jarvis_md() -> tuple[str, Path] | None:
    """Walk up from cwd looking for JARVIS.md. Returns (content, path) or None."""
    path = Path.cwd()
    for _ in range(5):
        candidate = path / "JARVIS.md"
        if candidate.exists():
            return candidate.read_text(encoding="utf-8"), candidate
        parent = path.parent
        if parent == path:
            break
        path = parent
    return None

from .agent import run_agent
from . import checkpoints
from .client import JarvisClient
from .commands import handle_command, _EXIT_SENTINEL, _RUN_AGENT_PREFIX
from .permissions import (
    is_auto_mode,
    is_dangerously_skip_permissions,
    set_auto_mode,
    set_dangerously_skip_permissions,
)
from .context import build_multimodal_content, expand_file_mentions, is_plan_mode, set_plan_mode
from .config import Config
from .context import ContextManager, UsageTracker
from .formatter import (
    print_banner, print_error, print_system, print_user_header, console,
    redirect_console, set_code_theme,
)
from .logger import SessionLogger
from .mcp_config import load_mcp_servers
from .mcp_manager import MCPManager, set_active_manager
from .sessions import SessionStore, list_sessions
from .settings import Settings
from .tools import register_tool


def _read_input(status_plain: str) -> str:
    """Claude-Code-style input bar:

        ╭─ ~/jarvis · 0.0k tokens ───────────╮
        │ > user types here
        ╰────────────────────────────────────╯

    The prompt must go through builtin input() (NOT console.input): Rich prints
    its prompt separately from input(), so any readline redraw repaints the line
    from column 0 and erases it. ANSI codes inside the prompt are wrapped in
    \\001/\\002 so readline excludes them from its length accounting.
    """
    width = max(min(console.width, 120), 20)
    top = f"╭─ {status_plain} " + "─" * max(width - len(status_plain) - 5, 0) + "╮"
    console.print(f"[bright_black]{top}[/bright_black]")
    prompt = "\001\x1b[2m\002│\001\x1b[0m\002 \001\x1b[1m\002>\001\x1b[0m\002 "
    try:
        return input(prompt)
    finally:
        console.print("[bright_black]╰" + "─" * (width - 2) + "╯[/bright_black]")


def _read_full_input(status_plain: str) -> str:
    """Read one logical line of user input, joining continuation lines.

    Two forms: a line ending in `\\` continues onto the next line (backslash
    stripped, lines joined with `\\n`); a line that is exactly ``` opens a
    fenced block that reads raw lines (no continuation prompt box) until a
    closing ```. Continuation lines use a plain `... ` prompt like Python's
    REPL, since redrawing the boxed prompt for each line would be noisy.
    """
    line = _read_input(status_plain)
    if line.strip() == "```":
        lines: list[str] = []
        while True:
            try:
                cont = input("... ")
            except EOFError:
                break
            if cont.strip() == "```":
                break
            lines.append(cont)
        return "\n".join(lines)

    lines = []
    while line.endswith("\\"):
        lines.append(line[:-1])
        try:
            line = input("... ")
        except EOFError:
            return "\n".join(lines)
    lines.append(line)
    return "\n".join(lines)


def _read_piped_stdin() -> str | None:
    """Read piped stdin (e.g. `cat x | jarvis -p`), or None if none is available.

    Must check isatty() first: reading from an interactive terminal would block
    waiting for EOF, hanging the REPL forever.
    """
    if sys.stdin.isatty():
        return None
    try:
        text = sys.stdin.read()
    except (OSError, ValueError):
        return None
    text = text.strip()
    return text or None


def _compose_one_shot_prompt(prompt: str | None, piped: str | None) -> str | None:
    """Combine the -p prompt and piped stdin into the effective one-shot prompt.

    The instruction comes first so the model reads it before the piped payload.
    """
    if prompt is None:
        return piped
    if piped is None:
        return prompt
    return f"{prompt}\n\n{piped}"


def _gh_token() -> str | None:
    """Get GitHub token from gh CLI, fall back to env var."""
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except FileNotFoundError:
        pass
    return os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")


def _az_logged_in() -> bool:
    """Return True if `az account show` succeeds."""
    try:
        r = subprocess.run(["az", "account", "show"], capture_output=True, timeout=8)
        return r.returncode == 0
    except FileNotFoundError:
        return False


def _connect_mcp(mcp: MCPManager, label: str, command: str, args: list[str], env: dict[str, str]) -> None:
    try:
        with console.status(f"[dim]Connecting to {label}...[/dim]", spinner="dots"):
            tools = mcp.connect(name=label, command=command, args=args, env=env)
        for tool in tools:
            register_tool(tool)
        console.print(f"[dim]  ✓ {label} ({len(tools)} tools)[/dim]")
    except Exception as e:
        console.print(f"[dim]  ✗ {label} unavailable: {e}[/dim]")


def _init_mcp(mcp: MCPManager) -> None:
    # GitHub — prefer gh CLI auth, fall back to env var
    github_token = _gh_token()
    if github_token:
        _connect_mcp(
            mcp, "GitHub MCP",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": github_token},
        )

    # Azure — uses DefaultAzureCredential (picks up `az login` automatically)
    if _az_logged_in():
        _connect_mcp(
            mcp, "Azure MCP",
            command="npx",
            args=["-y", "@azure/mcp@latest", "server", "start"],
            env={},
        )

    # Brave Search — needs BRAVE_API_KEY (free tier: brave.com/search/api)
    brave_key = os.getenv("BRAVE_API_KEY")
    if brave_key:
        _connect_mcp(
            mcp, "Brave Search MCP",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            env={"BRAVE_API_KEY": brave_key},
        )

    # Extra servers from ~/.jarvis/mcp.json and project .mcp.json
    for entry in load_mcp_servers():
        _connect_mcp(mcp, entry["name"], entry["command"], entry["args"], entry["env"])


def _result_payload(result: str, is_error: bool, tracker: UsageTracker) -> dict:
    """Build the headless `--output-format json`/`stream-json` result object."""
    return {
        "type": "result",
        "subtype": "error" if is_error else "success",
        "is_error": is_error,
        "result": result,
        "usage": {
            "input_tokens": tracker.prompt_tokens,
            "output_tokens": tracker.completion_tokens,
            "cached_input_tokens": tracker.cached_tokens,
        },
    }


def _emit_result(fmt: str, payload: dict, init_meta: dict, out) -> None:
    """Write the headless result payload to `out` in the given format."""
    if fmt == "json":
        out.write(json.dumps(payload) + "\n")
    elif fmt == "stream-json":
        out.write(json.dumps({"type": "system", "subtype": "init", **init_meta}) + "\n")
        out.write(json.dumps(payload) + "\n")


def _run_one_shot(
    prompt: str, connect_mcp: bool, debug: bool = False, max_turns: int | None = None,
    model: str | None = None, output_format: str = "text",
) -> None:
    """Run a single agent turn non-interactively and exit 0/1 — no banner, no
    readline loop, and MCP servers only connect if the caller asked for them."""
    try:
        config = Config.load()
    except RuntimeError as e:
        print_error(str(e))
        sys.exit(1)

    if model:
        config = dataclasses.replace(config, deployment=model)

    if output_format != "text":
        redirect_console(sys.stderr)

    client = JarvisClient(config)
    tracker = UsageTracker()
    logger = SessionLogger(cwd=os.getcwd(), level="debug" if debug else "info")
    session = SessionStore(cwd=os.getcwd())
    jarvis_md = _find_jarvis_md()
    context = ContextManager(project_context=jarvis_md[0] if jarvis_md else None)

    if connect_mcp:
        mcp = MCPManager()
        set_active_manager(mcp)
        _init_mcp(mcp)

    set_auto_mode(True)

    exit_code = 0
    is_error = False
    try:
        result = run_agent(prompt, client, context, tracker, logger, session, max_iterations=max_turns)
    except Exception as e:
        logger.error(str(e))
        print_error(f"Unexpected error: {e}")
        result = str(e)
        is_error = True
        exit_code = 1

    logger.end(tracker.prompt_tokens, tracker.completion_tokens)
    _emit_result(
        output_format, _result_payload(result, is_error, tracker),
        {"model": client.current_deployment(), "cwd": os.getcwd()}, sys.stdout,
    )
    sys.exit(exit_code)


def main() -> None:
    args = _parse_args(sys.argv[1:])
    piped = _read_piped_stdin()
    effective = _compose_one_shot_prompt(args.prompt, piped)
    if effective is not None:
        _run_one_shot(
            effective, connect_mcp=args.mcp, debug=args.debug,
            max_turns=args.max_turns, model=args.model,
            output_format=args.output_format,
        )

    try:
        config = Config.load()
    except RuntimeError as e:
        print_error(str(e))
        sys.exit(1)

    if args.model:
        config = dataclasses.replace(config, deployment=args.model)

    set_code_theme(Settings.load().theme)

    client = JarvisClient(config)
    tracker = UsageTracker()
    mcp = MCPManager()
    logger = SessionLogger(cwd=os.getcwd(), level="debug" if args.debug else "info")
    session = SessionStore(cwd=os.getcwd())

    # Load JARVIS.md project context if present
    jarvis_md = _find_jarvis_md()
    context = ContextManager(project_context=jarvis_md[0] if jarvis_md else None)

    continue_status: str | None = None
    if args.continue_:
        recent = list_sessions(cwd=os.getcwd(), limit=1)
        if recent:
            session, history = SessionStore.load(recent[0]["session_id"])
            context.load_history(history)
            continue_status = f"[dim]  ✓ Resumed session {session.session_id} ({len(history)} messages)[/dim]"
        else:
            continue_status = "[dim]  No previous session found for this directory — starting fresh.[/dim]"

    print_banner(model=client.current_deployment(), cwd=os.getcwd())
    if jarvis_md:
        console.print(f"[dim]  ✓ Project context loaded ({jarvis_md[1]})[/dim]")
    if continue_status:
        console.print(continue_status)
    _init_mcp(mcp)
    print_system("Type /help for available commands. Ctrl+C twice to exit.")
    if args.debug:
        print_system(f"Debug logging enabled — {logger.path}")
    console.print()

    import readline
    readline.parse_and_bind("tab: complete")

    # Check for a resume state written before the last restart
    resume_message: str | None = None
    if _RESUME_FILE.exists():
        try:
            resume = json.loads(_RESUME_FILE.read_text())
            _RESUME_FILE.unlink()
            if resume.get("auto"):
                set_auto_mode(True)
                console.print("[dim yellow]Auto mode restored from resume state.[/dim yellow]")
            if resume.get("dangerously_skip_permissions"):
                set_dangerously_skip_permissions(True)
                console.print("[dim red]Dangerously skip permissions restored from resume state.[/dim red]")
            if resume.get("plan"):
                set_plan_mode(True)
                console.print("[dim blue]Plan mode restored from resume state.[/dim blue]")
            resume_message = resume.get("message")
        except Exception:
            _RESUME_FILE.unlink(missing_ok=True)

    if resume_message:
        print_user_header(resume_message)
        try:
            run_agent(resume_message, client, context, tracker, logger, session)
        except Exception as e:
            print_error(f"Resume error: {e}")

    interrupted_once = False
    try:
        while True:
            try:
                console.print()
                cwd = Path.cwd()
                try:
                    short = "~" / cwd.relative_to(Path.home())
                except ValueError:
                    short = cwd
                status = f"{short} · {context.token_estimate() / 1000:.1f}k tokens"
                if is_plan_mode():
                    status += " · PLAN"
                if is_auto_mode():
                    status += " · AUTO"
                if is_dangerously_skip_permissions():
                    status += " · DANGER"
                user_input = _read_full_input(status).strip()
                if user_input:
                    readline.add_history(user_input)
                interrupted_once = False
            except EOFError:
                print_system("\nGoodbye.")
                break
            except KeyboardInterrupt:
                # Claude-Code-style: first Ctrl+C warns, a second consecutive one exits.
                if interrupted_once:
                    print_system("\nGoodbye.")
                    break
                interrupted_once = True
                console.print()
                print_system("(Press Ctrl+C again to exit)")
                continue

            if not user_input:
                continue

            if user_input.startswith("#"):
                note = user_input[1:].strip()
                if note:
                    from .commands import append_memory
                    print_system(append_memory(note))
                continue

            if user_input.startswith("/"):
                try:
                    result = handle_command(user_input, client, context, tracker, session)
                    if result == _EXIT_SENTINEL:
                        break
                    if result and result.startswith(_RUN_AGENT_PREFIX):
                        agent_message = result[len(_RUN_AGENT_PREFIX):]
                        try:
                            checkpoints.checkpoint_turn(context, user_input)
                            run_agent(agent_message, client, context, tracker, logger, session)
                        except KeyboardInterrupt:
                            console.print()
                            print_system("Cancelled.")
                        except Exception as e:
                            print_error(f"Unexpected error: {e}")
                except Exception as e:
                    print_error(f"Command failed: {e}")
                continue

            print_user_header(user_input)
            try:
                checkpoints.checkpoint_turn(context, user_input)
                run_agent(build_multimodal_content(expand_file_mentions(user_input)), client, context, tracker, logger, session)
            except KeyboardInterrupt:
                console.print()
                print_system("Cancelled.")
            except Exception as e:
                logger.error(str(e))
                print_error(f"Unexpected error: {e}")
    finally:
        logger.end(tracker.prompt_tokens, tracker.completion_tokens)
