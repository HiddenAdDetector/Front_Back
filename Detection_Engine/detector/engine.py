"""Rule-based AdSentinel detection engine."""

from __future__ import annotations

from dataclasses import replace
from threading import Event
from typing import Callable

from . import ai_judge
from .hidden import is_accessibility_location, is_offscreen, is_transparent
from .homoglyph import normalize_homoglyphs
from .jamo import is_decomposed_jamo, recompose_compat_jamo
from .keywords import (
    find_ad_lures,
    find_contact_lures,
    find_illegal_keywords,
    find_prevention_context,
)
from .models import Element, Verdict

ProgressCallback = Callable[[int, int, str], None]


def _detect_one(element: Element) -> Verdict:
    original = element.text
    homoglyph_normalized = normalize_homoglyphs(original)
    jamo_present = is_decomposed_jamo(homoglyph_normalized)
    normalized = recompose_compat_jamo(homoglyph_normalized) if jamo_present else homoglyph_normalized
    keywords = find_illegal_keywords(normalized)
    contact_lures = find_contact_lures(normalized)
    contextual_text = f"{normalized} {element.context}"
    prevention_context = find_prevention_context(contextual_text)
    ad_lures = find_ad_lures(contextual_text)
    exclude_as_prevention = bool(prevention_context) and not ad_lures

    techniques: list[str] = []
    reasons: list[str] = []
    if exclude_as_prevention:
        reasons.append(f"예방·신고·단속 안내 맥락 제외: {', '.join(prevention_context)}")
    elif keywords and jamo_present and normalized != homoglyph_normalized:
        techniques.append("JAMO")
        reasons.append(f"자모 재조합 후 불법광고 키워드 탐지: {', '.join(keywords)}")
    if not exclude_as_prevention and keywords and homoglyph_normalized != original:
        techniques.append("HOMOGLYPH")
        reasons.append(f"유사문자 정규화 후 불법광고 키워드 탐지: {', '.join(keywords)}")

    # Hidden state alone is never a violation. Accessibility-only selectors are
    # therefore harmless unless the element text itself contains an illegal
    # keyword; a keyword deliberately takes precedence over the class name.
    if not exclude_as_prevention and keywords and is_transparent(element):
        techniques.append("TRANSPARENT")
        reasons.append("투명 텍스트 스타일 탐지")
    if not exclude_as_prevention and keywords and is_offscreen(element):
        techniques.append("OFFSCREEN")
        reasons.append("화면 밖 은닉 스타일 또는 좌표 탐지")

    if contact_lures and techniques:
        reasons.append(f"연락처 유도 표현 동반: {', '.join(contact_lures)}")
    if not reasons:
        reasons.append("지원 대상 우회 기법과 불법광고 키워드의 결합이 탐지되지 않음")

    return Verdict(
        url=element.url,
        location=element.location,
        frame_path=list(element.frame_path),
        is_violation=bool(techniques),
        techniques=techniques,
        original_text=original,
        normalized_text=normalized,
        reason="; ".join(reasons),
        decision_source="rule",
    )


def _ai_candidate(element: Element, verdict: Verdict, candidate_id: str) -> ai_judge.AiCandidate | None:
    if not element.text.strip():
        return None

    contextual_text = f"{verdict.normalized_text} {element.context}"
    prevention_context = find_prevention_context(contextual_text)
    accessibility_location = is_accessibility_location(element.location)

    if verdict.is_violation:
        techniques = tuple(verdict.techniques)
        hidden_only = set(techniques) <= {"TRANSPARENT", "OFFSCREEN"}
        needs_review = hidden_only or bool(prevention_context) or accessibility_location
        if not needs_review:
            return None
        return ai_judge.AiCandidate(
            id=candidate_id,
            normalized_text=verdict.normalized_text,
            context=element.context,
            techniques=techniques,
        )

    if find_illegal_keywords(verdict.normalized_text):
        return None
    if prevention_context and not find_ad_lures(contextual_text):
        return None

    homoglyph_normalized = normalize_homoglyphs(element.text)
    jamo_present = is_decomposed_jamo(homoglyph_normalized)
    techniques: list[str] = []
    if jamo_present and verdict.normalized_text != homoglyph_normalized:
        techniques.append("JAMO")
    if homoglyph_normalized != element.text:
        techniques.append("HOMOGLYPH")
    if is_transparent(element):
        techniques.append("TRANSPARENT")
    if is_offscreen(element):
        techniques.append("OFFSCREEN")
    if not techniques:
        return None

    hidden_only = set(techniques) <= {"TRANSPARENT", "OFFSCREEN"}
    if hidden_only and accessibility_location:
        return None
    return ai_judge.AiCandidate(
        id=candidate_id,
        normalized_text=verdict.normalized_text,
        context=element.context,
        techniques=tuple(techniques),
    )


def _notify(callback: ProgressCallback | None, done: int, total: int, state: str) -> None:
    if callback is None:
        return
    try:
        callback(done, total, state)
    except Exception:
        # A UI callback must never interrupt detection or result persistence.
        pass


def detect(
    elements: list[Element],
    use_ai: bool = True,
    cancel_event: Event | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[Verdict]:
    """Inspect elements with rules and optionally promote ambiguous AI candidates."""

    total = len(elements)
    verdicts: list[Verdict] = []
    candidates: list[ai_judge.AiCandidate] = []
    index_by_candidate_id: dict[str, int] = {}
    for index, element in enumerate(elements):
        if cancel_event is not None and cancel_event.is_set():
            break

        verdict = _detect_one(element)
        verdicts.append(verdict)
        candidate_id = f"ai_{index + 1:04d}"
        candidate = _ai_candidate(element, verdict, candidate_id)
        if candidate is not None:
            candidates.append(candidate)
            index_by_candidate_id[candidate_id] = index
        _notify(on_progress, index + 1, total, "rule")

    if not use_ai or not candidates or (cancel_event is not None and cancel_event.is_set()):
        _notify(on_progress, total, total, "done")
        return verdicts

    _notify(on_progress, 0, len(candidates), "ai")
    ai_results = ai_judge.judge(candidates, cancel_event=cancel_event)
    min_confidence = ai_judge.load_settings().min_confidence
    processed = 0
    for candidate in candidates:
        result = ai_results.get(candidate.id)
        if result is not None:
            if result.confidence >= min_confidence:
                verdict_index = index_by_candidate_id[candidate.id]
                prior = verdicts[verdict_index]
                if result.is_ad:
                    verdicts[verdict_index] = replace(
                        prior,
                        is_violation=True,
                        techniques=list(candidate.techniques),
                        reason=f"AI 판정({result.confidence:.2f}): {result.reason}",
                        decision_source="ai",
                    )
                elif prior.is_violation:
                    verdicts[verdict_index] = replace(
                        prior,
                        is_violation=False,
                        techniques=[],
                        reason=f"AI 재검토 제외({result.confidence:.2f}): {result.reason}",
                        decision_source="ai",
                    )
        processed += 1
        _notify(on_progress, processed, len(candidates), "ai")
    _notify(on_progress, total, total, "done")
    return verdicts
