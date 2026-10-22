from dataclasses import asdict

import pytest

from detector.models import Element, Verdict


def test_element_keeps_crawler_payload() -> None:
    element = Element(
        url="https://example.go.kr/page",
        location="main > p.notice",
        frame_path=["https://example.go.kr/frame"],
        text="공지",
        context="본문",
        style={"opacity": "1", "fontSize": "16px"},
        bbox={"x": 1, "y": 2, "width": 30, "height": 10},
    )

    assert asdict(element)["frame_path"] == ["https://example.go.kr/frame"]
    assert element.style["opacity"] == "1"


def test_verdict_restricts_decision_source_for_type_checkers() -> None:
    verdict = Verdict(
        url="https://example.go.kr/page",
        location="main > p.notice",
        frame_path=[],
        is_violation=False,
        techniques=[],
        original_text="일반 공지",
        normalized_text="일반 공지",
        reason="탐지된 우회 기법 없음",
        decision_source="rule",
    )

    assert verdict.decision_source == "rule"


def test_required_fields_have_no_implicit_defaults() -> None:
    with pytest.raises(TypeError):
        Element(url="https://example.go.kr")  # type: ignore[call-arg]
