# kiwoom-rest-agent 제거 이력

## 1. 기존 역할

`kiwoom-rest-agent`는 DrCT에셋 프로젝트 초기 단계에서 Kiwoom 조건검색 및 Kiwoom 관련 API 연동 테스트/실행 보조 역할을 수행했다.

## 2. 제거 사유

현재 DrCT에셋의 Kiwoom 관련 주요 기능은 FastAPI 백엔드 내부 provider/service 구조로 이전되었다.

현재 대체 구조는 다음과 같다.

### 가격·캔들 수집
- Backend 내부 Kiwoom REST provider 사용
- 운영 source: `kiwoom_rest`

### 시장지표 수집
- Backend 내부 Kiwoom REST provider 사용
- 화면 조회는 DB 조회 전용 구조

### 조건검색 목록/결과 조회
- Backend 내부 WebSocket provider 사용
- 목록 조회: `LOGIN -> CNSRLST`
- 결과 조회: `LOGIN -> CNSRLST warmup -> CNSRREQ`

## 3. 삭제 판단 근거

- backend에서 `kiwoom-rest-agent` 실행 의존 없음
- frontend에서 agent output 직접 참조 없음
- scripts에서 agent 실행 의존 없음
- 조건검색 목록/결과 조회가 내부 WebSocket provider로 전환됨
- 가격·캔들/시장지표 수집이 backend 내부 provider로 전환됨
- runtime data, raw dump, token 응답 파일은 Git 추적 대상이 아님

## 4. 삭제 후 검증

삭제 후 다음 검증을 수행했다.

- `python scripts/check_db_health.py`
- `python -m compileall backend/app`
- `cd frontend && npm run build`
- agent 관련 참조 검색

## 5. 주의 사항

- 자동매매/주문 API는 추가하지 않는다.
- token/appkey/secretkey 원문은 저장/노출하지 않는다.
- SQLite DB, DB 백업, raw dump, runtime output은 Git에 올리지 않는다.
