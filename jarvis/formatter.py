from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel

console = Console()

# Claude-Code-style accent for the assistant/tool bullet
ACCENT = "#d97757"

# Pygments style used for fenced code blocks in rendered markdown. Set from
# Settings.theme at startup (cli.py) and by `/theme`; an unknown pygments style
# name degrades to Rich's default rather than raising.
_code_theme = "monokai"


def set_code_theme(name: str) -> None:
    global _code_theme
    _code_theme = name


def get_code_theme() -> str:
    return _code_theme


def print_banner(model: str = "", cwd: str = "") -> None:
    lines = ["[bold]✻ Welcome to Jarvis![/bold]"]
    if model or cwd:
        lines.append("")
    if model:
        lines.append(f"  [dim]model:[/dim] {model}")
    if cwd:
        lines.append(f"  [dim]cwd:[/dim]   {cwd}")
    console.print()
    console.print(Panel("\n".join(lines), border_style="bright_black", expand=False, padding=(0, 2)))
    console.print()


def print_user_header(message: str) -> None:
    console.print(f"[bold bright_black]>[/bold bright_black] [dim]{message}[/dim]")
    console.print()


def print_jarvis_header() -> None:
    console.print(f"[{ACCENT}]⏺[/{ACCENT}]")


def make_live_markdown() -> Live:
    return Live(
        Markdown("", code_theme=_code_theme),
        console=console,
        refresh_per_second=15,
        vertical_overflow="visible",
    )


def render_markdown_block(text: str) -> Padding:
    """Assistant markdown, indented under the ⏺ bullet."""
    return Padding(Markdown(text, code_theme=_code_theme), (0, 0, 0, 2))


def print_assistant_markdown(text: str) -> None:
    print_jarvis_header()
    console.print(render_markdown_block(text))


def print_tool_use(label: str) -> None:
    """One tool invocation, Claude Code style: ⏺ Reading(jarvis/cli.py)"""
    console.print(f"[green]⏺[/green] [bold]{label}[/bold]")


def print_tool_result(result: str, error: bool = False) -> None:
    """Indented one-line summary under the tool bullet: ⎿  ..."""
    first_line = next((ln for ln in result.splitlines() if ln.strip()), "(no output)")
    if len(first_line) > 100:
        first_line = first_line[:100] + "…"
    extra = len(result.splitlines()) - 1
    suffix = f" [dim]+{extra} lines[/dim]" if extra > 0 else ""
    style = "red" if error else "bright_black"
    console.print(f"  [bright_black]⎿[/bright_black]  [{style}]{first_line}[/{style}]{suffix}")


def print_error(message: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_system(message: str) -> None:
    console.print(f"[bright_black]{message}[/bright_black]")


def print_command_output(message: str) -> None:
    console.print(f"[cyan]{message}[/cyan]")


def print_streamed_line(line: str, stderr: bool = False) -> None:
    """One line of live `run_command` output; markup disabled since the line is arbitrary shell output."""
    console.print(line, style="yellow" if stderr else None, markup=False, highlight=False)


_TODO_MARKERS = {
    "completed": ("[green]✔[/green]", "dim strike"),
    "in_progress": (f"[{ACCENT}]◐[/{ACCENT}]", "bold"),
    "pending": ("☐", ""),
}


def print_todo_list(todos: list[dict[str, str]]) -> None:
    """Rich checklist panel, re-rendered in full every time the todo list changes."""
    if not todos:
        console.print(Panel("[dim](no todos)[/dim]", title="Todos", border_style="bright_black", expand=False))
        return
    lines = []
    for todo in todos:
        marker, style = _TODO_MARKERS.get(todo["status"], _TODO_MARKERS["pending"])
        text = todo["content"]
        lines.append(f"{marker} [{style}]{text}[/{style}]" if style else f"{marker} {text}")
    console.print(Panel("\n".join(lines), title="Todos", border_style="bright_black", expand=False, padding=(0, 2)))
