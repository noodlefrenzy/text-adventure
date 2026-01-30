# LLM Text Adventure

A Python CLI tool for generating and playing classic text adventure games using LLMs.

## Features

- **Generate**: Create complete game worlds using AI (rooms, objects, puzzles)
- **Play**: Traditional Zork-style parser for human gameplay
- **AI Play**: Watch an AI player explore and solve your adventures
- **Validate**: Check game files for correctness

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# Generate a new game
text-adventure generate --theme "haunted house" --rooms 10

# Play a game
text-adventure play game.json

# Watch AI play
text-adventure ai-play game.json
```

## Development

```bash
# Run tests
pytest

# Type checking
mypy src/

# Lint
ruff check .
ruff format .
```

## License

MIT
