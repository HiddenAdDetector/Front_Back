import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from detector import ai_judge
from detector.ai_judge import AiCandidate, GeminiSettings


def _candidate(candidate_id: str, text: str | None = None) -> AiCandidate:
    return AiCandidate(candidate_id, text or f"의심 문구 {candidate_id}", "주변 문맥", ("OFFSCREEN",))


def _settings(**overrides: object) -> GeminiSettings:
    values: dict[str, object] = {
        "api_key": "dummy-secret-key",
        "model": "test-model",
        "timeout_sec": 1,
        "batch_size": 20,
        "max_calls": 30,
        "min_confidence": 0.7,
    }
    values.update(overrides)
    return GeminiSettings(**values)  # type: ignore[arg-type]


class FakeModels:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return SimpleNamespace(text=outcome)


class FakeClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.models = FakeModels(outcomes)


def _install_fake(monkeypatch, tmp_path: Path, settings: GeminiSettings, outcomes: list[object]) -> FakeClient:
    client = FakeClient(outcomes)
    monkeypatch.setattr(ai_judge, "load_settings", lambda: settings)
    monkeypatch.setattr(ai_judge, "_create_client", lambda _settings: client)
    monkeypatch.setattr(ai_judge, "_runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(ai_judge, "_wait_before_retry", lambda *_args: False)
    return client


def test_missing_key_never_creates_client(monkeypatch) -> None:
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings(api_key=""))
    monkeypatch.setattr(
        ai_judge,
        "_create_client",
        lambda _settings: (_ for _ in ()).throw(AssertionError("must not call")),
    )

    assert ai_judge.judge([_candidate("a")]) == {}


def test_normal_response_and_duplicate_text_use_one_transmitted_candidate(monkeypatch, tmp_path) -> None:
    response = json.dumps([{"id": "a", "is_ad": True, "confidence": 0.91, "reason": "광고 유도"}])
    client = _install_fake(monkeypatch, tmp_path, _settings(), [response])

    results = ai_judge.judge([_candidate("a", "동일 문구"), _candidate("b", "동일 문구")])

    assert set(results) == {"a", "b"}
    assert results["b"].confidence == 0.91
    sent = json.loads(client.models.calls[0]["contents"])  # type: ignore[arg-type]
    assert len(sent) == 1
    assert set(sent[0]) == {"id", "normalized_text", "context", "techniques"}


def test_same_text_with_different_context_or_technique_is_not_deduplicated(monkeypatch, tmp_path) -> None:
    response = json.dumps(
        [
            {"id": "a", "is_ad": False, "confidence": 0.9, "reason": "예방 안내"},
            {"id": "b", "is_ad": True, "confidence": 0.9, "reason": "가입 광고"},
            {"id": "c", "is_ad": True, "confidence": 0.9, "reason": "다른 은닉 기법"},
        ]
    )
    client = _install_fake(monkeypatch, tmp_path, _settings(), [response])
    candidates = [
        AiCandidate("a", "동일 문구", "예방 및 신고 안내", ("OFFSCREEN",)),
        AiCandidate("b", "동일 문구", "가입 보너스 안내", ("OFFSCREEN",)),
        AiCandidate("c", "동일 문구", "가입 보너스 안내", ("TRANSPARENT",)),
    ]

    results = ai_judge.judge(candidates)

    assert set(results) == {"a", "b", "c"}
    sent = json.loads(client.models.calls[0]["contents"])  # type: ignore[arg-type]
    assert len(sent) == 3


def test_transmitted_text_and_context_are_capped_at_300_characters(monkeypatch, tmp_path) -> None:
    response = json.dumps([{"id": "a", "is_ad": False, "confidence": 1, "reason": "광고 아님"}])
    client = _install_fake(monkeypatch, tmp_path, _settings(), [response])
    candidate = AiCandidate("a", "가" * 500, "나" * 500, ("HOMOGLYPH",))

    ai_judge.judge([candidate])

    sent = json.loads(client.models.calls[0]["contents"])  # type: ignore[arg-type]
    assert len(sent[0]["normalized_text"]) == 300
    assert len(sent[0]["context"]) == 300


def test_missing_unknown_and_invalid_items_fall_back_individually(monkeypatch, tmp_path) -> None:
    response = json.dumps(
        [
            {"id": "a", "is_ad": True, "confidence": 0.8, "reason": "광고"},
            {"id": "unknown", "is_ad": True, "confidence": 1, "reason": "무시"},
            {"id": "b", "is_ad": "yes", "confidence": 0.9, "reason": "잘못된 형식"},
        ]
    )
    _install_fake(monkeypatch, tmp_path, _settings(), [response])

    results = ai_judge.judge([_candidate("a"), _candidate("b"), _candidate("c")])

    assert set(results) == {"a"}


