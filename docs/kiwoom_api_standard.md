# Kiwoom API Standardization Guide (38-A-3)

## 1) 목적
- 키움 API 코드 분산을 방지하고, DrCT 운영 코드에서 사용할 표준 구조를 정의한다.
- `kiwoom-rest-agent`와 `drct-asset-office`의 역할 경계를 명확히 한다.
- 가격/캔들, 순위, 조건검색, 테마/업종 흐름이 같은 공통 Client 계층을 사용하도록 설계한다.

## 2) 역할 분리 원칙
### 2.1 `kiwoom-rest-agent` 역할
- 실험/검증 전용 PoC Agent
- 인증/토큰 검증, API ID별 샘플 호출, raw/normalized 응답 저장, 호출 제한 탐색
- 신규 TR/API 사전 검증 후 DrCT 운영 모듈로 이관 대상 확정

### 2.2 `drct-asset-office` 역할
- 운영 서비스 코드
- DB 저장/중복 처리/수집 이력/화면 API 제공
- `kiwoom-rest-agent`를 직접 import하지 않음 (프로세스 실행은 허용)

### 2.3 금지
- `drct-asset-office`에서 `kiwoom-rest-agent/app/*` 직접 import 금지
- 주문 API 구현 금지
- 토큰 원문 로그 출력 금지

## 3) 현재 구현 조사 결과
## 3.1 Kiwoom 관련 주요 파일 (운영 코드)
- `backend/app/api/routes_external_kiwoom.py`
- `backend/app/services/external_kiwoom_service.py`
- `backend/app/schemas/external_kiwoom_schema.py`
- `backend/app/api/routes_kiwoom.py` (38-A POC)
- `backend/app/services/kiwoom_market_data_poc_service.py` (38-A POC)
- `backend/app/providers/market_data/kiwoom_rest_provider.py` (38-A POC)
- `backend/app/clients/kiwoom_rest_client.py` (38-A POC)
- `backend/app/schemas/kiwoom_schema.py` (38-A POC)

## 3.2 Kiwoom 관련 주요 파일 (Agent)
- `kiwoom-rest-agent/app/kiwoom_rest_client.py`
- `kiwoom-rest-agent/app/auth_client.py`
- `kiwoom-rest-agent/app/condition_client.py`
- `kiwoom-rest-agent/app/rank_client.py`
- `kiwoom-rest-agent/app/ws_client.py`
- `kiwoom-rest-agent/run_condition_list.py`
- `kiwoom-rest-agent/run_condition_once.py`

## 3.3 시장 트랜드 분석 화면의 실제 호출 경로
- Frontend: `frontend/src/pages/MarketTrendsPage.tsx`
- API Repository: `frontend/src/services/api/marketTrendApiRepository.ts`
- Backend Route: `backend/app/api/routes_external_kiwoom.py`
- Backend Service: `backend/app/services/external_kiwoom_service.py`
- 핵심 특징:
  - 조건검색 preview는 백엔드가 `kiwoom-rest-agent/run_condition_once.py`를 subprocess로 실행
  - 즉, 현재 시장 트랜드 조건검색은 DrCT 내부 Kiwoom REST Client가 아니라 Agent 런타임에 의존

## 4) 중복 분석 (기존 vs 38-A)
## 4.1 중복 기능
- 공통 헤더 개념 중복
  - `authorization: Bearer`
  - `api-id`
  - `cont-yn`, `next-key`
- 응답 파싱/에러 처리 책임 중복
- 종목코드 정규화와 수치 정규화 책임 중복

## 4.2 차이점
- Agent Client (`kiwoom-rest-agent/app/kiwoom_rest_client.py`)
  - 토큰을 인자로 받아 사용
  - `requests.Session` + `use_proxy` 제어
  - 주문 API ID 차단
- 38-A POC Client (`backend/app/clients/kiwoom_rest_client.py`)
  - `.env` 기반 토큰 사용
  - 간단 rate limit(throttle) 내장
  - POC 일봉 경로 중심
- 시장 트랜드 서비스
  - 직접 REST 호출보다 Agent subprocess 호출 방식

## 4.3 위험 요소
- 동일 책임(헤더/에러/rate limit)이 두 군데 이상에 존재
- 한쪽 수정 시 다른 경로 반영 누락 가능
- 조건검색(WebSocket)과 REST 일봉이 서로 다른 진입점으로 운영되어 장애 원인 추적이 어려움

