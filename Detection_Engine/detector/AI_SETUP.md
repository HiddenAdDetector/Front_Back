# Google Gemini API 설정

## 사용 서비스

- 서비스명: Google Gemini API
- SDK: `google-genai`
- 기본 모델: `gemini-3.5-flash-lite`
- 모델 교체: `.env`의 `GEMINI_MODEL` 값만 변경하며 재빌드하지 않는다.

설치 명령:

```powershell
python -m pip install google-genai python-dotenv
```

## 환경변수

| 이름 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `GEMINI_API_KEY` | AI 사용 시 필수 | 없음 | Gemini API 키. 소스코드와 로그에 저장하지 않는다. |
| `GEMINI_MODEL` | 선택 | `gemini-3.5-flash-lite` | 호출할 Gemini 모델 ID |
| `GEMINI_TIMEOUT_SEC` | 선택 | `20` | 요청 제한시간(초) |
| `GEMINI_BATCH_SIZE` | 선택 | `20` | API 요청 한 번에 전달할 최대 후보 수 |
| `GEMINI_MAX_CALLS` | 선택 | `30` | 한 번의 탐지 작업에서 허용할 최대 실제 API 호출 수(재시도 포함) |
| `GEMINI_MIN_CONFIDENCE` | 선택 | `0.7` | 광고 판정을 승격할 최소 신뢰도 |
| `GEMINI_TOTAL_BUDGET_SEC` | 선택 | `120` | 재시도와 대기를 포함한 AI 단계 전체 시간 예산(초) |

## `.env` 위치와 예시

`.env`는 실행 파일 또는 실행 스크립트와 같은 폴더에 둔다. PyInstaller 실행 환경에서는 `sys.executable`이 있는 폴더에서 읽는다. 키만 교체해 재빌드 없이 사용할 수 있다.

```dotenv
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT_SEC=20
GEMINI_BATCH_SIZE=20
GEMINI_MAX_CALLS=30
GEMINI_MIN_CONFIDENCE=0.7
GEMINI_TOTAL_BUDGET_SEC=120
```

키가 비어 있거나 SDK·네트워크·API 응답에 문제가 있으면 AI 호출 없이 규칙 결과를 반환한다. API 키는 콘솔, 예외 메시지, `detect_log.jsonl`에 기록하지 않는다.

Gemini에는 후보 ID, 앞 300자의 정규화 텍스트, 앞 300자의 주변 문맥, 규칙으로 확인된 은닉 기법만 전송한다. URL과 전체 페이지 내용은 전송하지 않는다. AI 결과와 오류·호출 상한 이벤트는 실행 파일 또는 스크립트 폴더의 `detect_log.jsonl`에 기록하며, `result.json` 스키마에는 AI 전용 필드를 추가하지 않는다.

진행 콜백의 `state` 값은 `rule`, `ai`, `done`이다. 콜백 자체의 오류는 탐지를 중단시키지 않는다.

AI 전체 시간이 `GEMINI_TOTAL_BUDGET_SEC`를 넘으면 진행 중 호출을 기다리지 않고 그때까지 검증된 결과만 반환한다. 남은 후보는 규칙 판정을 유지하며 `ai_budget_exhausted` 이벤트를 로그에 남긴다.
