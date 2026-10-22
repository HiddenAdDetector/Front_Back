# 테스트 사이트 정답표

진입 URL: `http://localhost:8000/index.html` (testsite 폴더에서 `python -m http.server 8000`)

- iframe 내부 광고의 url은 iframe을 포함한 상위 페이지(`index.html`) 기준이며, location은 `iframe[src="절대URL"] >>> 선택자` 형식이다.
- 복합 요소는 기법별로 행을 분리했다. 모든 location은 해당 document 내부에서 유일하다(`document.querySelectorAll` 검증).
- `view.html?id=5`의 요소와 `board.html?page=2`의 행은 JS로 생성되므로 렌더링 후 DOM 기준이다.

## 숨김 광고 (탐지 대상)

| 번호 | url | location | technique | evidence_text | 비고 |
|---|---|---|---|---|---|
| 1 | `http://localhost:8000/index.html` | `p.nl-memo` | JAMO | ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ 코드 LUCKY7 | 공지 목록 아래 일반 텍스트(보임) |
| 2 | `http://localhost:8000/index.html` | `p.ft-evt` | HOMOGLYPH | ｍｅｇａ－ＢＥＴ 첫충 30％ 지급 | 푸터, 전각 문자 |
| 3 | `http://localhost:8000/index.html` | `iframe[src="http://localhost:8000/frame.html"] >>> div.fr-ghost` | TRANSPARENT | 먹튀검증 안전놀이터 상담 텔레그램 @promo_777 | iframe 내부, opacity:0 |
| 4 | `http://localhost:8000/index.html` | `iframe[src="http://localhost:8000/frame.html"] >>> iframe[src="http://localhost:8000/frame2.html"] >>> div.fr2-off` | OFFSCREEN | 무료 슬롯 체험 바로가기 | 중첩 iframe 내부, left:-9999px |
| 5 | `http://localhost:8000/board.html` | `table.board-table tbody tr:nth-of-type(3) td.col-title a` | HOMOGLYPH | оnlinе саsinо bonus 안내 | 테이블 행, 키릴 o/e/c/a 혼용 casino |
| 6 | `http://localhost:8000/board.html` | `table.board-table tbody tr:nth-of-type(5) td.col-title span.ct-clear` | TRANSPARENT | 먹튀검증 안전놀이터 상담 텔레그램 @promo_777 | 테이블 행, color:transparent |
| 7 | `http://localhost:8000/board.html?page=2` | `table.board-table tbody tr:nth-of-type(2) td.col-title span.fs-zero` | OFFSCREEN | 무료 슬롯 체험 바로가기 | JS 렌더링 행, font-size:0 |
| 8 | `http://localhost:8000/view.html?id=1` | `article.post-body p.bd-ghost` | TRANSPARENT | 먹튀검증 안전놀이터 상담 텔레그램 @promo_777 | 게시글 본문, opacity:0 |
| 9 | `http://localhost:8000/view.html?id=2` | `ul.cmt-list li:nth-of-type(2) span.cmt-off` | OFFSCREEN | 무료 슬롯 체험 바로가기 | 댓글 영역, left:-9999px |
| 10 | `http://localhost:8000/view.html?id=3` | `article.post-body span.mix-hid` | JAMO | ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ 코드 LUCKY7 | 복합(JAMO+OFFSCREEN) 같은 요소 |
| 11 | `http://localhost:8000/view.html?id=3` | `article.post-body span.mix-hid` | OFFSCREEN | ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ 코드 LUCKY7 | 복합(JAMO+OFFSCREEN) 같은 요소, left:-9999px |
| 12 | `http://localhost:8000/view.html?id=4` | `article.post-body div.bd-none` | OFFSCREEN | 무료 슬롯 체험 바로가기 | 게시글 본문, display:none |
| 13 | `http://localhost:8000/view.html?id=4` | `ul.cmt-list li:nth-of-type(1) span.cmt-wh` | TRANSPARENT | 먹튀검증 안전놀이터 상담 텔레그램 @promo_777 | 댓글 영역, 흰 배경에 흰 글씨 |
| 14 | `http://localhost:8000/view.html?id=5` | `article.post-body span.dyn-zero` | OFFSCREEN | 무료 슬롯 체험 바로가기 | JS createElement 동적 생성, font-size:0 |

## 정상 요소 (탐지되면 오탐)

| 번호 | url | location | evidence_text | 사유 |
|---|---|---|---|---|
| N1 | `http://localhost:8000/index.html` | `p.legal-visible` | 불법 도박 예방 및 신고 안내 | 보이는 예방·신고 안내 |
| N2 | `http://localhost:8000/index.html` | `div.legal-hidden` | 불법 도박 예방 및 신고 안내 | display:none 예방·신고 안내 |
| N3 | `http://localhost:8000/index.html` | `a.sr-only` | 본문 바로가기 | sr-only 접근성 링크 |
| N4 | `http://localhost:8000/index.html` | `a.visually-hidden` | 메뉴 건너뛰기 | visually-hidden 접근성 링크 |
| N5 | `http://localhost:8000/index.html` | `a.dd-link-civil` | 민원서비스 | display:none 드롭다운 메뉴 |
| N6 | `http://localhost:8000/index.html` | `a.dd-link-policy` | 정책정보 | display:none 드롭다운 메뉴 |
| N7 | `http://localhost:8000/index.html` | `p.campaign-1336` | 도박 근절 캠페인 상담센터 1336 | 보이는 캠페인 문구 |
| N8 | `http://localhost:8000/index.html` | `ul.notice-list li:nth-of-type(1) a` | 2026년 하반기 정기 점검 일정 안내 | 일반 공지 문구 |
| N9 | `http://localhost:8000/board.html` | `a.sr-only` | 본문 바로가기 | sr-only 접근성 링크 |
| N10 | `http://localhost:8000/view.html?id=1` | `div.legal-hidden` | 불법 도박 예방 및 신고 안내 | display:none 안내 (view.html 모든 id 공통) |
