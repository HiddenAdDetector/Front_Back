import json
from datetime import datetime, timezone

import pytest

from detector.models import Verdict
from detector.result_writer import write_result


def _verdict(**overrides: object) -> Verdict:
    values: dict[str, object] = {
        "url": "https://example.go.kr/view?name=test&id=1024#section",
        "location": "div.notice > span.hidden",
        "frame_path": ["https://example.go.kr/widget/notice"],
        "is_violation": True,
        "techniques": ["JAMO"],
        "original_text": "ㅋㅏㅈㅣㄴㅗ",
        "normalized_text": "카지노",
        "reason": "자모 복원 후 키워드 탐지",
        "decision_source": "rule",
    }
    values.update(overrides)
    return Verdict(**values)  # type: ignore[arg-type]


def test_writes_strict_schema_without_bom_and_expands_techniques(tmp_path) -> None:
    path = write_result(
        "https://example.go.kr/",
        datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 21, 0, 0, 1, 250000, tzinfo=timezone.utc),
        [_verdict(techniques=["JAMO", "HOMOGLYPH"])],
        tmp_path,
        "1.0.0",
    )

    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    assert path.name == "result.json"
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert set(payload) == {"meta", "findings"}
    assert payload["meta"] == {
        "topic": "TOPIC",
        "entry_url": "https://example.go.kr/",
        "started_at": "2026-10-21T09:00:00+09:00",
        "finished_at": "2026-10-21T09:00:01+09:00",
        "elapsed_sec": 1.25,
        "tool_version": "1.0.0",
    }
    assert [item["technique"] for item in payload["findings"]] == ["JAMO", "HOMOGLYPH"]
    assert set(payload["findings"][0]) == {
        "id", "url", "is_violation", "location", "evidence_text", "technique"
    }
    assert payload["findings"][0]["location"] == (
        'iframe[src="https://example.go.kr/widget/notice"] >>> div.notice > span.hidden'
    )


def test_deduplicates_pdf_equivalent_urls_but_keeps_first_original(tmp_path) -> None:
    first = _verdict()
    duplicate = _verdict(
        url="http://example.go.kr/view/?id=1024&name=test",
        frame_path=["https://example.go.kr/widget/notice"],
    )

    path = write_result(
        "https://example.go.kr",
        datetime(2026, 10, 21, 9),
        datetime(2026, 10, 21, 9, 1),
        [first, duplicate],
        tmp_path,
        "dev",
    )

    findings = json.loads(path.read_text(encoding="utf-8"))["findings"]
    assert len(findings) == 1
    assert findings[0]["url"] == first.url


def test_writes_empty_findings_for_non_violation_partial_result(tmp_path) -> None:
    path = write_result(
        "https://example.go.kr",
        datetime(2026, 10, 21, 9),
        datetime(2026, 10, 21, 9),
        [_verdict(is_violation=False, techniques=[])],
        tmp_path,
        "dev",
    )

    assert json.loads(path.read_text(encoding="utf-8"))["findings"] == []


def test_rejects_nonstandard_technique(tmp_path) -> None:
    with pytest.raises(ValueError, match="Unsupported result technique"):
        write_result(
            "https://example.go.kr",
            datetime(2026, 10, 21, 9),
            datetime(2026, 10, 21, 9),
            [_verdict(techniques=["ETC"])],
            tmp_path,
            "dev",
        )


@pytest.mark.parametrize(
    "location",
    ["div", "span", 'iframe[src="https://example.go.kr/frame"] >>> div'],
)
def test_omits_ambiguous_bare_tag_locations(tmp_path, location: str) -> None:
    path = write_result(
        "https://example.go.kr",
        datetime(2026, 10, 21, 9),
        datetime(2026, 10, 21, 9, 1),
        [_verdict(location=location, frame_path=[])],
        tmp_path,
        "dev",
    )

    assert json.loads(path.read_text(encoding="utf-8"))["findings"] == []
