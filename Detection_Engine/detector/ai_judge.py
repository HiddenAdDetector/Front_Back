"""Optional, failure-safe Google Gemini classification for suspicious elements."""

from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Iterable

from dotenv import load_dotenv

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_TIMEOUT_SEC = 20.0
DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_CALLS = 30
DEFAULT_MIN_CONFIDENCE = 0.7
DEFAULT_TOTAL_BUDGET_SEC = 120.0
LOG_FILENAME = "detect_log.jsonl"
MAX_TEXT_CHARS = 300
MAX_CONTEXT_CHARS = 300
MAX_RETRIES = 2
MAX_CONSECUTIVE_FAILURES = 3
_log_dir_override: Path | None = None

SYSTEM_INSTRUCTION = (
    "각 항목이 도박·성인물 등 불법광고로 사용자를 유도하는 문구인지 판단한다. "
    "예방·신고·정책 안내, 단순 인용, 뉴스, 접근성 안내는 광고가 아니다. "
    "근거 없이 추측하지 말고 애매하면 is_ad를 false로 답한다. "
    "reason은 한국어 한 문장으로 작성한다."
)

RESPONSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "is_ad": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["id", "is_ad", "confidence", "reason"],
        "additionalProperties": False,
    },
}

_GOOGLE_API_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]{20,}")


@dataclass(frozen=True, slots=True)
class AiCandidate:
    id: str
    normalized_text: str
    context: str
    techniques: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AiResult:
    id: str
    is_ad: bool
    confidence: float
    reason: str


@dataclass(frozen=True, slots=True)
class GeminiSettings:
    api_key: str
    model: str
    timeout_sec: float
    batch_size: int
    max_calls: int
    min_confidence: float
    total_budget_sec: float = DEFAULT_TOTAL_BUDGET_SEC


def _runtime_dir() -> Path:
    executable_or_script = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
    return Path(executable_or_script).resolve().parent


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def load_settings() -> GeminiSettings:
    """Load Gemini settings from the executable/script-adjacent ``.env``."""

    load_dotenv(dotenv_path=_runtime_dir() / ".env", override=False)
    try:
        confidence = float(os.getenv("GEMINI_MIN_CONFIDENCE", str(DEFAULT_MIN_CONFIDENCE)))
    except ValueError:
        confidence = DEFAULT_MIN_CONFIDENCE
    return GeminiSettings(
        api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL,
        timeout_sec=_positive_float("GEMINI_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC),
        batch_size=_positive_int("GEMINI_BATCH_SIZE", DEFAULT_BATCH_SIZE),
        max_calls=_positive_int("GEMINI_MAX_CALLS", DEFAULT_MAX_CALLS),
        min_confidence=max(0.0, min(1.0, confidence)),
        total_budget_sec=_positive_float("GEMINI_TOTAL_BUDGET_SEC", DEFAULT_TOTAL_BUDGET_SEC),
    )


def _mask_sensitive(value: object, api_key: str = "") -> str:
    text = str(value)
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    return _GOOGLE_API_KEY_RE.sub("[REDACTED]", text)


def mask_sensitive(value: object, api_key: str = "") -> str:
    """Return a log-safe string with API credentials redacted."""

    return _mask_sensitive(value, api_key)


def set_log_dir(path: str | Path | None) -> None:
    """Override the directory used for ``detect_log.jsonl``."""

    global _log_dir_override
    _log_dir_override = None if path is None else Path(path)


def _write_log(event: str, *, settings: GeminiSettings | None = None, **fields: Any) -> None:
    """Append a sanitized operational record; logging failure never affects detection."""

    api_key = settings.api_key if settings is not None else ""
    safe_fields = {
        str(key): _mask_sensitive(value, api_key)
        if isinstance(value, (str, bytes, BaseException))
        else value
        for key, value in fields.items()
        if key.casefold() not in {"api_key", "key", "token"}
    }
    record = {"event": event, **safe_fields}
    try:
        log_path = (_log_dir_override or _runtime_dir()) / LOG_FILENAME
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, ensure_ascii=False, default=str)
            stream.write("\n")
    except OSError:
        pass


