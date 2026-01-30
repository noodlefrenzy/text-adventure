"""
plain.py

PURPOSE: Plain text output formatting for the CLI.
DEPENDENCIES: rich

ARCHITECTURE NOTES:
This module provides formatted console output using Rich.
It handles:
- Room descriptions
- Object listings
- Messages and errors
- Debug output
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

# Global console instance
console = Console()


def print_room(text: str) -> None:
    """Print a room description with formatting."""
    # Room descriptions use markdown formatting
    md = Markdown(text)
    console.print(md)


def print_message(text: str) -> None:
    """Print a normal game message."""
    console.print(text)


def print_error(text: str) -> None:
    """Print an error message."""
    console.print(f"[red]{text}[/red]")


def print_success(text: str) -> None:
    """Print a success message."""
    console.print(f"[green]{text}[/green]")


def print_prompt() -> str:
    """Print the input prompt and get user input."""
    return console.input("[bold cyan]>[/bold cyan] ")


def print_title(title: str) -> None:
    """Print a game title in a panel."""
    panel = Panel(
        Text(title, justify="center", style="bold"),
        border_style="blue",
    )
    console.print(panel)


def print_help(text: str) -> None:
    """Print help text."""
    md = Markdown(text)
    console.print(md)


def print_debug(data: dict[str, object] | str) -> None:
    """Print debug information."""
    console.print("[dim]--- DEBUG ---[/dim]")
    if isinstance(data, dict):
        import json

        console.print(f"[dim]{json.dumps(data, indent=2, default=str)}[/dim]")
    else:
        console.print(f"[dim]{data}[/dim]")
    console.print("[dim]-------------[/dim]")


def print_game_over(won: bool, message: str) -> None:
    """Print game over message."""
    if won:
        style = "bold green"
        border = "green"
    else:
        style = "bold red"
        border = "red"

    panel = Panel(
        Text(message, justify="center", style=style),
        title="Game Over",
        border_style=border,
    )
    console.print(panel)


def clear_screen() -> None:
    """Clear the console."""
    console.clear()
