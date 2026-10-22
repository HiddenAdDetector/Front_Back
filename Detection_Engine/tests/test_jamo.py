from detector.jamo import is_decomposed_jamo, recompose_compat_jamo


def test_recomposes_contest_example() -> None:
    text = "ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ"

    assert is_decomposed_jamo(text)
    assert recompose_compat_jamo(text) == "카지노 보너스"


def test_recomposes_final_consonant() -> None:
    assert recompose_compat_jamo("ㅁㅓㄱㅌㅟㄱㅓㅁㅈㅡㅇ") == "먹튀검증"


def test_does_not_classify_casual_jamo_as_obfuscation() -> None:
    assert not is_decomposed_jamo("오늘도 ㅋㅋ 감사합니다")
    assert not is_decomposed_jamo("모음 ㅏ 설명")


def test_preserves_non_jamo_text() -> None:
    assert recompose_compat_jamo("일반 공지 2026") == "일반 공지 2026"
