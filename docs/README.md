# AdSentinel Documentation

프로젝트 협업 문서를 보관하는 폴더입니다.

## 협업 규칙

1. 프론트엔드는 `frontend/`에서 작업합니다.
2. Spring Boot와 Playwright는 `backend-spring/`에서 작업합니다.
3. 탐지 모델은 `backend-spring/src/main/java/com/adsentinel/detector/`의 `Detector` 계약을 지킵니다.
4. 생성된 `target/`, `node_modules/`, `dist/`, 결과 JSON은 커밋하지 않습니다.
5. API 계약을 변경하면 루트 `README.md`와 해당 폴더 README를 함께 수정합니다.
