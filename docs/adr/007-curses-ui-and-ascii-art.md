# ADR-007: Curses UI and ASCII Art Generation

## Status
ACCEPTED

## Context

The text adventure experience can be significantly enhanced with visual elements:
1. ASCII art for room illustrations - creating atmosphere and visual interest
2. A full-screen terminal UI - providing a more immersive experience than scrolling text

The question is how to implement these features while:
- Maintaining backward compatibility with plain text mode
- Keeping the code maintainable
- Ensuring the features work well together

## Decision

### ASCII Art Generation

We chose a **two-pass generation approach**:

1. Generate the game first (without ASCII art)
2. Add ASCII art to each room in separate LLM calls

This design was chosen over inline generation (generating art with the game) because:
- Focused prompts produce better ASCII art quality
- Existing games can be retrofitted with art
- Generation failures don't affect game creation
- Art generation can be optional via `--ascii-art` flag

**Constraints:**
- Maximum 80 characters wide (terminal standard)
- 8-15 lines tall (fits in UI without scrolling)
- ASCII-only characters (32-126, no Unicode)

### Curses UI

We implemented a **single-file UI module** (`curses_ui.py`) that:
- Matches the interface of `plain.py` for consistency
- Uses a three-pane layout:
  ```
  +------------------------------------------+
  |          ASCII ART (up to 15 lines)      |
  +------------------------------------------+
  |          Room Description                |
  |          Objects, Exits                  |
  |          [Game messages]                 |
  +------------------------------------------+
  | > [input prompt]                         |
  | [status bar: turns, room]                |
  +------------------------------------------+
  ```
- Requires minimum 80x24 terminal (standard size)
- Gracefully degrades if terminal is too small

**Activation:** Via `--curses` / `-c` flag on `play` and `ai-play` commands.

### UI Protocol

Both UIs implement a common protocol:
```python
class UIProtocol(Protocol):
    def print_room(self, text: str, ascii_art: str | None = None) -> None
    def print_message(self, text: str) -> None
    def print_error(self, text: str) -> None
    def print_prompt(self) -> str
    def print_title(self, title: str) -> None
    def print_game_over(self, won: bool, message: str) -> None
    def print_debug(self, data: dict | str) -> None
```

This allows the game loop to be UI-agnostic.

## Consequences

### Positive

- ASCII art adds atmosphere without affecting gameplay logic
- Curses UI provides immersive full-screen experience
- Plain text mode remains available for accessibility/scripting
- Two-pass generation allows retrofitting existing games
- Protocol-based UI enables future UI implementations (web, TUI libraries)

### Negative

- ASCII art generation increases game creation time (~19 extra API calls for a 19-room game)
- Curses UI requires `curses.wrapper()` which complicates error handling
- ASCII art quality depends on LLM capability; some rooms may get poor art
- Curses doesn't work well in all terminal emulators

### Neutral

- Room model gains an optional `ascii_art: str | None` field
- Game JSON files are slightly larger when including ASCII art
- AI play with curses shows art briefly during rapid turns

## References

- `src/text_adventure/generator/ascii_art.py` - ASCII art generator
- `src/text_adventure/ui/curses_ui.py` - Curses UI implementation
- `src/text_adventure/ui/plain.py` - Plain text UI (original)
- Python curses documentation: https://docs.python.org/3/library/curses.html
