from detector.homoglyph import has_homoglyph_change, normalize_homoglyphs


def test_nfkc_restores_contest_example() -> None:
    text = "ｍｅｇａ－ＢＥＴ 첫충 30％ 지급"

    assert has_homoglyph_change(text)
    assert normalize_homoglyphs(text) == "mega-BET 첫충 30% 지급"


def test_restores_cyrillic_lookalikes() -> None:
    # The first two and final characters are Cyrillic.
    assert normalize_homoglyphs("саsinо 첫충") == "casino 첫충"


def test_ordinary_text_is_unchanged() -> None:
    text = "2026년 시민 대상 일반 공지"

    assert not has_homoglyph_change(text)
    assert normalize_homoglyphs(text) == text
