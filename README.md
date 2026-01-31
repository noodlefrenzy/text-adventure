# LLM Text Adventure

A Python CLI tool for generating and playing classic text adventure games using LLMs.

Generate rich, puzzle-filled adventures with AI, then play them yourself or watch an AI player explore and solve them.

## Features

- **Generate Games**: Create complete game worlds from a theme description using Claude AI
  - Interconnected rooms with descriptions
  - Interactive objects with examine text
  - Puzzles with locked doors, keys, and containers
  - Win conditions that feel satisfying to achieve
  - Optional ASCII art generation for each room

- **Play Games**: Classic Zork-style parser for human gameplay
  - Full-screen curses UI with ASCII art display
  - Full Infocom-style command parsing (PUT THE BRASS KEY IN THE WOODEN BOX)
  - Adjective-based disambiguation (TAKE BRASS KEY vs SILVER KEY)
  - All standard verbs: TAKE, DROP, EXAMINE, OPEN, CLOSE, UNLOCK, READ, TALK, etc.
  - Custom verbs defined in game JSON (no Python changes needed)

- **AI Player**: Watch an AI explore and solve your adventures
  - LLM-powered decision making
  - Progress tracking (rooms visited, items collected)
  - Configurable turn limits and display options

- **Validate Games**: Check game files for correctness before playing

## Installation

### Requirements

