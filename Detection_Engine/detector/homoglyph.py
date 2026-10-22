"""Unicode normalization and conservative homoglyph restoration."""

from __future__ import annotations

import unicodedata

# Characters are mapped to the Latin glyph they commonly imitate in spam.
# NFKC already handles full-width Latin letters, digits, punctuation and percent.
HOMOGLYPH_MAP: dict[int, str] = str.maketrans(
    {
        # Cyrillic
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "Х": "X",
        "а": "a",
        "е": "e",
        "к": "k",
        "м": "m",
        "о": "o",
        "р": "p",
        "с": "c",
        "т": "t",
        "х": "x",
        "у": "y",
        # Common numeric/symbol substitutions
        "ⓐ": "a",
        "ⓑ": "b",
        "ⓒ": "c",
        "ⓔ": "e",
        "ⓘ": "i",
        "ⓛ": "l",
        "ⓞ": "o",
        "ⓢ": "s",
        "ⓣ": "t",
        "ⓧ": "x",
        "ꓲ": "I",
        "ꓳ": "O",
        "ꓢ": "S",
        "ꓔ": "T",
    }
)


def normalize_homoglyphs(text: str) -> str:
    """Apply compatibility normalization and the explicit lookalike map."""

    # Applying NFKC to a whole compatibility-jamo run can compose it into a
    # Hangul syllable. Preserve those code points so JAMO remains attributable
    # to the dedicated reconstruction rule rather than HOMOGLYPH.
    normalized = "".join(
        character
        if "ㄱ" <= character <= "ㅣ"
        else unicodedata.normalize("NFKC", character)
        for character in text
    )
    return normalized.translate(HOMOGLYPH_MAP)


def has_homoglyph_change(text: str) -> bool:
    """Return whether homoglyph normalization changes the original text."""

    return normalize_homoglyphs(text) != text
