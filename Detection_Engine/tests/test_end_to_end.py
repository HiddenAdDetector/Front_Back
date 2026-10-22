import json
from datetime import datetime
from pathlib import Path

from detector.engine import detect
from detector.models import Element
from detector.result_writer import write_result


def test_sample_elements_can_produce_result_json_without_browser(tmp_path) -> None:
    sample_path = Path(__file__).parents[1] / "samples" / "elements.json"
    with sample_path.open("r", encoding="utf-8") as stream:
        elements = [Element(**item) for item in json.load(stream)]

    verdicts = detect(elements)
    result_path = write_result(
        entry_url="https://www.example.go.kr/",
        started_at=datetime(2026, 10, 21, 10, 0),
        finished_at=datetime(2026, 10, 21, 10, 0, 2),
        verdicts=verdicts,
        out_dir=tmp_path,
        tool_version="0.1.0",
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert [finding["id"] for finding in payload["findings"]] == ["f_001", "f_002"]
    assert [finding["technique"] for finding in payload["findings"]] == ["JAMO", "HOMOGLYPH"]
    assert payload["findings"][0]["evidence_text"] == "ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ 코드 LUCKY7"
