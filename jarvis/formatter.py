from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.padding import Padding

console = Console()


def print_banner() -> None:
    console.print()
    console.print("  [bold cyan]J.A.R.V.I.S.[/bold cyan] [dim]v0.1.0[/dim]")
    console.print("  [dim]Just A Rather Very Intelligent System[/dim]")
    console.print()


def print_user_header(message: str) -> None:
    console.print(f"[bold]You[/bold]")
    console.print(f"[dim]{message}[/dim]")
    console.print()


def print_jarvis_header() -> None:
    console.print(f"[bold cyan]Jarvis[/bold cyan]")


def make_live_markdown() -> Live:
    return Live(
        Markdown(""),
        console=console,
        refresh_per_second=15,
        vertical_overflow="visible",
    )


def print_tool_call(tool_name: str, brief_args: str) -> None:
    console.print(f"[dim]  [{tool_name}: {brief_args}][/dim]")


def print_streaming_token(token: str) -> None:
    console.print(token, end="", markup=False)


def print_assistant_markdown(text: str) -> None:
    console.print(Markdown(text))


def print_error(message: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_system(message: str) -> None:
    console.print(f"[yellow]{message}[/yellow]")


def print_command_output(message: str) -> None:
    console.print(f"[cyan]{message}[/cyan]")


def get_user_prompt() -> str:
    return console.input("[bold]> [/bold]")
