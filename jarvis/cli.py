from __future__ import annotations

import argparse
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
from .client import JarvisClient
from .commands import handle_command, _EXIT_SENTINEL, _RUN_AGENT_PREFIX
from .permissions import (
    is_auto_mode,
    is_dangerously_skip_permissions,
    set_auto_mode,
    set_dangerously_skip_permissions,
)
from .context import is_plan_mode, set_plan_mode
from .config import Config
from .context import ContextManager, UsageTracker
from .formatter import print_banner, print_error, print_system, print_user_header, console
from .logger import SessionLogger
from .mcp_manager import MCPManager
from .sessions import SessionStore
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


def _run_one_shot(prompt: str, connect_mcp: bool) -> None:
    """Run a single agent turn non-interactively and exit 0/1 — no banner, no
    readline loop, and MCP servers only connect if the caller asked for them."""
    try:
        config = Config.load()
    except RuntimeError as e:
        print_error(str(e))
        sys.exit(1)

    client = JarvisClient(config)
    tracker = UsageTracker()
    logger = SessionLogger(cwd=os.getcwd())
    session = SessionStore(cwd=os.getcwd())
    jarvis_md = _find_jarvis_md()
    context = ContextManager(project_context=jarvis_md[0] if jarvis_md else None)

    if connect_mcp:
        _init_mcp(MCPManager())

    set_auto_mode(True)

    exit_code = 0
    try:
        run_agent(prompt, client, context, tracker, logger, session)
    except Exception as e:
        logger.error(str(e))
        print_error(f"Unexpected error: {e}")
        exit_code = 1

    logger.end(tracker.prompt_tokens, tracker.completion_tokens)
    sys.exit(exit_code)


def main() -> None:
    args = _parse_args(sys.argv[1:])
    if args.prompt is not None:
        _run_one_shot(args.prompt, connect_mcp=args.mcp)

    try:
        config = Config.load()
    except RuntimeError as e:
        print_error(str(e))
        sys.exit(1)

    client = JarvisClient(config)
    tracker = UsageTracker()
    mcp = MCPManager()
    logger = SessionLogger(cwd=os.getcwd())
    session = SessionStore(cwd=os.getcwd())

    # Load JARVIS.md project context if present
    jarvis_md = _find_jarvis_md()
    context = ContextManager(project_context=jarvis_md[0] if jarvis_md else None)

    print_banner(model=client.current_deployment(), cwd=os.getcwd())
    if jarvis_md:
        console.print(f"[dim]  ✓ Project context loaded ({jarvis_md[1]})[/dim]")
    _init_mcp(mcp)
    print_system("Type /help for available commands. Ctrl+C twice to exit.")
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
                user_input = _read_input(status).strip()
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

            if user_input.startswith("/"):
                try:
                    result = handle_command(user_input, client, context, tracker)
                    if result == _EXIT_SENTINEL:
                        break
                    if result and result.startswith(_RUN_AGENT_PREFIX):
                        agent_message = result[len(_RUN_AGENT_PREFIX):]
                        try:
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
                run_agent(user_input, client, context, tracker, logger, session)
            except KeyboardInterrupt:
                console.print()
                print_system("Cancelled.")
            except Exception as e:
                logger.error(str(e))
                print_error(f"Unexpected error: {e}")
    finally:
        logger.end(tracker.prompt_tokens, tracker.completion_tokens)
