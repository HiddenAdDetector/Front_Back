"""Editable illegal-advertising keyword and contact-lure dictionaries."""

from __future__ import annotations

import re

# Keep these dictionaries at module scope so contest-specific terms can be
# reviewed and extended without changing the matching code.
GAMBLING_KEYWORDS: tuple[str, ...] = (
    "카지노",
    "온라인카지노",
    "슬롯",
    "슬롯머신",
    "토토",
    "사설토토",
    "바카라",
    "먹튀검증",
    "먹튀",
    "안전놀이터",
    "놀이터추천",
    "첫충",
    "첫충전",
    "보너스",
    "충전보너스",
    "가입보너스",
    "보너스코드",
    "배팅",
    "베팅",
    "잭팟",
)

ADULT_KEYWORDS: tuple[str, ...] = (
    "성인사이트",
    "성인방송",
    "성인채팅",
    "조건만남",
    "출장마사지",
    "오피사이트",
    "유흥사이트",
    "야동",
)

ILLEGAL_KEYWORDS: tuple[str, ...] = GAMBLING_KEYWORDS + ADULT_KEYWORDS

# Public-interest pages containing these terms are informational rather than
# advertisements, even when their markup happens to use hidden UI patterns.
PREVENTION_CONTEXT_TERMS: tuple[str, ...] = (
    "예방",
    "신고",
    "단속",
    "근절",
    "도박문제",
    "중독예방",
    "피해예방",
    "상담센터 1336",
    "상담센터1336",
    "불법 도박 근절",
    "불법도박 근절",
)

# Strong commercial/evasion cues that prevent a public-interest term from
# suppressing a finding. A bare telephone number is intentionally omitted.
AD_LURE_TERMS: tuple[str, ...] = (
    "첫충",
    "첫충전",
    "보너스",
    "가입",
    "가입코드",
    "추천코드",
    "쿠폰",
    "프로모션",
    "텔레그램",
    "telegram",
    "t.me/",
    "카카오톡",
    "카톡",
    "open.kakao.com/",
    "안전놀이터",
    "먹튀검증",
    "안 걸리는",
    "안걸리는",
    "단속 우회",
    "적발 우회",
)

CONTACT_LURE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:텔레그램|telegram|텔레)\s*(?:아이디|id|문의|상담)?\s*[:：]?\s*@?[a-z0-9_]{4,}", re.IGNORECASE),
    re.compile(r"(?:https?://)?t\.me/[a-z0-9_]{4,}", re.IGNORECASE),
    re.compile(r"(?:카카오톡|카톡|kakao(?:talk)?)\s*(?:아이디|id|문의|상담)?\s*[:：]?\s*[a-z0-9_]{4,}", re.IGNORECASE),
    re.compile(r"open\.kakao\.com/[a-z0-9_/.-]+", re.IGNORECASE),
    re.compile(r"(?:문의|상담|연락)\s*[:：]?\s*(?:0\d{1,2}[- .]?)?\d{3,4}[- .]?\d{4}"),
)


def find_illegal_keywords(text: str) -> list[str]:
    """Return unique dictionary terms found in *text*, longest first."""

    folded = text.casefold()
    matches = {keyword for keyword in ILLEGAL_KEYWORDS if keyword.casefold() in folded}
    return sorted(matches, key=lambda value: (-len(value), value))


def find_contact_lures(text: str) -> list[str]:
    """Return matched contact-lure snippets without duplicates."""

    matches: list[str] = []
    seen: set[str] = set()
    for pattern in CONTACT_LURE_PATTERNS:
        for match in pattern.finditer(text):
            snippet = match.group(0)
            key = snippet.casefold()
            if key not in seen:
                seen.add(key)
                matches.append(snippet)
    return matches


def find_prevention_context(text: str) -> list[str]:
    """Return public-interest prevention/reporting terms found in *text*."""

    folded = text.casefold()
    matches = {term for term in PREVENTION_CONTEXT_TERMS if term.casefold() in folded}
    return sorted(matches, key=lambda value: (-len(value), value))


def find_ad_lures(text: str) -> list[str]:
    """Return strong advertising or enforcement-evasion cues in *text*."""

    folded = text.casefold()
    matches = {term for term in AD_LURE_TERMS if term.casefold() in folded}
    return sorted(matches, key=lambda value: (-len(value), value))
