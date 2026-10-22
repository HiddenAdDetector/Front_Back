"""Test-wide guards that keep the suite independent from developer credentials."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def isolate_gemini_environment() -> Iterator[None]:
    names = (
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_TIMEOUT_SEC",
        "GEMINI_BATCH_SIZE",
        "GEMINI_MAX_CALLS",
        "GEMINI_MIN_CONFIDENCE",
        "GEMINI_TOTAL_BUDGET_SEC",
    )
    original = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ.pop(name, None)
    try:
        yield
    finally:
        for name in names:
            os.environ.pop(name, None)
            if original[name] is not None:
                os.environ[name] = original[name]