## 5) 표준 폴더 구조 제안
```text
backend/app/clients/kiwoom/
  __init__.py
  kiwoom_rest_client.py
  kiwoom_auth_client.py
  kiwoom_rate_limiter.py
  kiwoom_errors.py
  kiwoom_models.py

backend/app/providers/market_data/
  __init__.py
  base_market_data_provider.py
  kiwoom_price_provider.py
  kiwoom_market_indicator_provider.py
  kiwoom_ranking_provider.py
  kiwoom_sector_provider.py
  pykrx_legacy_provider.py
  kis_legacy_provider.py

backend/app/services/kiwoom/
  __init__.py
  kiwoom_market_data_poc_service.py
  kiwoom_price_collection_service.py
  kiwoom_market_trend_service.py
  kiwoom_token_service.py

scripts/kiwoom/
  test_kiwoom_auth.py
  test_kiwoom_daily_price.py
  test_kiwoom_market_index.py
  test_kiwoom_rate_limit.py
```

## 6) 표준 Client 결정안
## A안
- 38-A 신규 Client를 표준으로 채택, 시장 트랜드 경로를 점진 이관

## B안
- Agent Client를 표준으로 채택, DrCT 내부로 재배치 후 재사용

## C안 (권장)
- `backend/app/clients/kiwoom/`에 통합 표준 Client 신규 정의
- 38-A Client와 Agent Client의 장점을 흡수
  - 38-A의 rate limit/throttle + POC 친화
  - Agent의 proxy 제어 + 주문 API 차단 + 로깅 기준
- 기존 두 구현은 즉시 삭제하지 않고 어댑터 방식으로 단계 이관

## 7) 표준 Client 필수 요구사항
- base/mock URL 선택
- access token/header 구성
- `api-id`, `cont-yn`, `next-key` 처리
- timeout/rate limit
- HTTP/JSON 파싱 오류 코드화
- 키움 에러 코드 매핑
- raw response preview 로깅
- 민감정보 마스킹

## 8) 단계별 전환 로드맵
## 38-A-4 (통합 준비)
- `backend/app/clients/kiwoom/*` 신규 생성
- 공통 에러/모델/rate limiter 분리
- 기존 38-A client는 wrapper로 유지

## 38-B (저장 POC)
- 일봉 mapped row를 `stock_daily_prices`로 저장하는 옵션형 경로 추가
- `save=false` 기본 유지

## 38-C (가격/캔들 수집 연동)
- `stock_price_service`에 `source=kiwoom_rest` 선택 경로 추가
- 기존 `pykrx` 기본값 유지

## 38-D (시장트랜드 점진 이관)
- 조건검색 preview subprocess 경로를 유지하되
- 저장/후처리 단계는 통합 Client/Service 경로로 수렴

## 9) 현 단계 결론
- `kiwoom-rest-agent`: 실험/검증 전용으로 유지
- `drct-asset-office`: 운영 코드 표준화 대상
- 현재는 중복 구조가 존재하며, 안전한 방향은 C안(통합 Client 신설 + 점진 이관)
- 이번 단계는 설계/문서화 완료, 대규모 파일 이동/삭제는 사용자 승인 후 진행

## 10) 38-A-4 적용 사항 (표준 Client 골격)
- 신규 표준 경로 생성:
  - `backend/app/clients/kiwoom/kiwoom_rest_client.py`
  - `backend/app/clients/kiwoom/kiwoom_auth_client.py`
  - `backend/app/clients/kiwoom/kiwoom_rate_limiter.py`
  - `backend/app/clients/kiwoom/kiwoom_errors.py`
  - `backend/app/clients/kiwoom/kiwoom_models.py`
- legacy 호환 유지:
  - `backend/app/clients/kiwoom_rest_client.py`는 삭제하지 않고 wrapper로 유지
- 38-A POC provider는 표준 client 패키지를 직접 사용하도록 전환

## 11) 주문 API 차단 정책
- 기본값: `KIWOOM_REST_BLOCK_ORDER_API=true`
- 차단 방식:
  - 주문성 API ID 목록(`kt10000~kt10009` 등) 호출 시 즉시 예외
  - 오류 코드: `KIWOOM_ORDER_API_BLOCKED`
- 원칙:
  - DrCT 운영 경로에서 주문/자동매매 기능은 구현하지 않음

## 12) 시장 트랜드 이관 계획 (subprocess 유지 후 단계 전환)
1. 현재: `external_kiwoom_service`가 agent 스크립트를 subprocess로 실행
2. 1차: 표준 client 기반 provider에 condition/rank 호출 로직 복제
3. 2차: `external_kiwoom_service`가 subprocess 대신 provider 호출
4. 3차: `kiwoom-rest-agent`는 실험 전용으로 축소
5. 4차: 미사용 agent 파일은 사용자 승인 후 archive/delete

## 13) 삭제/롤백 원칙
- 사용자 승인 없는 삭제/롤백 금지
- 기존 경로는 wrapper/adapter 형태로 유지한 뒤 단계적 이관
