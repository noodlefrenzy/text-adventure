"""
cli.py

PURPOSE: Command-line interface for the text adventure game.
DEPENDENCIES: typer, rich

ARCHITECTURE NOTES:
The CLI provides commands for:
- play: Play a game interactively
- validate: Validate a game file
- generate: Generate a new game (Phase 6)
- ai-play: Watch AI play a game (Phase 7)
"""

import asyncio
import curses
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Protocol

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from text_adventure import __version__
from text_adventure.config import get_settings
from text_adventure.engine.engine import GameEngine
from text_adventure.generator import (
    AsciiArtGenerator,
    GameGenerationError,
    GameGenerator,
)
from text_adventure.llm.anthropic import create_anthropic_client
from text_adventure.models.game import Game
from text_adventure.observability import init_telemetry
from text_adventure.player import AIPlayer, PlaySession
from text_adventure.ui import plain
from text_adventure.ui.curses_ui import init_curses_ui

if TYPE_CHECKING:
    from curses import window as CursesWindow


class UIProtocol(Protocol):
    """Protocol for UI implementations."""

    def print_room(self, text: str, ascii_art: str | None = None) -> None: ...
    def print_message(self, text: str) -> None: ...
    def print_error(self, text: str) -> None: ...
    def print_prompt(self) -> str: ...
    def print_title(self, title: str) -> None: ...
    def print_game_over(self, won: bool, message: str) -> None: ...
    def print_debug(self, data: dict[str, object] | str) -> None: ...

