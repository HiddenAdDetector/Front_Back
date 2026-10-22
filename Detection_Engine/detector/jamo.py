"""Detection and reconstruction of Hangul compatibility-jamo obfuscation."""

from __future__ import annotations

import re

CHOSEONG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNGSEONG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONGSEONG = "\0ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

VOWEL_COMBINATIONS = {
    ("ㅗ", "ㅏ"): "ㅘ",
    ("ㅗ", "ㅐ"): "ㅙ",
    ("ㅗ", "ㅣ"): "ㅚ",
    ("ㅜ", "ㅓ"): "ㅝ",
    ("ㅜ", "ㅔ"): "ㅞ",
    ("ㅜ", "ㅣ"): "ㅟ",
    ("ㅡ", "ㅣ"): "ㅢ",
}

FINAL_COMBINATIONS = {
    ("ㄱ", "ㅅ"): "ㄳ",
    ("ㄴ", "ㅈ"): "ㄵ",
    ("ㄴ", "ㅎ"): "ㄶ",
    ("ㄹ", "ㄱ"): "ㄺ",
    ("ㄹ", "ㅁ"): "ㄻ",
    ("ㄹ", "ㅂ"): "ㄼ",
    ("ㄹ", "ㅅ"): "ㄽ",
    ("ㄹ", "ㅌ"): "ㄾ",
    ("ㄹ", "ㅍ"): "ㄿ",
    ("ㄹ", "ㅎ"): "ㅀ",
    ("ㅂ", "ㅅ"): "ㅄ",
}

_COMPAT_JAMO_RE = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]")
_COMPOSABLE_RUN_RE = re.compile(
    rf"(?:[{re.escape(CHOSEONG)}][{re.escape(JUNGSEONG)}]){{2,}}"
)


def is_decomposed_jamo(text: str) -> bool:
    """Return whether *text* contains a substantial composable jamo run."""

    compact = "".join(character for character in text if not character.isspace())
    if not compact:
        return False
    jamo_count = len(_COMPAT_JAMO_RE.findall(compact))
    return jamo_count / len(compact) >= 0.4 and bool(_COMPOSABLE_RUN_RE.search(compact))


def recompose_compat_jamo(text: str) -> str:
    """Compose compatibility jamo into modern Hangul syllables when possible."""

    result: list[str] = []
    index = 0
    while index < len(text):
        onset = text[index]
        if onset not in CHOSEONG or index + 1 >= len(text) or text[index + 1] not in JUNGSEONG:
            result.append(onset)
            index += 1
            continue

        vowel = text[index + 1]
        cursor = index + 2
        if cursor < len(text) and (vowel, text[cursor]) in VOWEL_COMBINATIONS:
            vowel = VOWEL_COMBINATIONS[(vowel, text[cursor])]
            cursor += 1

        final = "\0"
        if cursor < len(text) and text[cursor] in JONGSEONG[1:]:
            candidate = text[cursor]
            following_is_vowel = cursor + 1 < len(text) and text[cursor + 1] in JUNGSEONG
            if not following_is_vowel:
                final = candidate
                cursor += 1
                if cursor < len(text) and (final, text[cursor]) in FINAL_COMBINATIONS:
                    combined = FINAL_COMBINATIONS[(final, text[cursor])]
                    after_pair_is_vowel = cursor + 1 < len(text) and text[cursor + 1] in JUNGSEONG
                    if not after_pair_is_vowel:
                        final = combined
                        cursor += 1

        codepoint = (
            0xAC00
            + CHOSEONG.index(onset) * 21 * 28
            + JUNGSEONG.index(vowel) * 28
            + JONGSEONG.index(final)
        )
        result.append(chr(codepoint))
        index = cursor

    return "".join(result)