def test_invalid_json_retries_then_falls_back(monkeypatch, tmp_path) -> None:
    client = _install_fake(monkeypatch, tmp_path, _settings(), ["not-json"] * 3)

    assert ai_judge.judge([_candidate("a")]) == {}
    assert len(client.models.calls) == 3


def test_429_retries_and_three_failures_open_circuit(monkeypatch, tmp_path) -> None:
    client = _install_fake(
        monkeypatch,
        tmp_path,
        _settings(batch_size=1),
        [RuntimeError("429 quota exceeded")] * 3,
    )

    results = ai_judge.judge([_candidate("a"), _candidate("b")])

    assert results == {}
    assert len(client.models.calls) == 3
    log_text = (tmp_path / ai_judge.LOG_FILENAME).read_text(encoding="utf-8")
    assert "ai_circuit_open" in log_text


def test_timeout_retries_then_falls_back(monkeypatch, tmp_path) -> None:
    client = _install_fake(monkeypatch, tmp_path, _settings(), [TimeoutError("timed out")] * 3)

    assert ai_judge.judge([_candidate("a")]) == {}
    assert len(client.models.calls) == 3


def test_cancel_returns_without_waiting_for_inflight_call(monkeypatch, tmp_path) -> None:
    class BlockingModels:
        def generate_content(self, **_kwargs: object) -> object:
            time.sleep(2)
            return SimpleNamespace(text="[]")

    client = SimpleNamespace(models=BlockingModels())
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings())
    monkeypatch.setattr(ai_judge, "_create_client", lambda _settings: client)
    monkeypatch.setattr(ai_judge, "_runtime_dir", lambda: tmp_path)
    cancel_event = threading.Event()
    threading.Timer(0.05, cancel_event.set).start()

    started = time.perf_counter()
    results = ai_judge.judge([_candidate("a")], cancel_event=cancel_event)
    elapsed = time.perf_counter() - started

    assert results == {}
    assert elapsed < 0.5


def test_total_budget_returns_without_waiting_and_logs_remaining_candidates(monkeypatch, tmp_path) -> None:
    class BlockingModels:
        def generate_content(self, **_kwargs: object) -> object:
            time.sleep(2)
            return SimpleNamespace(text="[]")

    client = SimpleNamespace(models=BlockingModels())
    monkeypatch.setattr(ai_judge, "load_settings", lambda: _settings(total_budget_sec=0.05))
    monkeypatch.setattr(ai_judge, "_create_client", lambda _settings: client)
    monkeypatch.setattr(ai_judge, "_runtime_dir", lambda: tmp_path)

    started = time.perf_counter()
    results = ai_judge.judge([_candidate("a"), _candidate("b")])
    elapsed = time.perf_counter() - started

    assert results == {}
    assert elapsed < 0.5
    assert "ai_budget_exhausted" in (tmp_path / ai_judge.LOG_FILENAME).read_text(encoding="utf-8")


def test_max_calls_skips_remaining_batches(monkeypatch, tmp_path) -> None:
    response = json.dumps([{"id": "a", "is_ad": False, "confidence": 0.9, "reason": "아님"}])
    client = _install_fake(monkeypatch, tmp_path, _settings(batch_size=1, max_calls=1), [response])

    results = ai_judge.judge([_candidate("a"), _candidate("b")])

    assert set(results) == {"a"}
    assert len(client.models.calls) == 1
    assert "ai_call_limit" in (tmp_path / ai_judge.LOG_FILENAME).read_text(encoding="utf-8")


def test_error_logs_and_output_never_contain_api_key(monkeypatch, tmp_path, capsys) -> None:
    dummy_key = "test-api-key-not-a-secret"
    client = _install_fake(
        monkeypatch,
        tmp_path,
        _settings(api_key=dummy_key),
        [RuntimeError(f"request with {dummy_key} failed")] * 3,
    )

    assert ai_judge.judge([_candidate("a")]) == {}
    assert len(client.models.calls) == 3
    captured = capsys.readouterr()
    all_output = captured.out + captured.err + (tmp_path / ai_judge.LOG_FILENAME).read_text(encoding="utf-8")
    assert dummy_key not in all_output
