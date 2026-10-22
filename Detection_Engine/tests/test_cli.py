from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import detector_cli


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = PROJECT_ROOT / "detector_cli.py"
SAMPLE_PATH = PROJECT_ROOT / "samples" / "b_elements_sample.json"
FINDING_KEYS = {"id", "url", "is_violation", "location", "evidence_text", "technique"}


def _run_cli(*arguments: object, env_extra: dict[str, str] | None = None):
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("GEMINI_"):
            environment.pop(key)
    # Keep a developer's script-adjacent .env from enabling real API calls.
    environment["GEMINI_API_KEY"] = ""
    environment["PYTHONUTF8"] = "1"
    if env_extra:
        environment.update(env_extra)
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *(str(value) for value in arguments)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )


def _stdout_records(completed: subprocess.CompletedProcess[str]) -> list[dict[str, object]]:
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


def test_sample_writes_strict_result_and_final_stdout_record(tmp_path: Path) -> None:
    completed = _run_cli("--input", SAMPLE_PATH, "--out-dir", tmp_path, "--no-ai")

    assert completed.returncode == 0, completed.stderr
    records = _stdout_records(completed)
    assert records[-1]["type"] == "result"
    assert records[-1]["findings"] == 2
    payload = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert set(payload) == {"meta", "findings"}
    assert payload["findings"]
    assert all(set(finding) == FINDING_KEYS for finding in payload["findings"])
    assert payload["meta"]["topic"] == "TOPIC"
    assert payload["meta"]["tool_version"] == "0.5.0"


def test_b_fields_extra_fields_and_string_frame_path_are_accepted(tmp_path: Path) -> None:
    completed = _run_cli("--input", SAMPLE_PATH, "--out-dir", tmp_path, "--no-ai")
    payload = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0
    locations = {finding["location"] for finding in payload["findings"]}
    assert (
        'iframe[src="https://www.example.go.kr/widgets/banner"] >>> '
        "main > section.notice > span.promo"
    ) in locations


def test_prewrapped_iframe_location_is_not_wrapped_twice(tmp_path: Path) -> None:
    location = 'iframe[src="https://example.test/frame"] >>> body > a'
    input_path = tmp_path / "elements.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "url": "https://example.test/",
                    "location": location,
                    "framePath": "https://example.test/frame",
                    "text": "ㅋㅏㅈㅣㄴㅗ",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    completed = _run_cli("--input", input_path, "--out-dir", out_dir, "--no-ai")
    payload = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0
    assert payload["findings"][0]["location"] == location
    assert payload["findings"][0]["location"].count("iframe[src=") == 1


@pytest.mark.parametrize("contents", ["[]", "{broken json"])
def test_empty_or_broken_input_returns_two_and_writes_empty_result(
    tmp_path: Path, contents: str
) -> None:
    input_path = tmp_path / "elements.json"
    input_path.write_text(contents, encoding="utf-8")
    out_dir = tmp_path / "out"

    completed = _run_cli("--input", input_path, "--out-dir", out_dir)
    payload = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))

    assert completed.returncode == 2
    assert payload["findings"] == []
    assert _stdout_records(completed)[-1]["type"] == "result"


def test_bad_element_is_skipped_without_crashing_other_elements(tmp_path: Path) -> None:
    input_path = tmp_path / "elements.json"
    input_path.write_text(
        json.dumps(
            [
                {"url": 123, "location": None, "text": []},
                {
                    "url": "https://example.test/",
                    "location": "body > span",
                    "text": "ㅋㅏㅈㅣㄴㅗ",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    completed = _run_cli("--input", input_path, "--out-dir", out_dir, "--no-ai")
    payload = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))

    assert completed.returncode == 0
    assert "element 1 skipped" in completed.stderr
    assert len(payload["findings"]) == 1


def test_existing_cancel_file_saves_partial_result_and_returns_zero(tmp_path: Path) -> None:
    cancel_path = tmp_path / "cancel.request"
    cancel_path.touch()
    out_dir = tmp_path / "out"

    completed = _run_cli(
        "--input", SAMPLE_PATH, "--out-dir", out_dir, "--cancel-file", cancel_path
    )
    payload = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    final = _stdout_records(completed)[-1]

    assert completed.returncode == 0
    assert payload["findings"] == []
    assert final["cancelled"] is True


def test_zero_deadline_sets_cancel_and_returns_zero(tmp_path: Path) -> None:
    completed = _run_cli(
        "--input", SAMPLE_PATH, "--out-dir", tmp_path, "--deadline-sec", 0
    )
    final = _stdout_records(completed)[-1]

    assert completed.returncode == 0
    assert final["cancelled"] is True
    assert (tmp_path / "result.json").is_file()


def test_missing_key_does_not_use_ai_and_stdout_is_jsonl(tmp_path: Path) -> None:
    input_path = tmp_path / "elements.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "url": "https://example.test/",
                    "location": "body > span",
                    "text": "수상한 초대 문구",
                    "style": {"display": "none"},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    completed = _run_cli("--input", input_path, "--out-dir", out_dir)
    records = _stdout_records(completed)

    assert completed.returncode == 0
    assert records
    assert all(isinstance(record, dict) for record in records)
    assert records[-1]["ai_used"] is False


def test_dummy_key_never_appears_in_stdout_stderr_or_log(tmp_path: Path) -> None:
    dummy_key = "AIzaTHIS_IS_A_DUMMY_SECRET_1234567890"
    completed = _run_cli(
        "--input",
        SAMPLE_PATH,
        "--out-dir",
        tmp_path,
        "--no-ai",
        env_extra={"GEMINI_API_KEY": dummy_key},
    )
    combined = completed.stdout + completed.stderr
    combined += (tmp_path / "detect_log.jsonl").read_text(encoding="utf-8")

    assert completed.returncode == 0
    assert dummy_key not in combined


def test_default_deadline_finishes_before_contest_timeout() -> None:
    args = detector_cli._build_parser().parse_args(["--input", str(SAMPLE_PATH)])

    assert args.deadline_sec == detector_cli.DEFAULT_DEADLINE_SEC
    assert 0 < args.deadline_sec < 30 * 60


def test_ambiguous_bare_tag_input_is_skipped(tmp_path: Path) -> None:
    input_path = tmp_path / "elements.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "url": "https://example.test/",
                    "location": "div",
                    "text": "ㅋㅏㅈㅣㄴㅗ",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = _run_cli("--input", input_path, "--out-dir", tmp_path / "out", "--no-ai")
    payload = json.loads((tmp_path / "out" / "result.json").read_text(encoding="utf-8"))

    assert completed.returncode == 2
    assert payload["findings"] == []
    assert "must identify one element" in completed.stderr
