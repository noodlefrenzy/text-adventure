"""
lexer.py

PURPOSE: Tokenize player input for the parser.
DEPENDENCIES: None (pure Python)

ARCHITECTURE NOTES:
The lexer converts raw input strings into a list of normalized tokens.
It handles:
- Lowercasing
- Stripping articles (a, an, the)
- Splitting on whitespace
- Handling punctuation
"""

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Types of tokens produced by the lexer."""

    WORD = auto()  # Regular word
    COMMA = auto()  # Separator between multiple objects
    AND = auto()  # Conjunction
    PERIOD = auto()  # End of command (ignored)


@dataclass(frozen=True)
class Token:
    """A single token from lexer output."""

    type: TokenType
    value: str
    original: str  # Original form before normalization


# Articles to strip from input
ARTICLES = frozenset({"a", "an", "the"})

# Words that get special token types
CONJUNCTIONS = frozenset({"and", "&"})

# Contractions and their expansions
CONTRACTIONS = {
    "don't": "do not",
    "doesn't": "does not",
    "can't": "cannot",
    "won't": "will not",
    "i'm": "i am",
    "it's": "it is",
    "that's": "that is",
    "what's": "what is",
    "where's": "where is",
}


def tokenize(text: str) -> list[Token]:
    """
    Convert input text into a list of tokens.

    Handles:
    - Lowercasing
    - Punctuation splitting
    - Article removal
    - Contraction expansion
    - Conjunction recognition

    Args:
        text: Raw player input

    Returns:
        List of Token objects
    """
    # Normalize case
    text = text.lower().strip()

    if not text:
        return []

    # Expand contractions
    for contraction, expansion in CONTRACTIONS.items():
        text = text.replace(contraction, expansion)

    # Split on whitespace and punctuation, keeping punctuation as tokens
    # This regex splits while keeping delimiters
    parts = re.split(r"(\s+|[,.])", text)

    tokens: list[Token] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        original = part

        # Handle punctuation
        if part == ",":
            tokens.append(Token(TokenType.COMMA, ",", original))
            continue
        if part == ".":
            # Period at end of command - skip it
            continue

        # Handle conjunctions
        if part in CONJUNCTIONS:
            tokens.append(Token(TokenType.AND, "and", original))
            continue

        # Skip articles
        if part in ARTICLES:
            continue

        # Regular word
        tokens.append(Token(TokenType.WORD, part, original))

    return tokens


def tokens_to_words(tokens: list[Token]) -> list[str]:
    """
    Extract just the word values from a token list.

    Useful for simple parsing that doesn't need token types.

    Args:
        tokens: List of tokens

    Returns:
        List of word strings (only WORD tokens)
    """
    return [t.value for t in tokens if t.type == TokenType.WORD]


def split_on_conjunction(tokens: list[Token]) -> list[list[Token]]:
    """
    Split a token list on AND/COMMA conjunctions.

    Used for handling commands like "GET LAMP AND KEY" or "DROP SWORD, SHIELD".

    Args:
        tokens: List of tokens

    Returns:
        List of token lists, one for each segment
    """
    if not tokens:
        return []

    segments: list[list[Token]] = [[]]

    for token in tokens:
        if token.type in (TokenType.AND, TokenType.COMMA):
            if segments[-1]:  # Don't create empty segments
                segments.append([])
        else:
            segments[-1].append(token)

    # Remove any trailing empty segments
    return [s for s in segments if s]
