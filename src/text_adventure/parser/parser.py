"""
parser.py

PURPOSE: Parse tokenized input into Command objects.
DEPENDENCIES: lexer, command model

ARCHITECTURE NOTES:
The parser implements Infocom-style grammar:
    COMMAND := VERB [DIRECT_OBJ] [PREPOSITION INDIRECT_OBJ]
    DIRECT_OBJ := [ADJECTIVE*] NOUN
    INDIRECT_OBJ := [ADJECTIVE*] NOUN

It does NOT resolve object references to actual game objects - that's
the resolver's job. The parser just extracts the structure.

Special cases:
- Direction commands (NORTH) become Command(verb=NORTH)
- "LOOK AT X" becomes EXAMINE with X as direct object
- "PICK UP X" becomes TAKE with X as direct object
- GO NORTH becomes Command(verb=NORTH)
"""

from dataclasses import dataclass

from text_adventure.models.command import (
    PREPOSITION_WORDS,
    VERB_ALIASES,
    VERBS_REQUIRING_OBJECT,
    VERBS_WITH_INDIRECT,
    Command,
    Preposition,
    Verb,
)
from text_adventure.parser.lexer import tokenize, tokens_to_words


@dataclass
class ParseError:
    """Represents a parsing error with a user-friendly message."""

    message: str
    raw_input: str


@dataclass
class ParseResult:
    """Result of parsing - either a Command or an error."""

    command: Command | None
    error: ParseError | None

    @property
    def success(self) -> bool:
        return self.command is not None

    @classmethod
    def ok(cls, command: Command) -> "ParseResult":
        return cls(command=command, error=None)

    @classmethod
    def fail(cls, message: str, raw_input: str) -> "ParseResult":
        return cls(command=None, error=ParseError(message, raw_input))


# Multi-word verb phrases that need special handling
# Maps (first_word, second_word) -> verb
MULTI_WORD_VERBS: dict[tuple[str, str], Verb] = {
    ("pick", "up"): Verb.TAKE,
    ("put", "down"): Verb.DROP,
    ("look", "at"): Verb.EXAMINE,
    ("look", "in"): Verb.EXAMINE,  # LOOK IN box -> examine box
    ("look", "under"): Verb.EXAMINE,  # LOOK UNDER bed -> examine bed
    ("turn", "on"): Verb.USE,
    ("turn", "off"): Verb.USE,
    ("switch", "on"): Verb.USE,
    ("switch", "off"): Verb.USE,
}

# Direction words for GO command
DIRECTION_WORDS: dict[str, Verb] = {
    "north": Verb.NORTH,
    "n": Verb.NORTH,
    "south": Verb.SOUTH,
    "s": Verb.SOUTH,
    "east": Verb.EAST,
    "e": Verb.EAST,
    "west": Verb.WEST,
    "w": Verb.WEST,
    "up": Verb.UP,
    "u": Verb.UP,
    "down": Verb.DOWN,
    "d": Verb.DOWN,
    "in": Verb.IN,
    "enter": Verb.IN,
    "inside": Verb.IN,
    "out": Verb.OUT,
    "outside": Verb.OUT,
    "exit": Verb.OUT,
}


def parse(text: str) -> ParseResult:
    """
    Parse player input into a Command.

    Args:
        text: Raw player input string

    Returns:
        ParseResult containing either a Command or an error
    """
    raw_input = text.strip()

    if not raw_input:
        return ParseResult.fail("I beg your pardon?", raw_input)

    tokens = tokenize(raw_input)

    if not tokens:
        return ParseResult.fail("I beg your pardon?", raw_input)

    words = tokens_to_words(tokens)

    if not words:
        return ParseResult.fail("I don't understand that.", raw_input)

    # Get the first word - should be a verb or direction
    first_word = words[0]
    remaining = words[1:]

    # Check for multi-word verbs first
    if remaining and (first_word, remaining[0]) in MULTI_WORD_VERBS:
        verb = MULTI_WORD_VERBS[(first_word, remaining[0])]
        remaining = remaining[1:]
    elif first_word in VERB_ALIASES:
        verb = VERB_ALIASES[first_word]
    elif first_word in DIRECTION_WORDS:
        # Bare direction command (NORTH, S, etc.)
        direction_verb = DIRECTION_WORDS[first_word]
        return ParseResult.ok(Command(verb=direction_verb, raw_input=raw_input))
    else:
        return ParseResult.fail(
            f'I don\'t know the word "{first_word}".',
            raw_input,
        )

    # Handle GO + direction
    if verb == Verb.GO:
        if not remaining:
            return ParseResult.fail("Go where?", raw_input)
        direction = remaining[0]
        if direction in DIRECTION_WORDS:
            return ParseResult.ok(Command(verb=DIRECTION_WORDS[direction], raw_input=raw_input))
        return ParseResult.fail(
            f'I don\'t know how to go "{direction}".',
            raw_input,
        )

    # Handle LOOK (without object = describe room)
    if verb == Verb.LOOK and not remaining:
        return ParseResult.ok(Command(verb=Verb.LOOK, raw_input=raw_input))

    # Check if verb requires an object
    if verb in VERBS_REQUIRING_OBJECT and not remaining:
        verb_name = verb.name.lower()
        return ParseResult.fail(
            f"{verb_name.capitalize()} what?",
            raw_input,
        )

    # No remaining words - just the verb
    if not remaining:
        return ParseResult.ok(Command(verb=verb, raw_input=raw_input))

    # Parse object phrase(s)
    # Look for a preposition to split direct from indirect object
    prep_index = -1
    prep: Preposition | None = None

    if verb in VERBS_WITH_INDIRECT:
        for i, word in enumerate(remaining):
            if word in PREPOSITION_WORDS:
                prep_index = i
                prep = PREPOSITION_WORDS[word]
                break

    if prep_index >= 0:
        # Have a preposition - split into direct and indirect objects
        direct_words = remaining[:prep_index]
        indirect_words = remaining[prep_index + 1 :]

        if not direct_words:
            verb_name = verb.name.lower()
            return ParseResult.fail(
                f"{verb_name.capitalize()} what?",
                raw_input,
            )

        if not indirect_words:
            prep_word = [k for k, v in PREPOSITION_WORDS.items() if v == prep][0]
            return ParseResult.fail(
                f"{prep_word.capitalize()} what?",
                raw_input,
            )

        direct_obj = " ".join(direct_words)
        indirect_obj = " ".join(indirect_words)

        return ParseResult.ok(
            Command(
                verb=verb,
                direct_object=direct_obj,
                preposition=prep,
                indirect_object=indirect_obj,
                raw_input=raw_input,
            )
        )
    else:
        # No preposition - all remaining words are the direct object
        direct_obj = " ".join(remaining)
        return ParseResult.ok(
            Command(
                verb=verb,
                direct_object=direct_obj,
                raw_input=raw_input,
            )
        )
