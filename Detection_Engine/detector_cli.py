"""Subprocess entry point for the AdSentinel detection engine."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from detector import ai_judge
from detector.engine import detect
from detector.models import Element, Verdict
from detector.result_writer import TOPIC, is_ambiguous_location, write_result

KST = timezone(timedelta(hours=9))
DEFAULT_TOPIC = TOPIC
DEFAULT_TOOL_VERSION = "0.5.0"
CANCEL_POLL_SEC = 0.5
DEFAULT_DEADLINE_SEC = 1700.0


class InputError(ValueError):
    """Raised when the input document cannot be used."""


def _runtime_dir() -> Path:
    executable_or_script = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
    return Path(executable_or_script).resolve().parent


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _json_line(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def _safe_error(error: object) -> str:
    try:
        api_key = ai_judge.load_settings().api_key
    except Exception:
        api_key = os.getenv("GEMINI_API_KEY", "")
    return ai_judge.mask_sensitive(error, api_key)


def _warn(message: str) -> None:
    print(f"경고: {_safe_error(message)}", file=sys.stderr, flush=True)


def _parse_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field_name} must be a non-empty ISO 8601 string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise InputError(f"{field_name} is not valid ISO 8601") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed


def _as_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise InputError(f"{field_name} must be a string")
    return value


def _element_from_dict(raw: object) -> Element:
    if not isinstance(raw, dict):
        raise InputError("element must be an object")

    url = _as_string(raw.get("url"), "element.url")
    location = _as_string(raw.get("location"), "element.location")
    if is_ambiguous_location(location):
        raise InputError("element.location must identify one element, not a common bare tag")
    text = _as_string(raw.get("text"), "element.text")
    context = raw.get("context", "")
    if context is None:
        context = ""
    context = _as_string(context, "element.context")

    style = raw.get("style") or {}
    bbox = raw.get("bbox") or {}
    if not isinstance(style, dict):
        raise InputError("element.style must be an object")
    if not isinstance(bbox, dict):
        raise InputError("element.bbox must be an object")

    frame_path_value = raw.get("frame_path", raw.get("framePath", []))
    if frame_path_value is None:
        frame_path: list[str] = []
    elif isinstance(frame_path_value, str):
        frame_path = [frame_path_value]
    elif isinstance(frame_path_value, list) and all(
        isinstance(item, str) for item in frame_path_value
    ):
        frame_path = list(frame_path_value)
    else:
        raise InputError("element.frame_path must be a string or string array")

    if location.startswith('iframe[src=') and " >>> " in location:
        # TODO: Remove after B always sends an iframe-local selector in location.
        frame_path = []

    return Element(
        url=url,
        location=location,
        frame_path=frame_path,
        text=text,
        context=context,
        style=dict(style),
        bbox=dict(bbox),
    )


def _load_input(path: Path) -> tuple[dict[str, object], list[Element]]:
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            payload = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputError(f"input JSON could not be read: {error}") from error

    if isinstance(payload, list):
        metadata: dict[str, object] = {}
        raw_elements = payload
    elif isinstance(payload, dict):
        metadata = payload
        raw_elements = payload.get("elements")
        if not isinstance(raw_elements, list):
            raise InputError("top-level elements must be an array")
    else:
        raise InputError("input JSON must be an object or array")

    if not raw_elements:
        raise InputError("elements must contain at least one item")

    elements: list[Element] = []
    for index, raw in enumerate(raw_elements, start=1):
        try:
            elements.append(_element_from_dict(raw))
        except InputError as error:
            _warn(f"element {index} skipped: {error}")
    if not elements:
        raise InputError("input contains no valid elements")
    return metadata, elements


def _watch_cancel_file(
    cancel_path: Path,
    cancel_event: threading.Event,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set() and not cancel_event.is_set():
        if cancel_path.exists():
            cancel_event.set()
            return
        stop_event.wait(CANCEL_POLL_SEC)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AdSentinel element detection CLI")
    parser.add_argument("--input", required=True, type=Path, help="elements JSON file")
    parser.add_argument("--out-dir", type=Path, default=_runtime_dir())
    parser.add_argument("--entry-url")
    parser.add_argument("--started-at")
    parser.add_argument("--deadline-sec", type=float, default=DEFAULT_DEADLINE_SEC)
    parser.add_argument("--cancel-file", type=Path)
    parser.add_argument("--no-ai", action="store_true")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--tool-version", default=DEFAULT_TOOL_VERSION)
    return parser


def _write_empty_or_partial(
    *,
    entry_url: str,
    started_at: datetime,
    verdicts: list[Verdict],
    out_dir: Path,
    tool_version: str,
    topic: str,
) -> Path:
    return write_result(
        entry_url=entry_url,
        started_at=started_at,
        finished_at=datetime.now(KST),
        verdicts=verdicts,
        out_dir=out_dir,
        tool_version=tool_version,
        topic=topic,
    )


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    args = _build_parser().parse_args(argv)
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ai_judge.set_log_dir(out_dir)
    log_path = out_dir / ai_judge.LOG_FILENAME
    log_path.touch(exist_ok=True)

    now = datetime.now(KST)
    entry_url = args.entry_url or ""
    started_at = now
    verdicts: list[Verdict] = []
    result_path = out_dir / "result.json"
    exit_code = 0
    cancel_event = threading.Event()
    stop_event = threading.Event()
    timer: threading.Timer | None = None
    watcher: threading.Thread | None = None
    ai_used = False

    try:
        metadata, elements = _load_input(args.input.resolve())
        input_entry_url = metadata.get("entry_url", "")
        if input_entry_url and not isinstance(input_entry_url, str):
            raise InputError("entry_url must be a string")
        entry_url = args.entry_url or str(input_entry_url or elements[0].url)

        started_value = args.started_at or metadata.get("started_at")
        started_at = (
            _parse_datetime(started_value, "started_at") if started_value else datetime.now(KST)
        )

        if args.deadline_sec is not None:
            if args.deadline_sec < 0:
                raise InputError("deadline-sec must be zero or greater")
            timer = threading.Timer(args.deadline_sec, cancel_event.set)
            timer.daemon = True
            timer.start()
        if args.cancel_file is not None:
            if args.cancel_file.resolve().exists():
                cancel_event.set()
            watcher = threading.Thread(
                target=_watch_cancel_file,
                args=(args.cancel_file.resolve(), cancel_event, stop_event),
                name="adsentinel-cancel-file",
                daemon=True,
            )
            watcher.start()

        settings = ai_judge.load_settings()
        ai_enabled = not args.no_ai and bool(settings.api_key)

        def on_progress(done: int, total: int, state: str) -> None:
            nonlocal ai_used
            if state == "ai" and ai_enabled:
                ai_used = True
            _json_line(
                {"type": "progress", "state": state, "done": done, "total": total}
            )

        verdicts = detect(
            elements,
            use_ai=not args.no_ai,
            cancel_event=cancel_event,
            on_progress=on_progress,
        )
    except InputError as error:
        exit_code = 2
        _warn(str(error))
    except BaseException as error:
        exit_code = 1
        _warn(f"unexpected error: {error}")
    finally:
        stop_event.set()
        if timer is not None:
            timer.cancel()
        if watcher is not None:
            watcher.join(timeout=0.1)
        try:
            result_path = _write_empty_or_partial(
                entry_url=entry_url,
                started_at=started_at,
                verdicts=verdicts,
                out_dir=out_dir,
                tool_version=args.tool_version,
                topic=args.topic,
            )
        except BaseException as error:
            exit_code = 1
            _warn(f"result.json write failed: {error}")

    findings_count = 0
    try:
        with result_path.open("r", encoding="utf-8") as stream:
            findings_count = len(json.load(stream).get("findings", []))
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
        pass
    _json_line(
        {
            "type": "result",
            "path": str(result_path.resolve()),
            "findings": findings_count,
            "cancelled": cancel_event.is_set(),
            "ai_used": ai_used,
        }
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