- Python 3.11 or higher
- An [Anthropic API key](https://console.anthropic.com/) for generation and AI play features

### Install from Source

```bash
git clone https://github.com/noodlefrenzy/text-adventure.git
cd text-adventure
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

### Environment Setup

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

Or create a `.env` file in your project directory:
```
ANTHROPIC_API_KEY=your-api-key-here
```

## Quick Start

### Generate a Game

```bash
# Generate with default settings (8 rooms, "mysterious manor" theme)
text-adventure generate

# Specify theme and room count
text-adventure generate --theme "pirate ship" --rooms 10

# Save to specific file
text-adventure generate --theme "haunted lighthouse" -o lighthouse.json

# Generate with ASCII art for each room
text-adventure generate --theme "cyberpunk megacity" --ascii-art
```

### Play a Game

```bash
# Play interactively
text-adventure play game.json

# Play with debug output (shows game state)
text-adventure play game.json --debug

# Play with full-screen curses UI (displays ASCII art)
text-adventure play game.json --curses
```

### Watch AI Play

```bash
# Watch AI play with default settings
text-adventure ai-play game.json

# Slower playback with detailed output
text-adventure ai-play game.json --delay 1.0 --verbose

# Limit turns
text-adventure ai-play game.json --max-turns 50

# Watch with full-screen curses UI
text-adventure ai-play game.json --curses
```

### Validate a Game

```bash
text-adventure validate game.json
```

## Command Reference

### `generate`

Generate a new text adventure game using AI.

```
Options:
  -t, --theme TEXT           Theme/setting for the game [default: mysterious manor]
  -r, --rooms INTEGER        Number of rooms (3-20) [default: 8]
  -o, --output PATH          Output file path [default: auto-generated]
  --temperature FLOAT        Creativity level (0.0-1.0) [default: 0.7]
  -a, --ascii-art            Generate ASCII art for each room
```

### `play`

Play a text adventure game interactively.

```
Arguments:
  GAME_FILE                  Path to the game JSON file

Options:
  -d, --debug               Show debug information after each turn
  -c, --curses              Use full-screen curses UI with ASCII art display
```

### `ai-play`

Watch an AI player play through a game.

```
Arguments:
  GAME_FILE                  Path to the game JSON file

Options:
  -m, --max-turns INTEGER    Maximum turns before stopping [default: 100]
  --delay FLOAT              Delay between turns in seconds [default: 0.5]
  -v, --verbose              Show detailed game output
  -c, --curses               Use full-screen curses UI with ASCII art display
```

### `validate`

Validate a game JSON file.

```
Arguments:
  GAME_FILE                  Path to the game JSON file
```

### `config`

Show current configuration.

```
Options:
  -s, --show                 Show current configuration [default: true]
```

## Supported Commands (In-Game)

When playing, you can use these commands:

| Command | Aliases | Description |
|---------|---------|-------------|
| `NORTH` | `N` | Go north |
| `SOUTH` | `S` | Go south |
| `EAST` | `E` | Go east |
| `WEST` | `W` | Go west |
| `UP` | `U` | Go up |
| `DOWN` | `D` | Go down |
| `LOOK` | `L` | Describe current room |
| `EXAMINE <obj>` | `X <obj>`, `LOOK AT <obj>` | Examine an object |
| `TAKE <obj>` | `GET <obj>`, `PICK UP <obj>` | Take an object |
| `DROP <obj>` | `PUT DOWN <obj>` | Drop an object |
| `INVENTORY` | `I` | List inventory |
| `OPEN <obj>` | | Open a container or door |
| `CLOSE <obj>` | `SHUT <obj>` | Close a container or door |
| `READ <obj>` | | Read text on an object |
| `UNLOCK <obj> WITH <key>` | | Unlock with a key |
| `LOCK <obj> WITH <key>` | | Lock with a key |
| `PUT <obj> IN <container>` | `INSERT <obj> IN <container>` | Put object in container |
| `TALK TO <obj>` | `SPEAK TO <obj>` | Talk to a character |
| `SHOW <obj> TO <character>` | `GIVE <obj> TO <character>` | Show/give item to character |
| `ENTER <obj>` | | Enter a door or portal |
| `QUIT` | `Q`, `EXIT` | Exit the game |
| `HELP` | `?` | Show help |

## Game File Format

Games are stored as JSON files. Here's a minimal example:

```json
{
  "metadata": {
    "title": "My Adventure",
    "description": "A short adventure game."
  },
  "rooms": [
    {
      "id": "start",
      "name": "Starting Room",
      "description": "You are in a small room. An exit leads north.",
      "exits": {"north": "end"},
      "objects": ["key"]
    },
    {
      "id": "end",
      "name": "Ending Room",
      "description": "You made it!",
      "exits": {"south": "start"}
    }
  ],
  "objects": [
    {
      "id": "key",
      "name": "brass key",
      "adjectives": ["brass", "small"],
      "description": "A small brass key.",
      "location": "start",
      "takeable": true
    }
  ],
  "initial_state": {
    "current_room": "start"
  },
  "win_condition": {
    "type": "reach_room",
    "room": "end",
    "win_message": "Congratulations! You won!"
  }
}
```

See [tests/fixtures/sample_game.json](tests/fixtures/sample_game.json) for a complete example with puzzles.

### Custom Verbs and Actions

Adventure creators can define custom verbs and actions without modifying Python code:

```json
{
  "verbs": [
    {"verb": "sing", "aliases": ["perform", "karaoke"], "requires_object": false}
  ],
  "objects": [
    {
      "id": "salarymen",
      "actions": {
        "sing": {
          "message": "You belt out 'My Way' and they cheer!",
          "condition": "flags.talked_to_salarymen",
          "state_changes": {"flags.salarymen_distracted": true}
        }
      }
    }
  ]
}
```

See [docs/action-dsl-reference.md](docs/action-dsl-reference.md) for the complete Action DSL reference.

## Architecture

The project follows a clean separation of concerns:

```
src/text_adventure/
├── cli.py              # Command-line interface
├── config.py           # Configuration management
├── validator.py        # Game validation
├── models/             # Data models (Game, Command, State)
├── parser/             # Input parsing and object resolution
├── engine/             # Game logic and state management
├── generator/          # LLM-based game generation
├── player/             # AI player implementation
├── llm/                # LLM client abstraction
└── ui/                 # Output formatting
```

Key design decisions are documented in [Architecture Decision Records](docs/adr/).

## Development

### Setup

```bash
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest                    # Run all tests
pytest --cov              # With coverage
pytest tests/unit/        # Unit tests only
pytest tests/integration/ # Integration tests only
```

### Code Quality

```bash
ruff check .              # Lint
ruff format .             # Format
mypy src/                 # Type check
```

### Pre-commit Checklist

Before committing:
```bash
ruff format . && ruff check . && mypy src/ && pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Development setup
- Code style and testing
- Commit message format
- Pull request process

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Inspired by classic Infocom games like Zork, Wishbringer, and Hitchhiker's Guide to the Galaxy
- Built with [Anthropic Claude](https://www.anthropic.com/) for AI capabilities
- CLI powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
