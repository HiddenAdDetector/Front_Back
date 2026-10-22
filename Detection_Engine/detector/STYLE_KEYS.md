# B → A `Element` 수집 계약

B 크롤러는 각 DOM 요소를 아래 `Element` 구조로 A 탐지 엔진에 전달한다.
누락된 스타일 키는 A에서 기본값으로 처리하지만, 은닉 탐지 정확도를 위해 아래 항목은 모두 수집한다.

## 요소 필드

| 필드 | 기대 값 형식 | 설명 |
|---|---|---|
| `url` | 절대 URL 문자열 | 요소가 존재하는 페이지의 전체 URL |
| `location` | CSS 선택자 문자열 | 현재 document 또는 iframe document 내부에서 요소 하나만 가리키는 선택자 |
| `frame_path` | 절대 URL 문자열의 리스트 | 바깥쪽 iframe부터 안쪽 iframe 순서로 기록 |
| `text` | 문자열 | 정규화하지 않은 요소 원문 |
| `context` | 문자열 | 제목, 인접 문장 등 판정용 주변 문맥 |
| `style` | 객체 | 아래 계산 스타일 키와 값 |
| `bbox` | 숫자 객체 | `getBoundingClientRect()`의 `x`, `y`, `width`, `height` |

iframe 내부 요소의 `location`은 iframe 바깥 문서부터 이어 붙인 선택자가 아니라 **해당 iframe document 내부 기준 선택자**로 전달한다. A의 result writer가 `frame_path`를 사용해 다음처럼 `>>>` 경로를 조합한다.

```text
iframe[src="https://example.go.kr/frame"] >>> div.ad > span
```

`location`은 해당 document 안에서 정확히 한 요소만 가리켜야 한다. 같은 선택자가 둘 이상의 요소를 가리켜 위치를 특정할 수 없으면 공모전 채점에서 오답 처리된다.

## `style` 키와 값 형식

CSS 값은 별도 숫자 변환 없이 `getComputedStyle()`이 반환한 문자열 형식을 유지한다. boolean 집계값인 `ancestorDisplayNone`만 JSON boolean으로 전달한다.

| 키 | 기대 값 예시 | 설명 |
|---|---|---|
| `opacity` | `"0"`, `"0.5"`, `"1"` | 요소 자신의 opacity, 문자열 범위 0~1 |
| `ancestorOpacity` | `"0"`~`"1"` | 요소 자신과 조상들의 opacity 누적 곱 |
| `color` | `"rgb(0, 0, 0)"`, `"rgba(0, 0, 0, 0)"` | 계산된 글자색 |
| `backgroundColor` | `"rgb(...)"`, `"rgba(...)"` | 요소 자신의 계산된 배경색 |
| `effectiveBackground` | `"rgb(...)"`, `"rgba(...)"` | 실제로 글자 뒤에 보이는 불투명 배경색 |
| `fontSize` | `"14px"` | 계산된 글자 크기 |
| `display` | `"block"`, `"none"` | 요소 자신의 display |
| `ancestorDisplayNone` | `true`, `false` | 조상 중 `display:none` 존재 여부 |
| `visibility` | `"visible"`, `"hidden"` | 계산된 visibility |
| `position` | `"static"`, `"absolute"`, `"fixed"` | 계산된 position |
| `left`, `top` | `"auto"`, `"-9999px"` | 계산된 위치 |
| `clip` | `"auto"`, `"rect(0px, 0px, 0px, 0px)"` | 계산된 clip |
| `clipPath` | `"none"`, `"inset(50%)"` | 계산된 clip-path |
| `overflow` | `"visible"`, `"hidden"`, `"clip"` | 계산된 overflow |
| `textIndent` | `"0px"`, `"-9999px"` | 계산된 text-indent |
| `width`, `height` | `"120px"`, `"1px"` | 계산된 요소 크기 |

## `effectiveBackground` 계산 규칙

1. 요소 자신의 `backgroundColor`가 불투명이면 그 색을 사용한다.
2. 투명하거나 알파가 0이면 부모 방향으로 올라가며 처음 만나는 불투명 배경색을 사용한다.
3. `html`까지 불투명 배경이 없으면 브라우저 기본 캔버스 배경을 **흰색 `rgb(255, 255, 255)`으로 가정**한다.
4. 계산 결과는 반드시 `effectiveBackground`에 `rgb(...)` 또는 `rgba(...)` 문자열로 전달한다.

A는 투명한 `backgroundColor`만 전달되고 `effectiveBackground`가 없으면 명암비를 확정할 수 없으므로, 색상 대비만으로 TRANSPARENT 판정을 내리지 않는다.

## JSON 예시

```json
{
  "url": "https://example.go.kr/page",
  "location": "div.ad > span",
  "frame_path": ["https://example.go.kr/frame"],
  "text": "카지노 첫충",
  "context": "이벤트 안내",
  "style": {
    "opacity": "1",
    "ancestorOpacity": "1",
    "color": "rgb(255, 255, 255)",
    "backgroundColor": "rgba(0, 0, 0, 0)",
    "effectiveBackground": "rgb(255, 255, 255)",
    "fontSize": "14px",
    "display": "block",
    "ancestorDisplayNone": false,
    "visibility": "visible",
    "position": "static",
    "left": "auto",
    "top": "auto",
    "clip": "auto",
    "clipPath": "none",
    "overflow": "visible",
    "textIndent": "0px",
    "width": "120px",
    "height": "20px"
  },
  "bbox": {"x": 20, "y": 100, "width": 120, "height": 20}
}
```