class _Cancelled(Exception):
    pass


class _InvalidResponse(ValueError):
    pass


class _BudgetExceeded(Exception):
    pass


def _create_client(settings: GeminiSettings) -> Any:
    """Create the installed google-genai client using its verified v2 signature."""

    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=settings.api_key,
        http_options=types.HttpOptions(timeout=int(settings.timeout_sec * 1000)),
    )


def _call_model(client: Any, settings: GeminiSettings, batch: list[AiCandidate]) -> str:
    from google.genai import types

    payload = [
        {
            "id": candidate.id,
            "normalized_text": candidate.normalized_text[:MAX_TEXT_CHARS],
            "context": candidate.context[:MAX_CONTEXT_CHARS],
            "techniques": list(candidate.techniques),
        }
        for candidate in batch
    ]
    response = client.models.generate_content(
        model=settings.model,
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=RESPONSE_JSON_SCHEMA,
        ),
    )
    text = getattr(response, "text", None)
    if not isinstance(text, str):
        raise _InvalidResponse("Gemini response did not contain JSON text")
    return text


def _call_model_cancelable(
    client: Any,
    settings: GeminiSettings,
    batch: list[AiCandidate],
    cancel_event: Event | None,
    deadline: float,
) -> str:
    """Run a synchronous SDK call in a daemon thread so cancellation returns immediately."""

    outcome: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            outcome.put((True, _call_model(client, settings, batch)))
        except BaseException as error:  # propagated and sanitized by the caller
            outcome.put((False, error))

    thread = threading.Thread(target=run, name="adsentinel-gemini", daemon=True)
    thread.start()
    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise _Cancelled()
        if time.monotonic() >= deadline:
            raise _BudgetExceeded()
        try:
            succeeded, value = outcome.get(timeout=0.05)
        except queue.Empty:
            continue
        if succeeded:
            return str(value)
        if isinstance(value, BaseException):
            raise value
        raise RuntimeError("Gemini call failed")


def _parse_response(text: str, expected_ids: set[str]) -> dict[str, AiResult]:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as error:
        raise _InvalidResponse("Gemini returned invalid JSON") from error
    if not isinstance(payload, list):
        raise _InvalidResponse("Gemini response must be a JSON array")

    results: dict[str, AiResult] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        candidate_id = item.get("id")
        is_ad = item.get("is_ad")
        confidence = item.get("confidence")
        reason = item.get("reason")
        if candidate_id not in expected_ids or candidate_id in results:
            continue
        if not isinstance(is_ad, bool) or isinstance(confidence, bool):
            continue
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            continue
        if not isinstance(reason, str) or not reason.strip():
            continue
        results[candidate_id] = AiResult(
            id=candidate_id,
            is_ad=is_ad,
            confidence=float(confidence),
            reason=reason.strip(),
        )
    return results


def _is_rate_limit(error: BaseException) -> bool:
    code = getattr(error, "status_code", None) or getattr(error, "code", None)
    return code == 429 or "429" in str(error)


def _wait_before_retry(
    error: BaseException,
    retry_index: int,
    cancel_event: Event | None,
    deadline: float,
) -> bool:
    base_delay = 0.25 if _is_rate_limit(error) else 0.5
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return True
    delay = min(base_delay * (2**retry_index), remaining)
    if cancel_event is not None:
        return cancel_event.wait(delay)
    time.sleep(delay)
    return False


def _deduplicate_candidates(
    candidates: Iterable[AiCandidate],
) -> tuple[list[AiCandidate], dict[tuple[str, str, tuple[str, ...]], list[str]]]:
    representatives: list[AiCandidate] = []
    ids_by_signature: dict[tuple[str, str, tuple[str, ...]], list[str]] = {}
    for candidate in candidates:
        if not candidate.normalized_text.strip():
            continue
        signature = (
            candidate.normalized_text.strip(),
            candidate.context.strip(),
            candidate.techniques,
        )
        ids = ids_by_signature.setdefault(signature, [])
        ids.append(candidate.id)
        if len(ids) == 1:
            representatives.append(candidate)
    return representatives, ids_by_signature


