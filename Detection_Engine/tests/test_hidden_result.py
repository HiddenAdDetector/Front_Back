import json
from datetime import datetime

from detector.engine import detect
from detector.models import Element
from detector.result_writer import write_result


def test_overlapping_hidden_techniques_become_separate_findings(tmp_path) -> None:
    element = Element(
        url="https://example.go.kr/ad",
        location="div.ad > span",
        frame_path=[],
        text="카지노 첫충",
        context="",
        style={"opacity": "0", "display": "none"},
        bbox={},
    )
    verdicts = detect([element])

    result_path = write_result(
        entry_url="https://example.go.kr",
        started_at=datetime(2026, 10, 21, 10, 0),
        finished_at=datetime(2026, 10, 21, 10, 0, 1),
        verdicts=verdicts,
        out_dir=tmp_path,
        tool_version="0.2.0",
    )

    findings = json.loads(result_path.read_text(encoding="utf-8"))["findings"]
    assert [finding["technique"] for finding in findings] == ["TRANSPARENT", "OFFSCREEN"]
    assert findings[0]["url"] == findings[1]["url"]
    assert findings[0]["location"] == findings[1]["location"]
