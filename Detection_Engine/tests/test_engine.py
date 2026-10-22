import json
from pathlib import Path

from detector.engine import detect
from detector.models import Element

SAMPLE_PATH = Path(__file__).parents[1] / "samples" / "elements.json"


def _element(text: str) -> Element:
    return Element(
        url="https://example.go.kr/page",
        location="main > p",
        frame_path=[],
        text=text,
        context="",
        style={},
        bbox={},
    )


def test_detects_jamo_and_homoglyph_examples() -> None:
    verdicts = detect(
        [
            _element("ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ"),
            _element("ｍｅｇａ－ＢＥＴ 첫충 30％ 지급"),
        ]
    )

    assert verdicts[0].techniques == ["JAMO"]
    assert verdicts[0].normalized_text == "카지노 보너스"
    assert verdicts[1].techniques == ["HOMOGLYPH"]
    assert verdicts[1].normalized_text == "mega-BET 첫충 30% 지급"
    assert all(verdict.is_violation for verdict in verdicts)


def test_reports_overlapping_obfuscation_as_separate_techniques() -> None:
    verdict = detect([_element("ｍｅｇａ ㅋㅏㅈㅣㄴㅗ")])[0]

    assert verdict.techniques == ["JAMO", "HOMOGLYPH"]


def test_prevention_and_ordinary_notice_are_not_false_positives() -> None:
    verdicts = detect(
        [
            _element("불법 도박 예방 및 신고 안내"),
            _element("민원실 운영시간 변경 안내"),
        ]
    )

    assert [verdict.is_violation for verdict in verdicts] == [False, False]
    assert [verdict.techniques for verdict in verdicts] == [[], []]


def test_browser_free_sample_json() -> None:
    with SAMPLE_PATH.open("r", encoding="utf-8") as stream:
        elements = [Element(**item) for item in json.load(stream)]

    verdicts = detect(elements)

    assert len(verdicts) == 4
    assert [verdict.techniques for verdict in verdicts] == [
        ["JAMO"],
        ["HOMOGLYPH"],
        [],
        [],
    ]
