# ADR-005: CLI Framework Selection

## Status

Accepted

## Context

We needed a CLI framework for the text-adventure command-line tool. Requirements:

- Modern, type-safe command definition
- Good help text generation
- Support for subcommands (play, generate, ai-play, etc.)
- Rich output formatting (colors, progress indicators)
- Async support for LLM operations

Options considered:
1. **argparse**: Standard library, verbose, no rich output
2. **Click**: Popular, mature, some type support
3. **Typer**: Built on Click, full type hints, modern
4. **Fire**: Auto-generates CLI from functions, less control

## Decision

We chose **Typer** with **Rich** for output formatting.

```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def generate(
    theme: Annotated[str, typer.Option("--theme", "-t")] = "mysterious manor",
    rooms: Annotated[int, typer.Option("--rooms", "-r", min=3, max=20)] = 8,
) -> None:
    """Generate a new text adventure game using AI."""
    ...
```

### Command Structure

```
text-adventure
├── play <game.json>     # Play interactively
├── generate             # Generate new game
├── ai-play <game.json>  # Watch AI play
├── validate <game.json> # Validate game file
└── config               # Show configuration
```

## Consequences

### Positive

- **Type safety**: Arguments are validated by type annotations
- **Auto-documentation**: Help text generated from docstrings and type hints
- **Rich integration**: Progress spinners, colored output, formatted tables
- **Modern Python**: Uses Annotated types, clean syntax
- **Async friendly**: Works well with asyncio for LLM calls

### Negative

- **Extra dependencies**: Typer + Rich add to install size (~2MB)
- **Learning curve**: Typer's annotation syntax differs from argparse

### Neutral

- Click is a transitive dependency (Typer is built on it)
- Shell completion could be added but isn't essential for this use case

## References

- [Typer Documentation](https://typer.tiangolo.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
- `src/text_adventure/cli.py` - CLI implementation
- `src/text_adventure/ui/plain.py` - Output formatting utilities
