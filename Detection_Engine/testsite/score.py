"""result.json을 testsite/answer.json과 비교해 정탐/오탐/미탐을 출력한다.

사용법: python testsite/score.py <result.json>
정탐 기준: 정규화한 url + location + technique 3개가 모두 일치.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ANSWER_PATH = Path(__file__).resolve().parent / "answer.json"


def norm_url(url: str) -> tuple:
    """끝 `/`, http/https, `#` 이하, 쿼리 순서를 무시한 비교 키."""
    parts = urlsplit(url.strip())
    query = tuple(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return parts.netloc.casefold(), parts.path.rstrip("/"), query


def norm_location(location: str) -> str:
    return " ".join(location.split())


def key(finding: dict) -> tuple:
    return (
        norm_url(finding["url"]),
        norm_location(finding["location"]),
        (finding.get("technique") or "").upper(),
    )


def load_findings(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    return data["findings"] if isinstance(data, dict) else data


def describe(finding: dict) -> str:
    return (
        f"[{finding.get('id', '-')}] {finding['url']} | {finding['location']} | "
        f"{finding.get('technique')} | {finding.get('evidence_text', '')}"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python testsite/score.py <result.json>", file=sys.stderr)
        return 2
    answers = load_findings(ANSWER_PATH)
    truths = {key(f): f for f in answers if f["is_violation"]}
    normals = [f for f in answers if not f["is_violation"]]
    normal_keys = {(norm_url(f["url"])[:2], norm_location(f["location"])) for f in normals}

    results = [f for f in load_findings(Path(argv[1])) if f.get("is_violation", True)]
    matched: dict[tuple, dict] = {}
    false_pos: list[tuple[dict, bool]] = []
    for finding in results:
        k = key(finding)
        if k in truths:
            matched.setdefault(k, finding)
        else:
            is_normal = (norm_url(finding["url"])[:2], norm_location(finding["location"])) in normal_keys
            false_pos.append((finding, is_normal))
    missed = [f for k, f in truths.items() if k not in matched]

    print(f"정탐 {len(matched)} / 오탐 {len(false_pos)} / 미탐 {len(missed)}  (정답 {len(truths)}건, 결과 {len(results)}건)")
    print("\n== 정탐 ==")
    for k in matched:
        print("  " + describe(truths[k]))
    print("\n== 오탐 ==")
    for finding, is_normal in false_pos:
        print(f"  {'(정상요소) ' if is_normal else ''}{describe(finding)}")
    print("\n== 미탐 ==")
    for finding in missed:
        print("  " + describe(finding))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
