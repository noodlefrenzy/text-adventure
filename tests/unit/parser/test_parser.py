"""
TEST DOC: Parser

WHAT: Tests for command parsing
WHY: Parser must correctly interpret player intent
HOW: Test various command formats and edge cases

CASES:
- Direction commands (NORTH, GO NORTH)
- Simple verb commands (LOOK, INVENTORY)
- Verb + object (TAKE LAMP)
- Verb + object + preposition + object (PUT KEY IN BOX)
- Multi-word verbs (PICK UP, LOOK AT)

EDGE CASES:
- Empty input
- Unknown verbs
- Missing required objects
"""

import pytest

from text_adventure.models.command import Preposition, Verb
from text_adventure.parser.parser import parse


class TestDirectionCommands:
    """Tests for direction/movement commands."""

    @pytest.mark.parametrize(
        "input_text,expected_verb",
        [
            ("north", Verb.NORTH),
            ("n", Verb.NORTH),
            ("south", Verb.SOUTH),
            ("s", Verb.SOUTH),
            ("east", Verb.EAST),
            ("e", Verb.EAST),
            ("west", Verb.WEST),
            ("w", Verb.WEST),
            ("up", Verb.UP),
            ("u", Verb.UP),
            ("down", Verb.DOWN),
            ("d", Verb.DOWN),
            ("in", Verb.IN),
            ("enter", Verb.IN),
            ("out", Verb.OUT),
            ("exit", Verb.OUT),
        ],
    )
    def test_bare_direction(self, input_text: str, expected_verb: Verb):
        """Bare direction words parse correctly."""
        result = parse(input_text)
        assert result.success
        assert result.command is not None
        assert result.command.verb == expected_verb
        assert result.command.direct_object is None

    @pytest.mark.parametrize(
        "input_text,expected_verb",
        [
            ("go north", Verb.NORTH),
            ("go n", Verb.NORTH),
            ("go south", Verb.SOUTH),
            ("walk east", Verb.EAST),
            ("move west", Verb.WEST),
            ("go up", Verb.UP),
            ("go in", Verb.IN),
        ],
    )
    def test_go_direction(self, input_text: str, expected_verb: Verb):
        """GO + direction parses correctly."""
        result = parse(input_text)
        assert result.success
        assert result.command is not None
        assert result.command.verb == expected_verb

    def test_go_without_direction(self):
        """GO without direction produces error."""
        result = parse("go")
        assert not result.success
        assert result.error is not None
        assert "where" in result.error.message.lower()

    def test_go_invalid_direction(self):
        """GO with invalid direction produces error."""
        result = parse("go sideways")
        assert not result.success
        assert "sideways" in result.error.message.lower()


class TestSimpleVerbs:
    """Tests for verbs without required objects."""

    def test_look(self):
        """LOOK command parses correctly."""
        result = parse("look")
        assert result.success
        assert result.command.verb == Verb.LOOK
        assert result.command.direct_object is None

    def test_look_alias_l(self):
        """L is alias for LOOK."""
        result = parse("l")
        assert result.success
        assert result.command.verb == Verb.LOOK

    def test_inventory(self):
        """INVENTORY parses correctly."""
        result = parse("inventory")
        assert result.success
        assert result.command.verb == Verb.INVENTORY

    def test_inventory_aliases(self):
        """I and INV are aliases for INVENTORY."""
        for alias in ["i", "inv"]:
            result = parse(alias)
            assert result.success
            assert result.command.verb == Verb.INVENTORY

    def test_quit(self):
        """QUIT parses correctly."""
        result = parse("quit")
        assert result.success
        assert result.command.verb == Verb.QUIT

    def test_help(self):
        """HELP parses correctly."""
        result = parse("help")
        assert result.success
        assert result.command.verb == Verb.HELP


class TestVerbWithObject:
    """Tests for verb + direct object commands."""

    def test_take_object(self):
        """TAKE + object parses correctly."""
        result = parse("take lamp")
        assert result.success
        assert result.command.verb == Verb.TAKE
        assert result.command.direct_object == "lamp"

    def test_take_aliases(self):
        """GET and GRAB are aliases for TAKE."""
        for alias in ["get", "grab"]:
            result = parse(f"{alias} lamp")
            assert result.success
            assert result.command.verb == Verb.TAKE
            assert result.command.direct_object == "lamp"

    def test_drop_object(self):
        """DROP + object parses correctly."""
        result = parse("drop sword")
        assert result.success
        assert result.command.verb == Verb.DROP
        assert result.command.direct_object == "sword"

    def test_examine_object(self):
        """EXAMINE + object parses correctly."""
        result = parse("examine painting")
        assert result.success
        assert result.command.verb == Verb.EXAMINE
        assert result.command.direct_object == "painting"

    def test_examine_alias_x(self):
        """X is alias for EXAMINE."""
        result = parse("x sword")
        assert result.success
        assert result.command.verb == Verb.EXAMINE
        assert result.command.direct_object == "sword"

    def test_open_object(self):
        """OPEN + object parses correctly."""
        result = parse("open door")
        assert result.success
        assert result.command.verb == Verb.OPEN
        assert result.command.direct_object == "door"

    def test_close_object(self):
        """CLOSE + object parses correctly."""
        result = parse("close chest")
        assert result.success
        assert result.command.verb == Verb.CLOSE

    def test_read_object(self):
        """READ + object parses correctly."""
        result = parse("read book")
        assert result.success
        assert result.command.verb == Verb.READ
        assert result.command.direct_object == "book"

    def test_take_without_object(self):
        """TAKE without object produces error."""
        result = parse("take")
        assert not result.success
        assert "what" in result.error.message.lower()

    def test_examine_without_object(self):
        """EXAMINE without object produces error."""
        result = parse("examine")
        assert not result.success
        assert "what" in result.error.message.lower()


