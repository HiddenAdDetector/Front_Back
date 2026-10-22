# AdSentinel Frontend

React + TypeScript + Vite 기반의 실시간 모니터링 화면입니다.

## 담당 범위

- 탐색 URL 입력 및 시작·중지
- Playwright 현재 URL과 브라우저 캡처 표시
- 방문·대기·실패 페이지와 추출 요소 통계 표시
- 실시간 로그와 후보 탐지 결과 표시
- 후보/확정 탐지 리포트 표시

## 실행

```powershell
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

브라우저에서 `http://127.0.0.1:5173`을 엽니다. 백엔드는 `http://127.0.0.1:8080`에서 실행되어야 합니다.

## 빌드

```powershell
npm run build
```

## 주요 파일

- `src/App.tsx`: API polling, 모니터링 화면, 리포트 화면
- `src/styles.css`: JAWS 스타일을 참고한 대시보드 UI
- `src/main.tsx`: React 진입점

백엔드 결과 계약은 `technique`, `url`, `location`, `evidence_text` 필드를 사용합니다.
