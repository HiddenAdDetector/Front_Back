# AdSentinel

공공 웹사이트를 Playwright로 탐색하고 DOM/CSS 정보를 수집한 뒤, 불법광고 탐지 모델과 연동하는 React + Spring Boot 프로젝트입니다.

## 프로젝트 구조

```text
AdSentinel/
├─ frontend/        React + TypeScript + Vite 실시간 대시보드
├─ backend-spring/  Spring Boot + Java Playwright 크롤러/API
├─ Detection_Engine/ 탐지 CLI 배포 위치 및 계약 문서
├─ docs/             협업 문서
├─ output/           로컬 실행 결과 폴더
└─ .gitignore
```

## 역할 분담

| 영역 | 폴더 | 역할 |
|---|---|---|
| 프론트엔드 | `frontend/` | URL 입력, 실시간 상태, 브라우저 캡처, 로그, 리포트 |
| 크롤러·백엔드 | `backend-spring/` | Playwright, 다중 페이지, iframe, DOM/CSS, API |
| 탐지 모델 | `backend-spring/src/main/java/com/adsentinel/detector/` | 기법별 확정 판정 |
| 결과 저장 | `backend-spring/src/main/java/com/adsentinel/result/` | 제출 JSON과 리포트 저장 |

## 요구사항

- Java 17 이상
- Maven 3.9 이상 또는 IntelliJ IDEA
- Node.js 18 이상
- npm
- Playwright Chromium

## 실행 방법

### 제출용 통합 실행

`submission/AdSentinel` 폴더에서 `START.bat`을 실행하면 내장 서버와 화면이 함께 시작됩니다. 별도의 Node.js, Python, Java 설치는 필요하지 않습니다. 탐지 완료 후 `result.json`은 `START.bat`과 같은 폴더에 생성됩니다.

개발 환경에서는 아래 방법을 사용합니다.

백엔드:

```powershell
cd backend-spring
mvn spring-boot:run
```

IntelliJ에서는 `backend-spring/pom.xml`을 Maven 프로젝트로 불러온 뒤 `AdSentinelApplication`을 실행합니다.

프론트엔드:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

브라우저에서 `http://127.0.0.1:5173`을 엽니다. 백엔드는 `http://127.0.0.1:8080`에서 실행되어야 합니다.

## API

```text
GET  /api/health
POST /api/crawl
GET  /api/crawl/{jobId}
POST /api/crawl/{jobId}/stop
```

탐색 시작 요청:

```json
{ "url": "https://example.com" }
```

요소 데이터는 `url`, `location`, `framePath`, 원문 `text`, `context`, `style`, `bbox`, `visible`, `hiddenReasons`, `frameUrl`을 사용합니다.

탐지 결과는 `id`, `url`, `is_violation`, `location`, `evidence_text`, `technique`, `extra_finding`을 사용합니다. 허용 기법은 `HOMOGLYPH`, `JAMO`, `TRANSPARENT`, `OFFSCREEN`, `ETC`입니다.

## 탐지 상태

Python detector CLI 연결 후에는 Spring이 전체 크롤링 완료 뒤 CLI를 한 번 호출합니다. Gemini API 키가 없으면 Python 엔진의 규칙 판정으로 동작하고, `.env`에 키가 있으면 애매한 후보에 선택적으로 AI 판정을 수행합니다.

```text
report_type: detection_report
model_status: python_cli_connected
review_required: false
```

팀원 모델은 `Detection_Engine/detector_cli.exe`로 배치합니다. 개발 시에는 `detector_cli.py`를 사용합니다. B는 전체 크롤링 후 `elements.json`을 작성하고 CLI를 한 번 실행합니다. CLI가 `result.json`을 생성하며 B는 해당 파일을 다시 작성하지 않습니다.

## 출력 파일

제출용 통합 실행에서는 `START.bat`과 같은 폴더에 다음 파일이 생성됩니다.

- `result.json`: 공모전 제출용 결과
- `report.json`: 후보/확정 리포트, 기법별 통계, 탐색 종료 사유

원문과 결과 JSON에는 사이트 데이터가 포함될 수 있으므로 Git에 커밋하지 않습니다.

## 빌드 및 커밋 전 확인

```powershell
cd frontend
npm run build

cd ..\backend-spring
mvn clean package -DskipTests

cd ..
git status
git add README.md .gitignore frontend backend-spring docs
git commit -m "chore: organize frontend and spring backend"
git push origin main
```

`node_modules`, `dist`, `target`, `.idea`, `.venv`, 결과 JSON은 `.gitignore`로 제외됩니다.
