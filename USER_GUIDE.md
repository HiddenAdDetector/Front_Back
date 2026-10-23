# AdSentinel 사용설명서

## 결과 파일 생성 위치

`result.json`은 `START.bat`, `AdSentinel.jar`, `detector_cli.exe`가 있는 실행 폴더에 생성됩니다.

같은 위치에 업무 확인용 `report.json`, 탐지 입력 자료 `elements.json`, AI 운영 로그 `detect_log.jsonl`도 생성될 수 있습니다.

## 실행 방법

1. Windows 11에서 압축 파일 전체를 한 폴더에 풉니다.
2. 필요하면 `.env.example`을 `.env`로 복사하고 `GEMINI_API_KEY`를 입력합니다. API 키가 없어도 규칙 기반 탐지는 정상 동작합니다.
3. `START.bat`을 더블 클릭합니다.
4. 잠시 후 기본 브라우저에서 `http://127.0.0.1:8080` 화면이 자동으로 열립니다.
5. 점검할 웹사이트의 진입 URL 하나를 입력하고 `탐색 시작`을 누릅니다.
6. 탐지가 완료되면 화면에서 결과를 확인하고 실행 폴더의 `result.json`을 확인합니다.

프로그램 실행 중 표시되는 콘솔 창을 닫으면 서버가 종료됩니다.

## 탐지 기능

- `HOMOGLYPH`: 닮은꼴 문자 및 전각 문자 위장
- `JAMO`: 한글 자모 분해
- `TRANSPARENT`: 투명도, 투명 색상, 배경색과 같은 글자색
- `OFFSCREEN`: 화면 밖 좌표, 0~1px 글자, `display:none`, 클리핑

하위 페이지, 게시글, 댓글 요소 및 중첩 iframe 내부 요소를 탐색하며, 결과 위치는 CSS 선택자로 기록합니다.

## 상용 AI API 설정

- 서비스명: Google Gemini API
- 기본 모델명: `gemini-3.5-flash-lite`
- API 키 환경변수: `GEMINI_API_KEY`
- 모델 환경변수: `GEMINI_MODEL`

키는 `.env` 외부 설정 파일에서 실행 시점에 읽으므로 재빌드 없이 교체할 수 있습니다. 키가 없거나 API 연결에 실패하면 규칙 기반 판정으로 자동 전환됩니다.

## 종료 및 문제 해결

- 실행이 되지 않으면 세 파일 `START.bat`, `AdSentinel.jar`, `detector_cli.exe`가 같은 폴더에 있는지 확인합니다.
- 포트 8080을 다른 프로그램이 사용 중이면 해당 프로그램을 종료한 후 다시 실행합니다.
- Windows 보안 경고가 표시되면 압축을 완전히 해제했는지 확인한 뒤 실행을 허용합니다.
- 출력 파일이 열려 있으면 덮어쓰기가 실패할 수 있으므로 편집기에서 닫은 뒤 다시 탐지합니다.
내