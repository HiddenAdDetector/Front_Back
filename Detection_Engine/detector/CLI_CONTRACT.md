# AdSentinel CLI 연동 계약

## 실행

개발 환경:

```text
python detector_cli.py --input samples/b_elements_sample.json --out-dir output
```

배포 환경:

```text
detector_cli.exe --input elements.json --out-dir output
```

`--input`은 필수다. `--out-dir`을 생략하면 스크립트 또는 exe가 있는 폴더에 저장한다.

옵션:

- `--entry-url URL`, `--started-at ISO-8601`: 명령행 값이 입력 JSON 값보다 우선한다. 둘 다 없으면 각각 첫 유효 요소 URL과 현재 KST 시각을 쓴다.
- `--deadline-sec N`: N초가 지나면 취소 플래그를 세우고 확보한 결과만 저장한다. 생략 시 공모전 30분 상한보다 짧은 1700초를 적용한다.
- `--cancel-file PATH`: 해당 파일이 생겼는지 0.5초마다 확인하고, 발견하면 부분 결과를 저장한다. Windows에서 강제 종료 대신 이 방식을 사용한다.
- `--no-ai`: Gemini를 호출하지 않고 규칙 판정만 수행한다.
- `--topic`, `--tool-version`: 결과 메타데이터를 지정한다. 기본 topic은 기존 `TOPIC` 상수와 같다.

`.env`는 exe 또는 스크립트와 같은 폴더에서 읽는다. `GEMINI_API_KEY`가 없으면 오류가 아니라 자동으로 규칙 판정만 수행한다.

## 입력 JSON

객체 형식과 최상위 배열 형식을 모두 지원한다.

```json
{
  "entry_url": "https://www.example.go.kr/",
  "started_at": "2026-10-22T09:00:00+09:00",
  "elements": [
    {
      "url": "https://www.example.go.kr/page",
      "location": "main > span.banner",
      "framePath": "https://www.example.go.kr/widget",
      "text": "ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ",
      "context": "배너 주변 문맥",
      "style": {"opacity": "0", "fontSize": "14px"},
      "bbox": {"x": 10, "y": 20, "width": 150, "height": 20},
      "visible": false,
      "hiddenReasons": ["opacity"]
    }
  ]
}
```

`frame_path`와 `framePath`를 모두 허용한다. 문자열 하나는 한 항목짜리 목록으로 처리한다. `style`, `bbox`, `context`가 없으면 빈 값으로 처리하며 알 수 없는 필드는 무시한다. 잘못된 요소 하나는 경고 후 건너뛴다.

`frame_path`는 바깥 iframe부터 안쪽 iframe까지의 절대 URL 목록이고, `location`은 현재 iframe 문서 내부의 유일한 CSS 선택자여야 한다. A가 최종 결과에서 `iframe[src="..."] >>> 선택자`로 결합한다. 같은 선택자가 여러 요소를 가리키면 채점 오답이 될 수 있다.

`div`, `span`, `p`, `a`처럼 공통 태그명만 사용해 한 요소를 특정할 수 없는 `location`은 입력에서 제외한다. B는 클래스, ID, 속성 또는 `:nth-of-type()` 등을 포함한 고유 선택자를 전달해야 한다.

## stdout과 stderr

stdout은 UTF-8 JSON Lines이며 모든 줄을 독립 JSON으로 파싱해야 한다.

```json
{"type":"progress","state":"rule","done":1,"total":2}
{"type":"progress","state":"done","done":2,"total":2}
{"type":"result","path":"C:\\work\\output\\result.json","findings":1,"cancelled":false,"ai_used":false}
```

마지막 stdout 줄은 항상 `type=result`다. 사람이 읽는 경고와 오류는 stderr로만 출력한다. API 키는 어느 출력이나 로그에도 기록하지 않는다.

## 출력과 종료 코드

- `<out-dir>/result.json`: `meta`, `findings`를 포함한다. finding은 `id`, `url`, `is_violation`, `location`, `evidence_text`, `technique` 여섯 필드만 가진다.
- `<out-dir>/detect_log.jsonl`: AI 운영 로그다. AI를 쓰지 않으면 빈 파일일 수 있다.
- `0`: 정상 완료. 취소와 제한시간 만료 후 부분 저장도 포함한다.
- `1`: 예기치 못한 오류. 가능한 경우 빈 결과 또는 부분 결과를 저장한다.
- `2`: 입력 JSON 오류 또는 빈 `elements`. 빈 `result.json`을 저장한다.

## Java ProcessBuilder 예시

```java
Path cancelFile = outputDir.resolve("cancel.request");
ProcessBuilder builder = new ProcessBuilder(
    detectorExe.toString(),
    "--input", elementsJson.toString(),
    "--out-dir", outputDir.toString(),
    "--deadline-sec", "1500",
    "--cancel-file", cancelFile.toString()
);
Process process = builder.start();

// stdout(JSONL)과 stderr는 별도 스레드에서 동시에 끝까지 읽어 교착을 방지한다.
// 사용자가 중지를 누르면 Files.createFile(cancelFile)을 호출하고 프로세스를 기다린다.
int exitCode = process.waitFor();
```

중지 파일은 실행 전에 존재하지 않아야 한다. 새 실행 전 이전 파일을 지우고, 실행 중 중지 요청이 있을 때만 생성한다.
