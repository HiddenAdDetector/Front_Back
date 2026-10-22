import json
from datetime import datetime

from detector import ai_judge
from detector.ai_judge import AiResult, GeminiSettings
from detector.engine import detect
from detector.models import Element
from detector.result_writer import write_result


def _element(
    text: str,
    *,
    style: dict[str, object] | None = None,
    location: str = "main > span",
    context: str = "",
) -> Element:
    return Element(
        url="https://example.go.kr/page",
        location=location,
        frame_path=[],
        text=text,
        context=context,
        style={} if style is None else style,
        bbox={},
    )


def _settings(confidence: float = 0.7) -> GeminiSettings:
    return GeminiSettings("dummy", "test-model", 1, 20, 30, confidence)


def test_ai_promotes_unknown_hidden_text_and_result_schema_stays_strict(monkeypatch, tmp_path) -> None:
    captured: list[ai_judge.AiCandidate] = []

    def fake_judge(candidates, cancel_event=None):
        del cancel_event
        captured.extend(candidates)
        return {
            candidates[0].id: AiResult(candidates[0].id, True, 0.92, "가입을 유도하는 광고 문구")
        }

    monkeypatch.setattr(ai_judge, "judge", fake_judge)
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings())
    verdict = detect([_element("지금 바로 접속", style={"display": "none"})])[0]

    assert len(captured) == 1
    assert verdict.is_violation
    assert verdict.techniques == ["OFFSCREEN"]
    assert verdict.decision_source == "ai"
    assert "가입을 유도" in verdict.reason

    path = write_result(
        "https://example.go.kr",
        datetime(2026, 10, 21, 10),
        datetime(2026, 10, 21, 10, 0, 1),
        [verdict],
        tmp_path,
        "0.3.0",
    )
    finding = json.loads(path.read_text(encoding="utf-8"))["findings"][0]
    assert set(finding) == {"id", "url", "is_violation", "location", "evidence_text", "technique"}


def test_low_confidence_and_negative_ai_results_do_not_promote(monkeypatch) -> None:
    def fake_judge(candidates, cancel_event=None):
        del cancel_event
        return {
            candidates[0].id: AiResult(candidates[0].id, True, 0.69, "낮은 확신"),
            candidates[1].id: AiResult(candidates[1].id, False, 0.99, "광고 아님"),
        }

    monkeypatch.setattr(ai_judge, "judge", fake_judge)
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings(0.7))
    verdicts = detect(
        [
            _element("의심 문구 A", style={"display": "none"}),
            _element("의심 문구 B", style={"opacity": "0"}),
        ]
    )

    assert [verdict.is_violation for verdict in verdicts] == [False, False]
    assert [verdict.decision_source for verdict in verdicts] == ["rule", "rule"]


def test_ai_can_demote_ambiguous_rule_positive_hidden_finding(monkeypatch) -> None:
    captured: list[ai_judge.AiCandidate] = []

    def fake_judge(candidates, cancel_event=None):
        del cancel_event
        captured.extend(candidates)
        return {
            candidates[0].id: AiResult(candidates[0].id, False, 0.96, "정책 안내 문맥")
        }

    monkeypatch.setattr(ai_judge, "judge", fake_judge)
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings())

    verdict = detect([_element("카지노 안내", style={"display": "none"})])[0]

    assert len(captured) == 1
    assert not verdict.is_violation
    assert verdict.techniques == []
    assert verdict.decision_source == "ai"
    assert "재검토 제외" in verdict.reason


def test_obvious_jamo_rule_positive_skips_ai_review(monkeypatch) -> None:
    captured: list[ai_judge.AiCandidate] = []

    def fake_judge(candidates, cancel_event=None):
        del cancel_event
        captured.extend(candidates)
        return {}

    monkeypatch.setattr(ai_judge, "judge", fake_judge)
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings())

    verdict = detect([_element("ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ")])[0]

    assert captured == []
    assert verdict.is_violation
    assert verdict.techniques == ["JAMO"]


def test_prevention_and_accessibility_only_elements_are_not_candidates(monkeypatch) -> None:
    captured: list[ai_judge.AiCandidate] = []

    def fake_judge(candidates, cancel_event=None):
        del cancel_event
        captured.extend(candidates)
        return {}

    monkeypatch.setattr(ai_judge, "judge", fake_judge)
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings())
    verdicts = detect(
        [
            _element("불법 도박 예방 교육", style={"display": "none"}),
            _element("본문 바로가기", style={"display": "none"}, location="a.sr-only"),
        ]
    )

    assert captured == []
    assert not any(verdict.is_violation for verdict in verdicts)


def test_jamo_or_homoglyph_without_dictionary_keyword_becomes_candidate(monkeypatch) -> None:
    captured: list[ai_judge.AiCandidate] = []

    def fake_judge(candidates, cancel_event=None):
        del cancel_event
        captured.extend(candidates)
        return {}

    monkeypatch.setattr(ai_judge, "judge", fake_judge)
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings())
    detect([_element("ㅇㅣㅂㄱㅡㅁ ㅇㅠㄷㅗ"), _element("ｍｅｇａ－ＢＥＴ")])

    assert [candidate.techniques for candidate in captured] == [("JAMO",), ("HOMOGLYPH",)]
    assert captured[0].normalized_text == "입금 유도"


def test_use_ai_false_preserves_rule_only_flow(monkeypatch) -> None:
    monkeypatch.setattr(
        ai_judge,
        "judge",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not call AI")),
    )

    verdict = detect([_element("의심 문구", style={"display": "none"})], use_ai=False)[0]

    assert not verdict.is_violation
    assert verdict.decision_source == "rule"


def test_missing_key_returns_rule_result_without_sdk_call(monkeypatch) -> None:
    monkeypatch.setattr(ai_judge, "load_settings", lambda: GeminiSettings("", "test", 1, 20, 30, 0.7))
    monkeypatch.setattr(
        ai_judge,
        "_create_client",
        lambda _settings: (_ for _ in ()).throw(AssertionError("SDK must not be called")),
    )

    verdict = detect([_element("의심 문구", style={"display": "none"})])[0]

    assert not verdict.is_violation
    assert verdict.decision_source == "rule"


def test_progress_callback_reports_rule_ai_and_done(monkeypatch) -> None:
    events: list[tuple[int, int, str]] = []
    monkeypatch.setattr(ai_judge, "judge", lambda _candidates, cancel_event=None: {})
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings())

    detect(
        [_element("의심 문구", style={"display": "none"})],
        on_progress=lambda done, total, state: events.append((done, total, state)),
    )

    assert [state for _, _, state in events] == ["rule", "ai", "ai", "done"]
