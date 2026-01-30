"""
game_parser.py

PURPOSE: A parser that supports game-defined custom verbs.
DEPENDENCIES: parser, game model

ARCHITECTURE NOTES:
GameParser wraps the standard parser and adds support for custom verbs
defined in the game's JSON. This allows adventure creators to define
verbs like PRAY, BRIBE, DANCE without modifying Python code.

Custom verbs are routed to a generic handler that searches for matching
actions on objects in the current room.
"""

from dataclasses import dataclass

from text_adventure.models.command import (
    PREPOSITION_WORDS,
    VERB_ALIASES,
    Command,
    Preposition,
    Verb,
)
from text_adventure.models.game import Game
from text_adventure.parser.lexer import tokenize, tokens_to_words
from text_adventure.parser.parser import (
    DIRECTION_WORDS,
    MULTI_WORD_VERBS,
    ParseResult,
)


@dataclass
class CustomVerbInfo:
    """Information about a custom verb from the game definition."""

    name: str
    requires_object: bool
    requires_indirect: bool
    prepositions: list[str]


class GameParser:
    """
    A parser that supports both built-in and game-defined custom verbs.

    Usage:
        parser = GameParser(game)
        result = parser.parse("pray to altar")
    """

    def __init__(self, game: Game):
        """
        Initialize the parser with game-specific verb definitions.

        Args:
            game: The game definition containing custom verbs.
        """
        self.game = game

        # Build custom verb lookup tables
        self.custom_verbs: dict[str, CustomVerbInfo] = {}
        self.custom_verb_aliases: dict[str, str] = {}  # alias -> canonical name

        for verb_def in game.verbs:
            info = CustomVerbInfo(
                name=verb_def.verb.lower(),
                requires_object=verb_def.requires_object,
                requires_indirect=verb_def.requires_indirect,
                prepositions=verb_def.prepositions,
            )
            self.custom_verbs[verb_def.verb.lower()] = info

            # Register aliases
            for alias in verb_def.aliases:
                self.custom_verb_aliases[alias.lower()] = verb_def.verb.lower()

    def parse(self, text: str) -> ParseResult:
        """
        Parse player input, supporting both built-in and custom verbs.

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

        first_word = words[0]
        remaining = words[1:]

        # Check for multi-word built-in verbs first
        if remaining and (first_word, remaining[0]) in MULTI_WORD_VERBS:
            verb = MULTI_WORD_VERBS[(first_word, remaining[0])]
            remaining = remaining[1:]
            return self._parse_with_verb(verb, None, remaining, raw_input)

        # Check for built-in verbs
        if first_word in VERB_ALIASES:
            verb = VERB_ALIASES[first_word]
            return self._parse_with_verb(verb, None, remaining, raw_input)

        # Check for direction words
        if first_word in DIRECTION_WORDS:
            direction_verb = DIRECTION_WORDS[first_word]
            return ParseResult.ok(Command(verb=direction_verb, raw_input=raw_input))

        # Check for custom verbs (canonical name)
        if first_word in self.custom_verbs:
            return self._parse_custom_verb(first_word, remaining, raw_input)

        # Check for custom verb aliases
        if first_word in self.custom_verb_aliases:
            canonical = self.custom_verb_aliases[first_word]
            return self._parse_custom_verb(canonical, remaining, raw_input)

        return ParseResult.fail(
            f'I don\'t know the word "{first_word}".',
            raw_input,
        )

    def _parse_with_verb(
        self,
        verb: Verb,
        custom_verb_name: str | None,
        remaining: list[str],
        raw_input: str,
    ) -> ParseResult:
        """Parse remaining words with a known verb."""
        from text_adventure.models.command import (
            VERBS_REQUIRING_OBJECT,
            VERBS_WITH_INDIRECT,
        )

        # Handle GO + direction
        if verb == Verb.GO:
            if not remaining:
                return ParseResult.fail("Go where?", raw_input)
            direction = remaining[0]
            if direction in DIRECTION_WORDS:
                return ParseResult.ok(
                    Command(verb=DIRECTION_WORDS[direction], raw_input=raw_input)
                )
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
            return ParseResult.ok(
                Command(verb=verb, custom_verb=custom_verb_name, raw_input=raw_input)
            )

        # Parse object phrase(s)
        prep_index = -1
        prep: Preposition | None = None

        if verb in VERBS_WITH_INDIRECT:
            for i, word in enumerate(remaining):
                if word in PREPOSITION_WORDS:
                    prep_index = i
                    prep = PREPOSITION_WORDS[word]
                    break

        if prep_index >= 0:
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

            return ParseResult.ok(
                Command(
                    verb=verb,
                    direct_object=" ".join(direct_words),
                    preposition=prep,
                    indirect_object=" ".join(indirect_words),
                    custom_verb=custom_verb_name,
                    raw_input=raw_input,
                )
            )
        else:
            return ParseResult.ok(
                Command(
                    verb=verb,
                    direct_object=" ".join(remaining),
                    custom_verb=custom_verb_name,
                    raw_input=raw_input,
                )
            )

    def _parse_custom_verb(
        self,
        verb_name: str,
        remaining: list[str],
        raw_input: str,
    ) -> ParseResult:
        """Parse a custom verb from the game definition."""
        info = self.custom_verbs[verb_name]

        # Check if verb requires an object
        if info.requires_object and not remaining:
            return ParseResult.fail(
                f"{verb_name.capitalize()} what?",
                raw_input,
            )

        # No remaining words - just the verb
        if not remaining:
            return ParseResult.ok(
                Command(
                    verb=Verb.CUSTOM,
                    custom_verb=verb_name,
                    raw_input=raw_input,
                )
            )

        # Look for prepositions if verb supports indirect objects
        prep_index = -1
        prep: Preposition | None = None

        if info.requires_indirect or info.prepositions:
            valid_preps = (
                set(info.prepositions) if info.prepositions else set(PREPOSITION_WORDS.keys())
            )
            for i, word in enumerate(remaining):
                if word in valid_preps and word in PREPOSITION_WORDS:
                    prep_index = i
                    prep = PREPOSITION_WORDS[word]
                    break

        if prep_index >= 0:
            direct_words = remaining[:prep_index]
            indirect_words = remaining[prep_index + 1 :]

            if not direct_words and info.requires_object:
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

            return ParseResult.ok(
                Command(
                    verb=Verb.CUSTOM,
                    direct_object=" ".join(direct_words) if direct_words else None,
                    preposition=prep,
                    indirect_object=" ".join(indirect_words),
                    custom_verb=verb_name,
                    raw_input=raw_input,
                )
            )
        else:
            return ParseResult.ok(
                Command(
                    verb=Verb.CUSTOM,
                    direct_object=" ".join(remaining) if remaining else None,
                    custom_verb=verb_name,
                    raw_input=raw_input,
                )
            )