class TestMultiWordObjects:
    """Tests for commands with multi-word object references."""

    def test_adjective_noun(self):
        """Adjective + noun as object."""
        result = parse("take brass lamp")
        assert result.success
        assert result.command.direct_object == "brass lamp"

    def test_multiple_adjectives(self):
        """Multiple adjectives before noun."""
        result = parse("examine small brass key")
        assert result.success
        assert result.command.direct_object == "small brass key"

    def test_articles_stripped(self):
        """Articles are stripped from object reference."""
        result = parse("take the brass key")
        assert result.success
        assert result.command.direct_object == "brass key"


class TestMultiWordVerbs:
    """Tests for multi-word verb phrases."""

    def test_pick_up(self):
        """PICK UP becomes TAKE."""
        result = parse("pick up lamp")
        assert result.success
        assert result.command.verb == Verb.TAKE
        assert result.command.direct_object == "lamp"

    def test_look_at(self):
        """LOOK AT becomes EXAMINE."""
        result = parse("look at painting")
        assert result.success
        assert result.command.verb == Verb.EXAMINE
        assert result.command.direct_object == "painting"

    def test_put_down(self):
        """PUT DOWN becomes DROP."""
        result = parse("put down sword")
        assert result.success
        assert result.command.verb == Verb.DROP
        assert result.command.direct_object == "sword"


class TestVerbWithPreposition:
    """Tests for verb + object + preposition + object commands."""

    def test_put_in(self):
        """PUT X IN Y parses correctly."""
        result = parse("put key in box")
        assert result.success
        assert result.command.verb == Verb.PUT
        assert result.command.direct_object == "key"
        assert result.command.preposition == Preposition.IN
        assert result.command.indirect_object == "box"

    def test_put_on(self):
        """PUT X ON Y parses correctly."""
        result = parse("put book on table")
        assert result.success
        assert result.command.verb == Verb.PUT
        assert result.command.direct_object == "book"
        assert result.command.preposition == Preposition.ON
        assert result.command.indirect_object == "table"

    def test_unlock_with(self):
        """UNLOCK X WITH Y parses correctly."""
        result = parse("unlock door with key")
        assert result.success
        assert result.command.verb == Verb.UNLOCK
        assert result.command.direct_object == "door"
        assert result.command.preposition == Preposition.WITH
        assert result.command.indirect_object == "key"

    def test_give_to(self):
        """GIVE X TO Y parses correctly."""
        result = parse("give coin to merchant")
        assert result.success
        assert result.command.verb == Verb.GIVE
        assert result.command.direct_object == "coin"
        assert result.command.preposition == Preposition.TO
        assert result.command.indirect_object == "merchant"

    def test_multiword_objects_with_preposition(self):
        """Multi-word objects work with prepositions."""
        result = parse("put brass key in wooden box")
        assert result.success
        assert result.command.direct_object == "brass key"
        assert result.command.indirect_object == "wooden box"

    def test_preposition_variants(self):
        """Preposition variants (into, onto) work."""
        result = parse("put key into box")
        assert result.success
        assert result.command.preposition == Preposition.IN

        result = parse("put book onto table")
        assert result.success
        assert result.command.preposition == Preposition.ON


class TestErrorHandling:
    """Tests for error handling."""

    def test_empty_input(self):
        """Empty input produces error."""
        result = parse("")
        assert not result.success
        assert "pardon" in result.error.message.lower()

    def test_whitespace_only(self):
        """Whitespace-only input produces error."""
        result = parse("   ")
        assert not result.success

    def test_unknown_verb(self):
        """Unknown verb produces error."""
        result = parse("flurble lamp")
        assert not result.success
        assert "flurble" in result.error.message.lower()

    def test_error_preserves_raw_input(self):
        """Errors preserve the raw input."""
        result = parse("xyzzy")
        assert not result.success
        assert result.error.raw_input == "xyzzy"


class TestCaseSensitivity:
    """Tests for case handling."""

    def test_uppercase_verb(self):
        """Uppercase verbs are recognized."""
        result = parse("TAKE LAMP")
        assert result.success
        assert result.command.verb == Verb.TAKE

    def test_mixed_case(self):
        """Mixed case is handled."""
        result = parse("TaKe LaMp")
        assert result.success
        assert result.command.verb == Verb.TAKE

    def test_object_preserved_lowercase(self):
        """Object references are lowercased."""
        result = parse("TAKE BRASS KEY")
        assert result.success
        assert result.command.direct_object == "brass key"