def judge(
    candidates: Iterable[AiCandidate],
    cancel_event: Event | None = None,
) -> dict[str, AiResult]:
    """Judge candidates with Gemini, returning only validated results by id."""

    settings = load_settings()
    deadline = time.monotonic() + settings.total_budget_sec
    representatives, ids_by_signature = _deduplicate_candidates(candidates)
    if not representatives or not settings.api_key:
        return {}
    if cancel_event is not None and cancel_event.is_set():
        return {}

    try:
        client = _create_client(settings)
    except BaseException as error:
        _write_log("ai_client_error", settings=settings, error=error)
        return {}

    representative_results: dict[str, AiResult] = {}
    call_count = 0
    consecutive_failures = 0
    stop_calling = False

    for offset in range(0, len(representatives), settings.batch_size):
        if stop_calling or (cancel_event is not None and cancel_event.is_set()):
            break
        if time.monotonic() >= deadline:
            _write_log(
                "ai_budget_exhausted",
                settings=settings,
                skipped_candidates=len(representatives) - offset,
                total_budget_sec=settings.total_budget_sec,
            )
            break
        if call_count >= settings.max_calls:
            _write_log(
                "ai_call_limit",
                settings=settings,
                skipped_candidates=len(representatives) - offset,
                max_calls=settings.max_calls,
            )
            break

        batch = representatives[offset : offset + settings.batch_size]
        parsed: dict[str, AiResult] | None = None
        for retry_index in range(MAX_RETRIES + 1):
            if call_count >= settings.max_calls:
                break
            try:
                call_count += 1
                response_text = _call_model_cancelable(
                    client,
                    settings,
                    batch,
                    cancel_event,
                    deadline,
                )
                parsed = _parse_response(response_text, {candidate.id for candidate in batch})
                consecutive_failures = 0
                break
            except _Cancelled:
                _write_log("ai_cancelled", settings=settings, completed=len(representative_results))
                stop_calling = True
                break
            except _BudgetExceeded:
                _write_log(
                    "ai_budget_exhausted",
                    settings=settings,
                    skipped_candidates=len(representatives) - offset,
                    total_budget_sec=settings.total_budget_sec,
                )
                stop_calling = True
                break
            except BaseException as error:
                consecutive_failures += 1
                _write_log(
                    "ai_call_error",
                    settings=settings,
                    error=error,
                    attempt=retry_index + 1,
                    rate_limited=_is_rate_limit(error),
                )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    _write_log(
                        "ai_circuit_open",
                        settings=settings,
                        consecutive_failures=consecutive_failures,
                    )
                    stop_calling = True
                    break
                if retry_index < MAX_RETRIES and call_count < settings.max_calls:
                    if _wait_before_retry(error, retry_index, cancel_event, deadline):
                        stop_calling = True
                        break

        if parsed is not None:
            representative_results.update(parsed)
            for result in parsed.values():
                _write_log(
                    "ai_result",
                    settings=settings,
                    candidate_id=result.id,
                    is_ad=result.is_ad,
                    confidence=result.confidence,
                    reason=result.reason,
                    model=settings.model,
                )

    expanded: dict[str, AiResult] = {}
    representative_by_signature = {
        (candidate.normalized_text.strip(), candidate.context.strip(), candidate.techniques): candidate.id
        for candidate in representatives
    }
    for signature, candidate_ids in ids_by_signature.items():
        representative_id = representative_by_signature[signature]
        result = representative_results.get(representative_id)
        if result is None:
            continue
        for candidate_id in candidate_ids:
            expanded[candidate_id] = AiResult(
                id=candidate_id,
                is_ad=result.is_ad,
                confidence=result.confidence,
                reason=result.reason,
            )
    return expanded
