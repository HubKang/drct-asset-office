# DrCT에셋 (drct-asset-office)

## 1. 프로젝트 개요
DrCT에셋은 **자동매매가 아닌 투자 자문 보조 시스템**입니다.  
국내주식 데이터(가격/캔들, 시장지표, 뉴스/공시, 조건검색 결과)를 수집·저장하고, 저장 데이터를 기반으로 GPT 자문 패키지를 생성합니다.

핵심 원칙:
- 자동 매수/매도 기능 미구현
- 주문 API 미연동
- 최종 투자 판단은 사용자 책임

---

## 2. 현재 아키텍처 (2026-05 기준)

### 2.1 기술 스택
- Backend: Python + FastAPI
- Frontend: React + Vite + TypeScript
- Database: SQLite
- 국내주식 데이터 원천:
  - 가격/캔들: Kiwoom REST
  - 시장지표: Kiwoom REST
  - 조건검색: Kiwoom WebSocket (`LOGIN -> CNSRLST`, `CNSRREQ`)
- LLM:
  - 로컬 LLM(LM Studio): 단건 요약 보조
  - GPT: 최종 투자 검토/자문 패키지

### 2.2 백엔드 구조 요약
- API 라우터: `backend/app/api/*`
- 서비스 계층: `backend/app/services/*`
- Provider/Collector 계층:
  - `backend/app/providers/market_data/kiwoom_rest_provider.py`
  - `backend/app/providers/market_data/kiwoom_rest_market_indicator_provider.py`
  - `backend/app/providers/market_data/kiwoom_rest_condition_provider.py`
- 저장소/엔티티:
  - `backend/app/repositories/*`
  - `backend/app/entities/*`

### 2.3 프론트 주요 화면(메뉴명 기준)
- `관심종목 Data수집` (`/watchlist`)
- `관심종목 Data분석` (`/stock-prices`)
- `시장 테마 관리` (`/market-themes`)
- `시장 트렌드 분석` (`/market-trends`)
- `GPT 자문 패키지` (`/advisory-packages`)

라우트 정의: `frontend/src/router/routeRegistry.tsx`

---

## 3. 데이터 흐름 원칙

### 3.1 수집과 조회 분리
- **수집은 POST collect API 또는 명시적 버튼 동작에서만 수행**
- **GET 조회 API는 외부 Kiwoom API를 직접 호출하지 않음**

### 3.2 조건검색(내재화 완료)
- 목록 조회: `POST /external/kiwoom/conditions/refresh`
- 결과 조회: `POST /external/kiwoom/conditions/{condition_seq}/preview`
- 실행 경로: `routes_external_kiwoom -> external_kiwoom_service -> kiwoom_rest_condition_provider`
- 기존 `kiwoom-rest-agent` subprocess 의존 제거

### 3.3 가격/시장지표 운영 source
- 가격/캔들 기본 source: `kiwoom_rest`
- 시장지표 기본 source: `kiwoom_rest`
- 가격·기술지표·시장지표는 DB 저장 후 화면에서 조회

---

## 4. 저장 구조 핵심

주요 테이블(요약):
- `stocks`
- `watchlist`
- `stock_daily_prices`
- `stock_daily_technical_indicators`
- `stock_daily_market_metrics`
- `news_items`
- `disclosures`

참고:
- `stock_daily_prices.trading_value` 단위는 **백만** 기준
- 화면에서 거래대금(억원) 표시는 `trading_value / 100`

---

## 5. 실행 방법

## 5.1 백엔드
```bash
python scripts/init_db.py
uvicorn backend.app.main:app --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## 5.2 프론트엔드
```bash
cd frontend
npm install
npm run dev
```

- 접속: `http://127.0.0.1:5173`

---

## 6. 검증 명령 (권장)

```bash
python -m compileall backend/app
python scripts/check_db_health.py
cd frontend && npm run build
git status --short
```

---

## 7. Git/보안 운영 규칙

- 절대 커밋 금지:
  - 토큰 응답/테스트 파일
  - raw/normalized dump
  - SQLite DB/백업
  - 런타임 산출물/로그/캐시
- 민감정보(`token`, `appkey`, `secretkey`) 원문 출력 금지
- 사용자 승인 없는 롤백 금지:
  - `git reset`
  - `git restore`
  - `git checkout --`

권장 `.gitignore` 포함 항목:
- `kiwoom-rest-agent/data/**`
- `*.tsbuildinfo`
- `db/*.sqlite*`
- `*.log`
- `*token*.json`

---

## 8. 현재 우선순위

현재 개발 우선순위는 **추가 수집 기능 확대보다 저장 데이터 활용 고도화**입니다.

중심 흐름:
1. 조건검색 결과 활용
2. 관심종목 Data수집/분석 파이프라인 안정화
3. 저장 데이터 기반 GPT 자문 패키지 고도화

---

## 9. 주의 사항

- 본 프로젝트는 투자 판단을 보조하는 정보 시스템입니다.
- 자동매매/주문 실행 기능은 범위 밖입니다.
- 모든 분석 결과는 참고자료이며, 최종 의사결정 책임은 사용자에게 있습니다.
