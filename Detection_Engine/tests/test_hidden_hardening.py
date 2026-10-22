from detector.engine import detect
from detector.hidden import COLLECTOR_STYLE_KEYS, is_offscreen, is_transparent
from detector.keywords import find_ad_lures
from detector.models import Element


def _element(
    text: str,
    *,
    style: dict[str, object] | None = None,
    context: str = "",
) -> Element:
    return Element(
        url="https://example.go.kr/page",
        location="main > span",
        frame_path=[],
        text=text,
        context=context,
        style={} if style is None else style,
        bbox={},
    )


def test_ad_lure_prevents_abuse_of_reporting_exclusion() -> None:
    element = _element(
        "불법 도박 신고 안 걸리는 안전놀이터",
        style={"display": "none"},
    )

    verdict = detect([element])[0]

    assert find_ad_lures(element.text) == ["안 걸리는", "안전놀이터"]
    assert verdict.is_violation
    assert verdict.techniques == ["OFFSCREEN"]


def test_genuine_prevention_context_is_still_excluded() -> None:
    element = _element(
        "카지노 중독 예방 및 불법 도박 신고 안내",
        style={"display": "none"},
        context="도박문제 상담센터 1336",
    )

    verdict = detect([element])[0]

    assert not verdict.is_violation
    assert verdict.techniques == []


def test_effective_background_enables_transparent_parent_contrast() -> None:
    element = _element(
        "카지노 첫충",
        style={
            "color": "rgb(255, 255, 255)",
            "backgroundColor": "rgba(0, 0, 0, 0)",
            "effectiveBackground": "rgb(255, 255, 255)",
        },
    )

    assert is_transparent(element)
    assert detect([element])[0].techniques == ["TRANSPARENT"]


def test_transparent_background_without_effective_background_remains_indeterminate() -> None:
    element = _element(
        "카지노 첫충",
        style={
            "color": "rgb(255, 255, 255)",
            "backgroundColor": "rgba(0, 0, 0, 0)",
        },
    )

    assert not is_transparent(element)


def test_ancestor_display_none_is_offscreen() -> None:
    hidden = _element("카지노 첫충", style={"display": "block", "ancestorDisplayNone": True})
    ordinary = _element("민원 안내", style={"display": "block", "ancestorDisplayNone": "true"})

    assert is_offscreen(hidden)
    assert detect([hidden])[0].techniques == ["OFFSCREEN"]
    assert not detect([ordinary])[0].is_violation


def test_collector_contract_contains_agreed_keys() -> None:
    assert COLLECTOR_STYLE_KEYS == (
        "opacity",
        "ancestorOpacity",
        "color",
        "backgroundColor",
        "effectiveBackground",
        "fontSize",
        "display",
        "ancestorDisplayNone",
        "visibility",
        "position",
        "left",
        "top",
        "clip",
        "clipPath",
        "overflow",
        "textIndent",
        "width",
        "height",
    )
