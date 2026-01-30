"""
TEST DOC: Lexer

WHAT: Tests for input tokenization
WHY: Correct tokenization is essential for parsing
HOW: Test various input formats and edge cases

CASES:
- Simple word tokenization
- Article stripping
- Conjunction handling
- Punctuation handling

EDGE CASES:
- Empty input
- Only articles
- Multiple conjunctions
"""

from text_adventure.parser.lexer import (
    TokenType,
    split_on_conjunction,
    tokenize,
    tokens_to_words,
)


class TestTokenize:
    """Tests for the tokenize function."""

    def test_simple_words(self):
        """Simple words are tokenized correctly."""
        tokens = tokenize("take lamp")
        assert len(tokens) == 2
        assert tokens[0].value == "take"
        assert tokens[1].value == "lamp"

    def test_lowercasing(self):
        """Input is lowercased."""
        tokens = tokenize("TAKE LAMP")
        assert tokens[0].value == "take"
        assert tokens[1].value == "lamp"

    def test_articles_stripped(self):
        """Articles (a, an, the) are removed."""
        tokens = tokenize("take the lamp")
        assert len(tokens) == 2
        assert tokens[0].value == "take"
        assert tokens[1].value == "lamp"

        tokens = tokenize("get a key")
        assert len(tokens) == 2
        assert tokens[0].value == "get"
        assert tokens[1].value == "key"

        tokens = tokenize("examine an apple")
        assert len(tokens) == 2
        assert tokens[0].value == "examine"
        assert tokens[1].value == "apple"

    def test_conjunction_and(self):
        """'and' becomes an AND token."""
        tokens = tokenize("take lamp and key")
        assert len(tokens) == 4
        assert tokens[0].value == "take"
        assert tokens[1].value == "lamp"
        assert tokens[2].type == TokenType.AND
        assert tokens[3].value == "key"

    def test_conjunction_ampersand(self):
        """'&' becomes an AND token."""
        tokens = tokenize("lamp & key")
        assert len(tokens) == 3
        assert tokens[1].type == TokenType.AND

    def test_comma(self):
        """Commas become COMMA tokens."""
        tokens = tokenize("take lamp, key")
        assert len(tokens) == 4
        assert tokens[2].type == TokenType.COMMA

    def test_period_ignored(self):
        """Periods at end of command are ignored."""
        tokens = tokenize("take lamp.")
        assert len(tokens) == 2
        assert tokens[1].value == "lamp"

    def test_empty_input(self):
        """Empty input returns empty list."""
        assert tokenize("") == []
        assert tokenize("   ") == []

    def test_only_articles(self):
        """Input with only articles returns empty list."""
        assert tokenize("the a an") == []

    def test_contractions_expanded(self):
        """Contractions are expanded."""
        tokens = tokenize("don't do that")
        words = tokens_to_words(tokens)
        assert "do" in words
        assert "not" in words

    def test_preserves_original(self):
        """Tokens preserve original form."""
        tokens = tokenize("THE LAMP")
        # Value is lowercased, original preserves case
        assert tokens[0].value == "lamp"
        assert tokens[0].original == "lamp"  # After lowercasing


class TestTokensToWords:
    """Tests for tokens_to_words helper."""

    def test_extracts_words(self):
        """Only word tokens are extracted."""
        tokens = tokenize("take lamp and key")
        words = tokens_to_words(tokens)
        assert words == ["take", "lamp", "key"]

    def test_empty_tokens(self):
        """Empty token list returns empty word list."""
        assert tokens_to_words([]) == []


class TestSplitOnConjunction:
    """Tests for split_on_conjunction."""

    def test_split_on_and(self):
        """Splits on AND tokens."""
        tokens = tokenize("lamp and key")
        segments = split_on_conjunction(tokens)
        assert len(segments) == 2
        assert tokens_to_words(segments[0]) == ["lamp"]
        assert tokens_to_words(segments[1]) == ["key"]

    def test_split_on_comma(self):
        """Splits on COMMA tokens."""
        tokens = tokenize("lamp, key, sword")
        segments = split_on_conjunction(tokens)
        assert len(segments) == 3

    def test_no_conjunction(self):
        """No conjunction returns single segment."""
        tokens = tokenize("brass lamp")
        segments = split_on_conjunction(tokens)
        assert len(segments) == 1
        assert tokens_to_words(segments[0]) == ["brass", "lamp"]

    def test_empty_segments_removed(self):
        """Empty segments from consecutive conjunctions are removed."""
        tokens = tokenize("lamp and and key")
        segments = split_on_conjunction(tokens)
        assert len(segments) == 2

    def test_empty_input(self):
        """Empty input returns empty list."""
        assert split_on_conjunction([]) == []