app = typer.Typer(
    name="text-adventure",
    help="Generate and play LLM-powered text adventure games.",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"text-adventure version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """LLM Text Adventure - Generate and play text adventure games."""
    pass


def _get_room_ascii_art(game: Game, room_id: str) -> str | None:
    """Get ASCII art for a room if available."""
    room = game.get_room(room_id)
    return room.ascii_art if room else None


def _run_game_loop(
    game: Game,
    engine: GameEngine,
    ui: UIProtocol,
    debug: bool = False,
) -> None:
    """Run the main game loop with the given UI."""
    # Track last room to detect room changes
    last_room = engine.state.current_room

    # Show title
    ui.print_title(game.metadata.title)

    if game.metadata.description:
        ui.print_message(game.metadata.description)

    # Show initial room description with ASCII art
    ascii_art = _get_room_ascii_art(game, engine.state.current_room)
    ui.print_room(engine.describe_current_room(), ascii_art=ascii_art)

    # Update turn count if UI supports it
    if hasattr(ui, "set_turn_count"):
        ui.set_turn_count(engine.state.turns)

    # Main game loop
    while True:
        try:
            user_input = ui.print_prompt()
        except (EOFError, KeyboardInterrupt):
            ui.print_message("Thanks for playing!")
            break

        if not user_input.strip():
            continue

        # Process the input
        result = engine.process_input(user_input)

        # Check for room change - show ASCII art on room entry
        current_room = engine.state.current_room
        if current_room != last_room:
            # Player moved to a new room - show ASCII art
            ascii_art = _get_room_ascii_art(game, current_room)
            ui.print_room(result.message, ascii_art=ascii_art)
            last_room = current_room
        elif result.error:
            ui.print_error(result.message)
        elif result.game_over:
            ui.print_game_over(result.won, result.message)
            break
        else:
            ui.print_message(result.message)

        # Update turn count if UI supports it
        if hasattr(ui, "set_turn_count"):
            ui.set_turn_count(engine.state.turns)

        # Debug output
        if debug:
            ui.print_debug(
                {
                    "room": engine.state.current_room,
                    "inventory": engine.state.inventory,
                    "turns": engine.state.turns,
                    "flags": engine.state.flags,
                }
            )


def _play_with_curses(
    stdscr: "CursesWindow",
    game: Game,
    debug: bool,
) -> None:
    """Play the game with curses UI."""
    ui = init_curses_ui(stdscr)
    engine = GameEngine(game)
    _run_game_loop(game, engine, ui, debug=debug)


class PlainUIAdapter:
    """Adapter to make plain module conform to UIProtocol."""

    def print_room(self, text: str, ascii_art: str | None = None) -> None:
        if ascii_art:
            console.print(ascii_art)
            console.print()
        plain.print_room(text)
        console.print()

    def print_message(self, text: str) -> None:
        plain.print_message(text)
        console.print()

    def print_error(self, text: str) -> None:
        plain.print_error(text)
        console.print()

    def print_prompt(self) -> str:
        return plain.print_prompt()

    def print_title(self, title: str) -> None:
        plain.print_title(title)
        console.print()

    def print_game_over(self, won: bool, message: str) -> None:
        plain.print_game_over(won, message)

    def print_debug(self, data: dict[str, object] | str) -> None:
        plain.print_debug(data)
        console.print()


@app.command()
def play(
    game_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the game JSON file",
            exists=True,
            readable=True,
        ),
    ],
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            "-d",
            help="Show debug information after each turn",
        ),
    ] = False,
    use_curses: Annotated[
        bool,
        typer.Option(
            "--curses",
            "-c",
            help="Use full-screen curses UI with ASCII art display",
        ),
    ] = False,
) -> None:
    """Play a text adventure game interactively."""
    # Load and validate the game
    try:
        with open(game_file) as f:
            game_data = json.load(f)
        game = Game.model_validate(game_data)
    except json.JSONDecodeError as e:
        plain.print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1) from None
    except ValidationError as e:
        plain.print_error(f"Invalid game file: {e}")
        raise typer.Exit(1) from None

    if use_curses:
        # Run with curses UI
        try:
            curses.wrapper(lambda stdscr: _play_with_curses(stdscr, game, debug))
        except curses.error as e:
            plain.print_error(f"Curses error: {e}")
            plain.print_error("Try running without --curses flag.")
            raise typer.Exit(1) from None
    else:
        # Run with plain UI
        engine = GameEngine(game)
        ui = PlainUIAdapter()
        _run_game_loop(game, engine, ui, debug=debug)


@app.command()
def validate(
    game_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the game JSON file",
            exists=True,
            readable=True,
        ),
    ],
) -> None:
    """Validate a game JSON file."""
    try:
        with open(game_file) as f:
            game_data = json.load(f)
    except json.JSONDecodeError as e:
        plain.print_error(f"Invalid JSON at line {e.lineno}: {e.msg}")
        raise typer.Exit(1) from None

    try:
        game = Game.model_validate(game_data)
    except ValidationError as e:
        plain.print_error("Validation errors:")
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            plain.print_error(f"  {loc}: {error['msg']}")
        raise typer.Exit(1) from None

    # Show validation success and stats
    plain.print_success(f"Valid game: {game.metadata.title}")
    console.print(f"  Rooms: {len(game.rooms)}")
    console.print(f"  Objects: {len(game.objects)}")
    console.print(f"  Verbs: {len(game.verbs)}")
    console.print(f"  Win condition: {game.win_condition.type}")


@app.command()
def generate(
    theme: Annotated[
        str,
        typer.Option(
            "--theme",
            "-t",
            help="Theme or setting for the game",
        ),
    ] = "mysterious manor",
    rooms: Annotated[
        int,
        typer.Option(
            "--rooms",
            "-r",
            help="Number of rooms to generate",
            min=3,
            max=20,
        ),
    ] = 8,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path (default: auto-generated)",
        ),
    ] = None,
    temperature: Annotated[
        float,
        typer.Option(
            "--temperature",
            help="Creativity level (0.0-1.0)",
            min=0.0,
            max=1.0,
        ),
    ] = 0.7,
    ascii_art: Annotated[
        bool,
        typer.Option(
            "--ascii-art",
            "-a",
            help="Generate ASCII art for each room",
        ),
    ] = False,
) -> None:
    """Generate a new text adventure game using AI."""
    settings = get_settings()

    # Initialize telemetry
    init_telemetry(settings.otel)

    # Check for API key
    if not settings.llm.anthropic_api_key:
        plain.print_error("ANTHROPIC_API_KEY environment variable not set.")
        plain.print_error("Please set it to use the generate command.")
        raise typer.Exit(1)

    # Determine output path
    if output is None:
        # Generate filename from theme
        safe_theme = re.sub(r"[^a-z0-9]+", "_", theme.lower()).strip("_")
        output = Path(f"{safe_theme}.json")

    # Check if file exists
    if output.exists() and not typer.confirm(f"File {output} already exists. Overwrite?"):
        raise typer.Exit(0)

    console.print(f"[bold]Generating game:[/bold] {theme}")
    console.print(f"  Rooms: {rooms}")
    console.print(f"  Temperature: {temperature}")
    console.print(f"  ASCII art: {ascii_art}")
    console.print(f"  Output: {output}")
    console.print()

    # Create client and generator
    client = create_anthropic_client(
        api_key=settings.llm.anthropic_api_key,
        model=settings.llm.model,
    )

    async def do_generate() -> Game:
        generator = GameGenerator(client)
        game = await generator.generate(
            theme=theme,
            num_rooms=rooms,
            temperature=temperature,
        )

        # Add ASCII art if requested (two-pass generation)
        if ascii_art:
            art_generator = AsciiArtGenerator(client)
            game = await art_generator.generate_for_game(game, temperature=temperature)

        return game

    # Run generation with progress indicator
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_desc = "Generating game..."
            if ascii_art:
                task_desc = "Generating game with ASCII art..."
            progress.add_task(task_desc, total=None)
            game = asyncio.run(do_generate())
    except GameGenerationError as e:
        plain.print_error(f"Generation failed: {e}")
        raise typer.Exit(1) from None

    # Save the game
    with open(output, "w") as f:
        json.dump(game.model_dump(mode="json"), f, indent=2)

    plain.print_success(f"Game saved to {output}")
    console.print()
    console.print(f"[bold]{game.metadata.title}[/bold]")
    console.print(f"  {game.metadata.description}")
    console.print()
    console.print(f"  Rooms: {len(game.rooms)}")
    console.print(f"  Objects: {len(game.objects)}")
    console.print(f"  Win condition: {game.win_condition.type}")
    if ascii_art:
        rooms_with_art = sum(1 for r in game.rooms if r.ascii_art)
        console.print(f"  Rooms with ASCII art: {rooms_with_art}")
    console.print()
    console.print(f"Play with: [bold]text-adventure play {output}[/bold]")


@app.command("ai-play")
def ai_play(
    game_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the game JSON file",
            exists=True,
            readable=True,
        ),
    ],
    max_turns: Annotated[
        int,
        typer.Option(
            "--max-turns",
            "-m",
            help="Maximum turns before stopping",
            min=1,
            max=1000,
        ),
    ] = 100,
    delay: Annotated[
        float,
        typer.Option(
            "--delay",
            help="Delay between turns in seconds (for readability)",
            min=0.0,
            max=10.0,
        ),
    ] = 0.5,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed game output",
        ),
    ] = False,
    use_curses: Annotated[
        bool,
        typer.Option(
            "--curses",
            "-c",
            help="Use full-screen curses UI with ASCII art display",
        ),
    ] = False,
) -> None:
    """Watch an AI player play through a game."""
    import time

    from text_adventure.engine.engine import TurnResult

    settings = get_settings()

    # Initialize telemetry
    init_telemetry(settings.otel)

    # Check for API key
    if not settings.llm.anthropic_api_key:
        plain.print_error("ANTHROPIC_API_KEY environment variable not set.")
        plain.print_error("Please set it to use the ai-play command.")
        raise typer.Exit(1)

    # Load the game
    try:
        with open(game_file) as f:
            game_data = json.load(f)
        game = Game.model_validate(game_data)
    except json.JSONDecodeError as e:
        plain.print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1) from None
    except ValidationError as e:
        plain.print_error(f"Invalid game file: {e}")
        raise typer.Exit(1) from None

    def _run_ai_play_plain() -> PlaySession:
        """Run AI play with plain text UI."""
        # Show game info
        plain.print_title(f"AI Playing: {game.metadata.title}")
        console.print()
        if game.metadata.description:
            console.print(f"[italic]{game.metadata.description}[/italic]")
            console.print()
        console.print(f"Max turns: {max_turns}")
        console.print()

        # Create client and player
        client = create_anthropic_client(
            api_key=settings.llm.anthropic_api_key,
            model=settings.llm.model,
        )
        player = AIPlayer(client)

        # Track last room to detect room changes
        last_room: str | None = None

        def on_turn(turn: int, command: str, result: TurnResult) -> None:
            """Display each turn."""
            nonlocal last_room

            if delay > 0:
                time.sleep(delay)

            # Show turn with token count if available
            turn_header = f"[bold cyan]Turn {turn}:[/bold cyan] [yellow]{command}[/yellow]"
            console.print(turn_header)

            # Detect room change and show ASCII art
            if result.new_room and result.new_room != last_room:
                ascii_art = _get_room_ascii_art(game, result.new_room)
                if ascii_art:
                    console.print()
                    console.print(ascii_art)
                last_room = result.new_room

            if result.error:
                console.print(f"[red]{result.message}[/red]")
            elif result.game_over:
                console.print()
                if result.won:
                    console.print(f"[bold green]{result.message}[/bold green]")
                else:
                    console.print(f"[bold red]{result.message}[/bold red]")
            else:
                # Always show game output so viewers can follow along
                console.print(result.message)

            if verbose:
                # Verbose mode shows token usage and debug info
                debug_parts = [f"error={result.error}", f"game_over={result.game_over}"]
                console.print(f"[dim]  ({', '.join(debug_parts)})[/dim]")

            console.print()

        async def do_play() -> PlaySession:
            return await player.play(game, max_turns=max_turns, on_turn=on_turn)

        return asyncio.run(do_play())

    def _run_ai_play_curses(stdscr: "CursesWindow") -> PlaySession:
        """Run AI play with curses UI."""
        ui = init_curses_ui(stdscr)

        # Show game info
        ui.print_title(f"AI Playing: {game.metadata.title}")
        if game.metadata.description:
            ui.print_message(game.metadata.description)
        ui.print_message(f"Max turns: {max_turns}")

        # Create client and player
        client = create_anthropic_client(
            api_key=settings.llm.anthropic_api_key,
            model=settings.llm.model,
        )
        player = AIPlayer(client)

        # Track last room to detect room changes
        last_room: str | None = None

        def on_turn(turn: int, command: str, result: TurnResult) -> None:
            """Display each turn."""
            nonlocal last_room

            if delay > 0:
                time.sleep(delay)

            # Update status
            ui.set_turn_count(turn)
            ui.print_message(f"Turn {turn}: {command}")

            # Detect room change and show ASCII art
            if result.new_room and result.new_room != last_room:
                ascii_art = _get_room_ascii_art(game, result.new_room)
                ui.print_room(result.message, ascii_art=ascii_art)
                last_room = result.new_room
            elif result.error:
                ui.print_error(result.message)
            elif result.game_over:
                ui.print_game_over(result.won, result.message)
            else:
                ui.print_message(result.message)

            if verbose:
                debug_parts = [f"error={result.error}", f"game_over={result.game_over}"]
                ui.print_message(f"  ({', '.join(debug_parts)})")

        async def do_play() -> PlaySession:
            return await player.play(game, max_turns=max_turns, on_turn=on_turn)

        return asyncio.run(do_play())

    # Run the AI player
    try:
        if use_curses:  # noqa: SIM108 - clarity over ternary for different function signatures
            session_result = curses.wrapper(_run_ai_play_curses)
        else:
            session_result = _run_ai_play_plain()
    except KeyboardInterrupt:
        console.print()
        plain.print_message("AI play interrupted.")
        raise typer.Exit(0) from None
    except curses.error as e:
        plain.print_error(f"Curses error: {e}")
        plain.print_error("Try running without --curses flag.")
        raise typer.Exit(1) from None

    # Show final results (always in plain text after curses exits)
    console.print("[bold]─── Results ───[/bold]")
    console.print()
    console.print(f"Turns taken: {session_result.turns}")
    console.print(f"Rooms visited: {len(session_result.rooms_visited)}")
    console.print(f"Items collected: {len(session_result.items_collected)}")
    console.print()

    # Token usage stats
    console.print("[bold]─── Token Usage ───[/bold]")
    console.print()
    console.print(f"Input tokens:  {session_result.total_input_tokens:,}")
    console.print(f"Output tokens: {session_result.total_output_tokens:,}")
    console.print(f"Total tokens:  {session_result.total_tokens:,}")
    if session_result.turns > 0:
        console.print(f"Avg per turn:  {session_result.avg_tokens_per_turn:,.0f}")
    console.print()

    if session_result.won:
        plain.print_success("AI player won the game!")
    elif session_result.gave_up:
        plain.print_error("AI player got stuck and gave up.")
    else:
        plain.print_message("AI player reached the turn limit.")


@app.command("config")
def config_cmd(
    show: Annotated[
        bool,
        typer.Option(
            "--show",
            "-s",
            help="Show current configuration",
        ),
    ] = True,
) -> None:
    """Show or modify configuration."""
    if show:
        settings = get_settings()
        console.print("[bold]Current Configuration:[/bold]")
        console.print(f"  Data directory: {settings.data_dir}")
        console.print(f"  Log level: {settings.log_level}")
        console.print(f"  Debug: {settings.debug}")
        console.print()
        console.print("[bold]LLM Settings:[/bold]")
        console.print(f"  Provider: {settings.llm.provider}")
        console.print(f"  Model: {settings.llm.model}")
        console.print(f"  Temperature: {settings.llm.temperature}")
        api_key_status = "set" if settings.llm.anthropic_api_key else "not set"
        console.print(f"  API Key: {api_key_status}")
        console.print()
        console.print("[bold]OpenTelemetry Settings:[/bold]")
        console.print(f"  Enabled: {settings.otel.enabled}")
        console.print(f"  Service name: {settings.otel.service_name}")
        endpoint_status = settings.otel.endpoint if settings.otel.endpoint else "(console only)"
        console.print(f"  Endpoint: {endpoint_status}")


if __name__ == "__main__":
    app()
