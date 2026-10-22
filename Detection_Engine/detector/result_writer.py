"""Strict writer for the contest's ``result.json`` interchange format."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .models import Verdict

TOPIC = "TOPIC"
KST = timezone(timedelta(hours=9))
ALLOWED_TECHNIQUES = frozenset({"HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN"})
FINDING_KEYS = frozenset(
    {"id", "url", "is_violation", "location", "evidence_text", "technique"}
)
META_REQUIRED_KEYS = frozenset(
    {"topic", "entry_url", "started_at", "finished_at", "elapsed_sec"}
)
META_ALLOWED_KEYS = META_REQUIRED_KEYS | {"tool_version"}
AMBIGUOUS_BARE_TAGS = frozenset(
    {
        "a",
        "div",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "small",
        "span",
        "strong",
        "td",
    }
)


def _as_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _comparison_url(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Build the PDF-specified URL deduplication key."""

    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    query = tuple(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return parsed.netloc.casefold(), path, query


def _finding_location(verdict: Verdict) -> str:
    frames = [f'iframe[src="{source}"]' for source in verdict.frame_path]
    return " >>> ".join([*frames, verdict.location])


def is_ambiguous_location(location: str) -> bool:
    """Return whether a selector is only a common bare tag.

    Such selectors normally identify multiple elements and are scored as wrong
    by the contest.  For iframe locations only the innermost selector is
    inspected because the frame chain itself does not make a bare ``div``
    unique within that document.
    """

    selector = location.rsplit(" >>> ", 1)[-1].strip().casefold()
    return selector in AMBIGUOUS_BARE_TAGS


def _validate_payload(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != {"meta", "findings"}:
        raise ValueError("result.json must contain exactly meta and findings")

    meta = payload["meta"]
    findings = payload["findings"]
    if (
        not isinstance(meta, dict)
        or not META_REQUIRED_KEYS.issubset(meta)
        or not set(meta).issubset(META_ALLOWED_KEYS)
    ):
        raise ValueError("result.json meta is missing required fields")
    if not isinstance(findings, list):
        raise ValueError("result.json findings must be an array")
    for key in ("topic", "entry_url", "started_at", "finished_at"):
        if not isinstance(meta[key], str):
            raise ValueError(f"result.json meta.{key} must be a string")
    elapsed = meta["elapsed_sec"]
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or elapsed < 0:
        raise ValueError("result.json meta.elapsed_sec must be a non-negative number")
    for key in ("started_at", "finished_at"):
        try:
            datetime.fromisoformat(meta[key])
        except ValueError as error:
            raise ValueError(f"result.json meta.{key} must be ISO 8601") from error

    ids: set[str] = set()
    finding_keys: set[tuple[tuple[str, str, tuple[tuple[str, str], ...]], str, str]] = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != FINDING_KEYS:
            raise ValueError("result.json finding has an invalid schema")
        for key in ("id", "url", "location", "evidence_text", "technique"):
            if not isinstance(finding[key], str) or not finding[key].strip():
                raise ValueError(f"result.json finding.{key} must be a non-empty string")
        if finding["is_violation"] is not True:
            raise ValueError("result.json finding.is_violation must be true")
        if finding["technique"] not in ALLOWED_TECHNIQUES:
            raise ValueError("result.json finding.technique is unsupported")
        if finding["id"] in ids:
            raise ValueError("result.json finding ids must be unique")
        ids.add(finding["id"])
        dedup_key = (
            _comparison_url(finding["url"]),
            finding["location"],
            finding["technique"],
        )
        if dedup_key in finding_keys:
            raise ValueError("result.json contains a duplicate finding")
        finding_keys.add(dedup_key)


def _default_output_dir() -> Path:
    executable_or_script = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
    return Path(executable_or_script).resolve().parent


def write_result(
    entry_url: str,
    started_at: datetime,
    finished_at: datetime,
    verdicts: list[Verdict],
    out_dir: str | Path | None = None,
    tool_version: str = "",
    topic: str = TOPIC,
) -> Path:
    """Write a schema-strict result file and return its absolute path.

    The function accepts an incomplete list of verdicts, so callers can invoke
    it from cancellation and timeout handlers without a separate code path.
    """

    started = _as_kst(started_at)
    finished = _as_kst(finished_at)
    elapsed = round((finished - started).total_seconds(), 3)
    elapsed_value: int | float = int(elapsed) if elapsed.is_integer() else elapsed

    findings: list[dict[str, object]] = []
    seen: set[tuple[tuple[str, str, tuple[tuple[str, str], ...]], str, str]] = set()
    for verdict in verdicts:
        if not verdict.is_violation:
            continue
        location = _finding_location(verdict)
        if is_ambiguous_location(location):
            continue
        for technique in dict.fromkeys(verdict.techniques):
            if technique not in ALLOWED_TECHNIQUES:
                raise ValueError(f"Unsupported result technique: {technique!r}")
            dedup_key = (_comparison_url(verdict.url), location, technique)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            findings.append(
                {
                    "id": f"f_{len(findings) + 1:03d}",
                    "url": verdict.url,
                    "is_violation": True,
                    "location": location,
                    "evidence_text": verdict.original_text,
                    "technique": technique,
                }
            )

    payload = {
        "meta": {
            "topic": topic,
            "entry_url": entry_url,
            "started_at": started.isoformat(timespec="seconds"),
            "finished_at": finished.isoformat(timespec="seconds"),
            "elapsed_sec": elapsed_value,
            "tool_version": tool_version,
        },
        "findings": findings,
    }
    _validate_payload(payload)

    destination = Path(out_dir) if out_dir is not None else _default_output_dir()
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    result_path = destination / "result.json"
    temporary_path = destination / ".result.json.tmp"
    with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    temporary_path.replace(result_path)
    raw = result_path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("result.json must not contain a UTF-8 BOM")
    _validate_payload(json.loads(raw.decode("utf-8")))
    return result_path
