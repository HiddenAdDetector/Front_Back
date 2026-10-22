# AdSentinel Spring Boot Backend

Spring Boot 3 + Java Playwright 기반의 웹 탐색·DOM/CSS 수집 서버입니다.

## 담당 범위

- 동일 호스트 내부 페이지 탐색
- iframe 포함 DOM/CSS 수집
- 원문 textContent, 문맥, 선택자, 스타일, 좌표 수집
- 실시간 탐색 상태·로그·스크린샷 제공
- 규칙 기반 후보 탐지
- 팀원 탐지 모델 연동 지점 제공
- `result.json`, `result_extra.json`, `report.json` 저장

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

현재 `MockDetector`는 모델 연결 전 후보 생성용입니다. 팀원 모델은 `Detector` 인터페이스를 구현하거나 REST 어댑터로 연결합니다.

모델 연결 전 결과는 `candidate_detection_report`이며, 최종 제출 전에는 모델 확정 결과만 `result.json`에 포함해야 합니다.

## 출력

실행 위치 기준 `output/`에 다음 파일이 생성됩니다.

- `result.json`: 공모전 제출 형식
- `result_extra.json`: 추가 결과
- `report.json`: 후보 수, 기법별 통계, 종료 사유, 모델 연결 상태

생성 결과 파일은 `.gitignore`로 제외합니다. 개인정보나 사이트 원문이 포함될 수 있으므로 Git에 올리지 않습니다.
