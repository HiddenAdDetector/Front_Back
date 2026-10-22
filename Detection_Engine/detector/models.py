"""Data contracts exchanged between the crawler and detection engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(slots=True)
class Element:
    """A browser element collected by part B and inspected by part A."""

    url: str
    location: str
    frame_path: list[str]
    text: str
    context: str
    style: dict[str, Any]
    bbox: dict[str, Any]


@dataclass(slots=True)
class Verdict:
    """The engine's decision for one input element."""

    url: str
    location: str
    frame_path: list[str]
    is_violation: bool
    techniques: list[str]
    original_text: str
    normalized_text: str
    reason: str
    decision_source: Literal["rule", "ai"]
