import pytest

from detector.engine import detect
from detector.hidden import is_offscreen, is_transparent
from detector.models import Element


def _element(
    text: str = "카지노 첫충",
    *,
    style: dict[str, object] | None = None,
    bbox: dict[str, object] | None = None,
    location: str = "main > span.ad",
    context: str = "",
) -> Element:
    return Element(
        url="https://example.go.kr/page",
        location=location,
        frame_path=[],
        text=text,
        context=context,
        style={} if style is None else style,
        bbox={} if bbox is None else bbox,
    )


@pytest.mark.parametrize(
    "style",
    [
        {"opacity": "0"},
        {"opacity": "1", "ancestorOpacity": "0.01"},
        {"color": "transparent"},
        {"color": "rgba(20, 30, 40, 0)"},
        {"color": "rgb(120, 120, 120)", "backgroundColor": "rgb(120, 120, 120)"},
        {"color": "rgb(120, 120, 120)", "backgroundColor": "rgb(121, 121, 121)"},
    ],
)
def test_transparent_rules_require_illegal_text_in_engine(style: dict[str, object]) -> None:
    hidden = _element(style=style)
    ordinary = _element("민원 안내", style=style)

    assert is_transparent(hidden)
    assert detect([hidden])[0].techniques == ["TRANSPARENT"]
    assert not detect([ordinary])[0].is_violation


def test_transparent_background_does_not_enable_color_comparison() -> None:
    element = _element(
        style={"color": "rgb(0, 0, 0)", "backgroundColor": "rgba(0, 0, 0, 0)"}
    )

    assert not is_transparent(element)


@pytest.mark.parametrize(
    ("style", "bbox"),
    [
        ({"fontSize": "1px"}, {}),
        ({"position": "absolute", "left": "-9999px"}, {}),
        ({"position": "fixed", "top": "-1000px"}, {}),
        ({"display": "none"}, {}),
        ({"visibility": "hidden"}, {}),
        ({"clip": "rect(0px, 0px, 0px, 0px)"}, {}),
        ({"clipPath": "inset(50%)"}, {}),
        ({"clipPath": "polygon(0 0, 0 0, 0 0)"}, {}),
        ({"overflow": "hidden", "width": "1px", "height": "1px"}, {}),
        ({"textIndent": "-1000px"}, {}),
        ({}, {"x": -2000, "y": 10, "width": 20, "height": 20}),
    ],
)
def test_offscreen_rules(style: dict[str, object], bbox: dict[str, object]) -> None:
    element = _element(style=style, bbox=bbox)

    assert is_offscreen(element)
    assert detect([element])[0].techniques == ["OFFSCREEN"]


def test_blank_text_and_missing_style_keys_are_safe() -> None:
    blank = _element("  \n", style={}, bbox={})
    nonblank = _element(style={}, bbox={})

    assert not is_transparent(blank)
    assert not is_offscreen(blank)
    assert not detect([blank])[0].is_violation
    assert not is_transparent(nonblank)
    assert not is_offscreen(nonblank)


def test_both_hidden_techniques_and_jamo_are_preserved() -> None:
    element = _element(
        "ㅋㅏㅈㅣㄴㅗ",
        style={"opacity": "0", "display": "none"},
    )

    assert detect([element])[0].techniques == ["JAMO", "TRANSPARENT", "OFFSCREEN"]


def test_accessibility_class_is_safe_without_keyword_but_keyword_wins() -> None:
    ordinary = _element(
        "본문 바로가기",
        style={"display": "none"},
        location="a.skip-link",
    )
    illegal = _element(
        "카지노 첫충",
        style={"display": "none"},
        location="span.visually-hidden",
    )

    assert not detect([ordinary])[0].is_violation
    assert detect([illegal])[0].techniques == ["OFFSCREEN"]


def test_prevention_context_suppresses_hidden_and_obfuscated_findings() -> None:
    element = _element(
        "ㅋㅏㅈㅣㄴㅗ 예방 및 신고 안내 상담센터 1336",
        style={"opacity": "0", "display": "none"},
        context="불법 도박 근절 캠페인",
    )

    verdict = detect([element])[0]

    assert not verdict.is_violation
    assert verdict.techniques == []
    assert "안내 맥락 제외" in verdict.reason


def test_transparent_and_offscreen_can_overlap() -> None:
    verdict = detect(
        [_element(style={"color": "transparent", "position": "absolute", "left": "-9999px"})]
    )[0]

    assert verdict.techniques == ["TRANSPARENT", "OFFSCREEN"]
