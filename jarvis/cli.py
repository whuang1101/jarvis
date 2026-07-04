from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_RESUME_FILE = Path.home() / ".jarvis" / "resume.json"


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
from .permissions import is_auto_mode, set_auto_mode
from .context import is_plan_mode, set_plan_mode
from .config import Config
from .context import ContextManager, UsageTracker
from .formatter import print_banner, print_error, print_system, print_user_header, console
from .logger import SessionLogger
from .mcp_manager import MCPManager
from .tools import register_tool


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


def main() -> None:
    try:
        config = Config.load()
    except RuntimeError as e:
        print_error(str(e))
        sys.exit(1)

    client = JarvisClient(config)
    tracker = UsageTracker()
    mcp = MCPManager()
    logger = SessionLogger(cwd=os.getcwd())

    # Load JARVIS.md project context if present
    jarvis_md = _find_jarvis_md()
    context = ContextManager(project_context=jarvis_md[0] if jarvis_md else None)

    print_banner()
    if jarvis_md:
        console.print(f"[dim]  ✓ Project context loaded ({jarvis_md[1]})[/dim]")
    _init_mcp(mcp)
    print_system("Type /help for available commands. Ctrl+D to exit.")
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
            if resume.get("plan"):
                set_plan_mode(True)
                console.print("[dim blue]Plan mode restored from resume state.[/dim blue]")
            resume_message = resume.get("message")
        except Exception:
            _RESUME_FILE.unlink(missing_ok=True)

    if resume_message:
        print_user_header(resume_message)
        try:
            run_agent(resume_message, client, context, tracker, logger)
        except Exception as e:
            print_error(f"Resume error: {e}")

    try:
        while True:
            try:
                console.rule(style="dim")
                cwd = Path.cwd()
                try:
                    short = "~" / cwd.relative_to(Path.home())
                except ValueError:
                    short = cwd
                tags = f" [{context.token_estimate() / 1000:.1f}k]"
                if is_plan_mode():
                    tags += " [bold blue]PLAN[/bold blue]"
                if is_auto_mode():
                    tags += " [bold yellow]AUTO[/bold yellow]"
                user_input = console.input(f"[dim]{short}[/dim]{tags} [bold]>[/bold] ").strip()
                if user_input:
                    readline.add_history(user_input)
            except EOFError:
                print_system("\nGoodbye.")
                break
            except KeyboardInterrupt:
                print_system("\nGoodbye.")
                break

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
                            run_agent(agent_message, client, context, tracker, logger)
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
                run_agent(user_input, client, context, tracker, logger)
            except KeyboardInterrupt:
                console.print()
                print_system("Cancelled.")
            except Exception as e:
                logger.error(str(e))
                print_error(f"Unexpected error: {e}")
    finally:
        logger.end(tracker.prompt_tokens, tracker.completion_tokens)
