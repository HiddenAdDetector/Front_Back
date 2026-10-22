# AdSentinel Spring Boot Backend

Spring Boot 3 + Java Playwright 기반의 웹 탐색·DOM/CSS 수집 서버입니다.

## 담당 범위

- 동일 호스트 내부 페이지 탐색
- iframe 포함 DOM/CSS 수집
- 원문 textContent, 문맥, 선택자, 스타일, 좌표 수집
- 실시간 탐색 상태·로그·스크린샷 제공
- 규칙 기반 후보 탐지
- 팀원 탐지 모델 연동 지점 제공
- Python `detector_cli`가 `result.json`을 저장하고 Spring이 `report.json`을 저장

## 실행 환경

- Java 17 이상
- Maven 3.9 이상 또는 IntelliJ Maven
- Playwright Java 1.42.0
- Chromium 브라우저 설치 필요

## 실행

```powershell
cd backend-spring
mvn spring-boot:run
```

IntelliJ에서는 `pom.xml`을 Maven 프로젝트로 불러온 뒤 `AdSentinelApplication`을 실행합니다.

기본 주소:

```text
http://127.0.0.1:8080
```

## API

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/health` | 서버 상태 확인 |
| POST | `/api/crawl` | 탐색 시작, `{ "url": "https://example.com" }` |
| GET | `/api/crawl/{jobId}` | 실시간 상태 조회 |
| POST | `/api/crawl/{jobId}/stop` | 탐색 중지 |

## 패키지 구조

- `api`: REST Controller
- `crawler`: Playwright 탐색과 ElementRecord 수집
- `detector`: `Detector` 인터페이스와 현재 규칙 기반 후보 탐지기
- `result`: 공모전 JSON과 리포트 저장

## 탐지 모델 연동

탐지 모델은 Python CLI(`detector_cli`)를 Java `ProcessBuilder`로 호출합니다. `MockDetector`는 연동 경로에서 사용하지 않습니다.

크롤링 중에는 페이지별 탐지 호출을 하지 않습니다. 전체 크롤링이 끝나면 다음 순서로 한 번만 실행합니다.

```text
output/elements.json
  → detector_cli.exe --input ... --out-dir ... --cancel-file ... --deadline-sec ...
  → output/result.json
```

기본 CLI 경로는 `Detection_Engine/detector_cli.py`이며 `detector.cli.path`로 변경할 수 있습니다. 배포 시 같은 위치의 `detector_cli.exe`를 사용하며, `.env`와 API 키는 저장소에 커밋하지 않고 `.env.example`만 공유합니다.

CLI 연결 후 `detection_report`가 생성되며, A가 작성한 strict schema `result.json`을 최종 결과로 사용합니다.

## 출력

실행 위치 기준 `output/`에 다음 파일이 생성됩니다.

- `result.json`: 공모전 제출 형식
- `report.json`: 후보 수, 기법별 통계, 종료 사유, 모델 연결 상태

생성 결과 파일은 `.gitignore`로 제외합니다. 개인정보나 사이트 원문이 포함될 수 있으므로 Git에 올리지 않습니다.
