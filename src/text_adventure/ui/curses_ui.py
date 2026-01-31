"""
curses_ui.py

PURPOSE: Full-screen terminal UI using curses.
DEPENDENCIES: curses (stdlib)

ARCHITECTURE NOTES:
The curses UI provides a rich terminal experience with:
- ASCII art display area at the top
- Room description and game messages in the middle
- Input prompt at the bottom
- Status bar showing turn count and current room

Window layout (80x24 minimum):
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

The UI gracefully degrades if terminal is too small.
"""

import contextlib
import curses
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curses import window as CursesWindow


# Minimum terminal dimensions
MIN_WIDTH = 80
MIN_HEIGHT = 24

# Layout constants
ASCII_ART_MAX_HEIGHT = 15
INPUT_HEIGHT = 1
STATUS_HEIGHT = 1
BORDER_LINES = 2  # Separator lines


@dataclass
class WindowLayout:
    """Calculated window dimensions."""

    width: int
    height: int
    art_height: int
    content_height: int
    content_start: int
    input_row: int
    status_row: int


class CursesUI:
    """
    Full-screen curses-based UI for text adventure games.

    Provides a three-pane layout:
    - Top: ASCII art (optional)
    - Middle: Room description and game messages
    - Bottom: Input prompt and status bar
    """

    def __init__(self, stdscr: "CursesWindow"):
        """
        Initialize the curses UI.

        Args:
            stdscr: The curses standard screen.
        """
        self._stdscr = stdscr
        self._current_ascii_art: str | None = None
        self._message_history: list[tuple[str, str]] = []  # (message, style)
        self._current_room_name: str = ""
        self._turn_count: int = 0

        # Initialize curses settings
        curses.curs_set(1)  # Show cursor
        curses.use_default_colors()  # Use terminal's default colors

        # Initialize color pairs
        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_CYAN, -1)  # Art/headers
            curses.init_pair(2, curses.COLOR_GREEN, -1)  # Success
            curses.init_pair(3, curses.COLOR_RED, -1)  # Errors
            curses.init_pair(4, curses.COLOR_YELLOW, -1)  # Prompt
            curses.init_pair(5, curses.COLOR_WHITE, -1)  # Normal text
            curses.init_pair(6, curses.COLOR_MAGENTA, -1)  # Status bar

        self._layout = self._calculate_layout()

    def _calculate_layout(self) -> WindowLayout:
        """Calculate the window layout based on current terminal size."""
        height, width = self._stdscr.getmaxyx()

        # Calculate content area
        # Reserve space for: input (1) + status (1) + separators (2)
        available_for_content = height - INPUT_HEIGHT - STATUS_HEIGHT - BORDER_LINES

        # ASCII art gets up to 15 lines if we have room
        if self._current_ascii_art:
            art_lines = len(self._current_ascii_art.split("\n"))
            art_height = min(art_lines, ASCII_ART_MAX_HEIGHT, available_for_content // 2)
        else:
            art_height = 0

        content_height = available_for_content - art_height
        content_start = art_height + (1 if art_height > 0 else 0)  # Add separator if art exists

        return WindowLayout(
            width=width,
            height=height,
            art_height=art_height,
            content_height=content_height,
            content_start=content_start,
            input_row=height - 2,
            status_row=height - 1,
        )

    def _check_size(self) -> bool:
        """Check if terminal is large enough."""
        height, width = self._stdscr.getmaxyx()
        return width >= MIN_WIDTH and height >= MIN_HEIGHT

    def _addstr_safe(
        self, row: int, col: int, text: str, attr: int = 0, max_width: int | None = None
    ) -> None:
        """Safely add a string, handling boundary conditions."""
        height, width = self._stdscr.getmaxyx()
        if row < 0 or row >= height or col >= width:
            return

        max_width = max_width or (width - col)
        if len(text) > max_width:
            text = text[:max_width]

        # WHY: curses raises error when writing to bottom-right corner
        with contextlib.suppress(curses.error):
            self._stdscr.addstr(row, col, text, attr)

    def _draw_separator(self, row: int) -> None:
        """Draw a horizontal separator line."""
        width = self._layout.width
        self._addstr_safe(row, 0, "─" * width, curses.A_DIM)

    def _wrap_text(self, text: str, width: int) -> list[str]:
        """Wrap text to fit within the given width."""
        lines: list[str] = []
        for paragraph in text.split("\n"):
            if paragraph:
                wrapped = textwrap.wrap(paragraph, width=width - 1)
                lines.extend(wrapped if wrapped else [""])
            else:
                lines.append("")
        return lines

    def refresh_display(self) -> None:
        """Refresh the entire display."""
        self._stdscr.clear()
        self._layout = self._calculate_layout()

        if not self._check_size():
            self._draw_size_warning()
            self._stdscr.refresh()
            return

        # Draw ASCII art if present
        row = 0
        if self._current_ascii_art and self._layout.art_height > 0:
            row = self._draw_ascii_art()
            self._draw_separator(row)
            row += 1

        # Draw message history
        self._draw_messages(row)

        # Draw input prompt area
        self._draw_separator(self._layout.input_row - 1)
        self._draw_input_area()

        # Draw status bar
        self._draw_status_bar()

        self._stdscr.refresh()

    def _draw_size_warning(self) -> None:
        """Draw a warning that the terminal is too small."""
        height, width = self._stdscr.getmaxyx()
        msg = f"Terminal too small ({width}x{height}). Need {MIN_WIDTH}x{MIN_HEIGHT}."
        row = height // 2
        col = max(0, (width - len(msg)) // 2)
        self._addstr_safe(row, col, msg, curses.color_pair(3) | curses.A_BOLD)

    def _draw_ascii_art(self) -> int:
        """Draw ASCII art. Returns the row after the art."""
        if not self._current_ascii_art:
            return 0

        lines = self._current_ascii_art.split("\n")
        max_lines = self._layout.art_height
        art_attr = curses.color_pair(1)

        for i, line in enumerate(lines[:max_lines]):
            self._addstr_safe(i, 0, line, art_attr)

        return min(len(lines), max_lines)

    def _draw_messages(self, start_row: int) -> None:
        """Draw message history in the content area."""
        content_height = self._layout.input_row - 1 - start_row
        width = self._layout.width

        # Collect all lines to display
        all_lines: list[tuple[str, int]] = []
        for message, style in self._message_history:
            attr = self._style_to_attr(style)
            wrapped = self._wrap_text(message, width)
            for line in wrapped:
                all_lines.append((line, attr))

        # Display the most recent lines that fit
        visible_lines = all_lines[-content_height:] if all_lines else []

        for i, (line, attr) in enumerate(visible_lines):
            self._addstr_safe(start_row + i, 0, line, attr)

    def _style_to_attr(self, style: str) -> int:
        """Convert style name to curses attribute."""
        match style:
            case "room":
                return curses.color_pair(5) | curses.A_BOLD
            case "error":
                return curses.color_pair(3)
            case "success":
                return curses.color_pair(2)
            case "title":
                return curses.color_pair(1) | curses.A_BOLD
            case "help":
                return curses.color_pair(5) | curses.A_DIM
            case _:
                return curses.color_pair(5)

    def _draw_input_area(self) -> None:
        """Draw the input prompt area."""
        prompt = "> "
        self._addstr_safe(
            self._layout.input_row,
            0,
            prompt,
            curses.color_pair(4) | curses.A_BOLD,
        )
        # Position cursor after prompt
        self._stdscr.move(self._layout.input_row, len(prompt))

    def _draw_status_bar(self) -> None:
        """Draw the status bar at the bottom."""
        width = self._layout.width
        room_info = f"Room: {self._current_room_name}" if self._current_room_name else ""
        turn_info = f"Turn: {self._turn_count}"
        status = f" {room_info}  |  {turn_info} "

        # Right-align the status
        padding = width - len(status)
        full_status = " " * padding + status

        self._addstr_safe(
            self._layout.status_row,
            0,
            full_status[:width],
            curses.color_pair(6) | curses.A_REVERSE,
        )

    # Public interface (matching plain.py)

    def print_room(self, text: str, ascii_art: str | None = None) -> None:
        """Print a room description with optional ASCII art."""
        self._current_ascii_art = ascii_art

        # Extract room name from first line if bold markdown
        lines = text.split("\n")
        if lines and lines[0].startswith("**") and lines[0].endswith("**"):
            self._current_room_name = lines[0].strip("*")

        self._message_history.append((text, "room"))
        self.refresh_display()

    def print_message(self, text: str) -> None:
        """Print a normal game message."""
        self._message_history.append((text, "normal"))
        self.refresh_display()

    def print_error(self, text: str) -> None:
        """Print an error message."""
        self._message_history.append((text, "error"))
        self.refresh_display()

    def print_success(self, text: str) -> None:
        """Print a success message."""
        self._message_history.append((text, "success"))
        self.refresh_display()

    def print_prompt(self) -> str:
        """Print the input prompt and get user input."""
        self.refresh_display()
        curses.echo()
        try:
            # Position cursor at input area
            prompt_col = 2  # After "> "
            self._stdscr.move(self._layout.input_row, prompt_col)

            # Get input with a reasonable max length
            max_input = self._layout.width - prompt_col - 1
            input_bytes = self._stdscr.getstr(self._layout.input_row, prompt_col, max_input)
            return input_bytes.decode("utf-8", errors="replace").strip()
        finally:
            curses.noecho()

    def print_title(self, title: str) -> None:
        """Print a game title."""
        # Create a centered title
        border = "=" * len(title)
        self._message_history.append((border, "title"))
        self._message_history.append((title, "title"))
        self._message_history.append((border, "title"))
        self._message_history.append(("", "normal"))
        self.refresh_display()

    def print_help(self, text: str) -> None:
        """Print help text."""
        self._message_history.append((text, "help"))
        self.refresh_display()

    def print_debug(self, data: dict[str, object] | str) -> None:
        """Print debug information."""
        if isinstance(data, dict):
            import json

            debug_text = json.dumps(data, indent=2, default=str)
        else:
            debug_text = str(data)

        self._message_history.append(("--- DEBUG ---", "help"))
        self._message_history.append((debug_text, "help"))
        self._message_history.append(("-------------", "help"))
        self.refresh_display()

    def print_game_over(self, won: bool, message: str) -> None:
        """Print game over message."""
        style = "success" if won else "error"
        self._message_history.append(("", "normal"))
        self._message_history.append(("=" * 40, style))
        self._message_history.append(("GAME OVER", style))
        self._message_history.append(("=" * 40, style))
        self._message_history.append((message, style))
        self.refresh_display()

        # Wait for user to acknowledge
        self._addstr_safe(
            self._layout.input_row,
            0,
            "Press any key to exit...",
            curses.color_pair(4),
        )
        self._stdscr.refresh()
        self._stdscr.getch()

    def clear_screen(self) -> None:
        """Clear the console and message history."""
        self._message_history.clear()
        self._current_ascii_art = None
        self._stdscr.clear()
        self.refresh_display()

    def set_turn_count(self, turns: int) -> None:
        """Update the turn count in the status bar."""
        self._turn_count = turns


# Module-level instance for use in curses.wrapper context
_current_ui: CursesUI | None = None


def init_curses_ui(stdscr: "CursesWindow") -> CursesUI:
    """Initialize and return a CursesUI instance."""
    global _current_ui
    _current_ui = CursesUI(stdscr)
    return _current_ui


def get_curses_ui() -> CursesUI | None:
    """Get the current CursesUI instance."""
    return _current_ui
