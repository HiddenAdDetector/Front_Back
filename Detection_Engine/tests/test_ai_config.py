from pathlib import Path

from detector import ai_judge


def test_loads_env_from_runtime_directory(monkeypatch, tmp_path: Path) -> None:
    dummy_key = "dummy-secret-key-never-log"
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f"GEMINI_API_KEY={dummy_key}",
                "GEMINI_MODEL=test-model",
                "GEMINI_TIMEOUT_SEC=7",
                "GEMINI_BATCH_SIZE=3",
                "GEMINI_MAX_CALLS=4",
                "GEMINI_MIN_CONFIDENCE=0.85",
                "GEMINI_TOTAL_BUDGET_SEC=9",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ai_judge, "_runtime_dir", lambda: tmp_path)
    for name in (
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_TIMEOUT_SEC",
        "GEMINI_BATCH_SIZE",
        "GEMINI_MAX_CALLS",
        "GEMINI_MIN_CONFIDENCE",
        "GEMINI_TOTAL_BUDGET_SEC",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = ai_judge.load_settings()

    assert settings.api_key == dummy_key
    assert settings.model == "test-model"
    assert settings.timeout_sec == 7
    assert settings.batch_size == 3
    assert settings.max_calls == 4
    assert settings.min_confidence == 0.85
    assert settings.total_budget_sec == 9


def test_log_masks_api_key_everywhere(monkeypatch, tmp_path: Path) -> None:
    dummy_key = "AIzaThisIsAFakeKeyThatMustNeverAppear12345"
    settings = ai_judge.GeminiSettings(dummy_key, "test-model", 1, 1, 1, 0.7)
    monkeypatch.setattr(ai_judge, "_runtime_dir", lambda: tmp_path)

    ai_judge._write_log("error", settings=settings, error=f"request failed: {dummy_key}")

    all_output = "".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())
    assert dummy_key not in all_output
    assert "[REDACTED]" in all_output
