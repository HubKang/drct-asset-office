# DrCT에셋 (drct-asset-office)

## 1. 프로젝트 개요
DrCT에셋은 AI Agent와 자동화 도구를 활용해 투자 정보 수집, 분석, 리스크 점검, 리포트 생성을 지원하는 개인 투자자문 프로젝트입니다.

## 2. DrCT에셋의 목적
- 투자 관련 데이터를 체계적으로 축적
- 분석/의사결정 보조 자료를 Markdown 기반으로 관리
- 로컬 LLM, NotebookLM, GPT 기반 자문 워크플로우를 분리 운영

## 3. 기술 스택
- Backend: Python, FastAPI (향후 구현)
- Database: SQLite (DB 파일은 루트 `db/`)
- Frontend: React + TypeScript (향후 샘플 UI 기준 적용)
- 문서/산출물: Markdown
- AI/LLM: LM Studio, NotebookLM, GPT Plus

## 4. 기본 폴더 구조
```text
drct-asset-office/
├─ backend/
│  └─ app/
│     ├─ core/
│     ├─ sql/
│     ├─ entities/
│     ├─ schemas/
│     ├─ repositories/
│     ├─ services/
│     ├─ collectors/
│     ├─ llm/
│     ├─ api/
│     └─ jobs/
├─ frontend/
├─ db/
├─ data/
├─ reports/
├─ prompts/
├─ agents/
├─ knowledge/
└─ docs/
```

## 5. PC1/PC2 개발 운영 원칙
- PC1: 주 개발 환경(코드 작성/실행/테스트)
- PC2: 보조 환경(검증, 문서 확인, 백업)
- `.env`, 로컬 DB, 민감 데이터는 GitHub에 업로드 금지
- 상세 절차는 `docs/setup_windows.md` 기준으로 통일

## 6. 실행 준비 절차 안내
실행 준비와 환경 구성 절차는 `docs/setup_windows.md`를 참고하세요.

## 7. DB 초기화
- 초기 스키마 적용 및 DB 생성: `python scripts/init_db.py`
- 생성 경로: `db/drct_asset.sqlite3`
- 10B.1 컬럼 추가 마이그레이션(수동 적용 시):
  - `sqlite3 db/drct_asset.sqlite3 < backend/app/sql/migrations/002_add_markdown_content_to_research_reports.sql`
  - 또는 `ALTER TABLE research_reports ADD COLUMN markdown_content TEXT;`

## 8. API 실행 및 수동 테스트
1. DB 초기화: `python scripts/init_db.py`
2. 서버 실행: `uvicorn backend.app.main:app --reload`
3. 문서 접속: `http://127.0.0.1:8000/docs`
4. 헬스체크:
   - `curl http://127.0.0.1:8000/health`
5. 종목 등록:
   - `curl -X POST http://127.0.0.1:8000/stocks -H "Content-Type: application/json" -d "{\"stock_code\":\"005930\",\"stock_name\":\"삼성전자\",\"market\":\"KOSPI\",\"sector\":\"반도체\",\"industry\":\"전자제품\"}"`
6. 관심종목 등록:
   - `curl -X POST http://127.0.0.1:8000/watchlist -H "Content-Type: application/json" -d "{\"stock_id\":1,\"status\":\"관심\",\"interest_reason\":\"테스트\",\"entry_condition\":\"20일선 지지\",\"exit_condition\":\"전저점 이탈\",\"risk_note\":\"단기 변동성\"}"`
7. 스키마 코멘트 조회:
   - `curl "http://127.0.0.1:8000/schema-comments?table_name=stocks"`

## 9. Frontend 실행
1. `cd frontend`
2. `npm install`
3. `copy .env.example .env`
4. `npm run dev`
5. 브라우저에서 `http://127.0.0.1:5173` 접속

## 10. Frontend 데이터 소스 전환
- `frontend/.env`에서 `VITE_DATA_SOURCE=mock`이면 mock repository 사용
- `frontend/.env`에서 `VITE_DATA_SOURCE=api`이면 FastAPI API 호출
- API 모드 전제:
  1. `python scripts/init_db.py`
  2. `uvicorn backend.app.main:app --reload`

## 11. CORS 안내
- API 모드에서 브라우저 호출 시 CORS 오류가 발생할 수 있음
- Backend CORS 설정은 별도 4.5단계에서 처리 필요

## 12. 뉴스 수집기 실행 (Naver API)
1. 네이버 개발자센터에서 Client ID / Client Secret 발급
2. 루트 `.env`에 아래 값 입력
   - `NEWS_PROVIDER=naver`
   - `NAVER_CLIENT_ID=...`
   - `NAVER_CLIENT_SECRET=...`
3. DB 초기화: `python scripts/init_db.py`
4. 서버 실행: `uvicorn backend.app.main:app --reload`
5. 단일 종목 뉴스 수집 테스트
   - `curl -X POST http://127.0.0.1:8000/collectors/news -H "Content-Type: application/json" -d "{\"stock_id\":1,\"providers\":[\"naver\"],\"display\":20,\"sort\":\"date\"}"`
6. 뉴스 목록 조회
   - `curl "http://127.0.0.1:8000/news?stock_id=1"`
7. 원본 JSON 저장 위치
   - `data/raw/news/naver`

## 13. 뉴스 관리 화면 (Frontend)
1. backend 실행 후 frontend 실행
2. `http://127.0.0.1:5173/#/news` 접속
3. 데이터 소스가 `api`이면 `GET /news`를 호출해 뉴스 목록을 조회
4. 검색 필터: `stock_id`, `keyword`, `source`, `limit`

## 14. Frontend API 연결 점검
1. backend 실행
2. `curl http://127.0.0.1:8000/health`
3. `curl "http://127.0.0.1:8000/news?stock_id=1"`
4. frontend 실행
5. `http://127.0.0.1:5173` 접속
6. 우측 상단 `API: 온라인` 표시 확인

## 15. 뉴스 수집 실행 (Frontend /news)
1. `VITE_DATA_SOURCE=api` 설정
2. `/news` 화면에서 종목, display, sort 선택
3. `뉴스 수집 실행` 클릭 -> `POST /collectors/news` 호출
4. 성공 시 수집 결과 표시 후 선택 종목 뉴스 자동 재조회


## 16. DB 일시 형식 정규화
- 기존 ISO 형식 데이터 정규화:
  - python scripts/normalize_datetime_format.py
- 표준 저장 형식:
  - YYYY-MM-DD HH:MM:SS (TEXT)


## 17. 수집 이력 API/화면 테스트
- Backend
  - `curl "http://127.0.0.1:8000/collection-runs"`
  - `curl "http://127.0.0.1:8000/collection-runs?status=success"`
  - `curl "http://127.0.0.1:8000/collection-runs?collector_name=naver_news_collector"`
- Frontend
  - 데이터관리 > 수집 이력 메뉴 이동
  - 목록/상태 필터/target 검색 동작 확인

## 18. 수집 이력 화면 운영 편의 기능 (7.1)
- 수집 이력 화면에서 새로고침 버튼으로 현재 검색 조건 유지 재조회
- 상태 요약(전체/성공/실패/부분성공/진행중) 확인
- 긴 메시지는 축약 표시되고 자세히로 전체 메시지 확인
- 뉴스 관리 화면 수집 결과에서 수집 이력 확인 버튼으로 /#/collection-runs 이동

- 프론트엔드 파일은 UTF-8로 저장합니다.
- 한글이 깨져 보이면 VS Code에서 Reopen with Encoding 또는 Save with Encoding -> UTF-8을 사용합니다.


## 19. DART 공시 수집기 (8단계)
1. OpenDART API Key 발급 후 루트 `.env`에 `DART_API_KEY` 입력
2. backend 실행: `uvicorn backend.app.main:app --reload`
3. 단일 종목 공시 수집 테스트
   - `curl -X POST http://127.0.0.1:8000/collectors/disclosures -H "Content-Type: application/json" -d "{\"stock_id\":1,\"days\":30,\"page_count\":100}"`
4. 공시 목록 조회
   - `curl "http://127.0.0.1:8000/disclosures?stock_id=1"`
5. 원본 응답 JSON 저장 경로
   - `data/raw/dart/disclosures`

- data/raw/dart/corp_codes/CORPCODE.xml이 존재하면 기본적으로 재사용합니다.
- 강제 재다운로드가 필요하면 코드에서 orce_download=True를 사용할 수 있습니다.
- DART_API_KEY는 .env에 저장하고 GitHub에 올리지 않습니다.


## 20. 공시 관리 화면 (9단계)
1. backend 실행 후 frontend 실행
2. http://127.0.0.1:5173/#/disclosures 접속
3. 종목 선택 후 공시 수집 실행으로 POST /collectors/disclosures 호출
4. 관심종목 전체 수집으로 POST /collectors/disclosures/watchlist 호출
5. GET /disclosures 목록 조회 및 검색(stock_id, keyword, disclosure_type, limit) 확인
6. 수집 이력 확인으로 /#/collection-runs 이동 확인


## 21. 로컬 LLM 뉴스·공시 요약 (10B단계)
1. LM Studio 서버 실행 (OpenAI-compatible API 활성화)
2. `.env` 설정
   - `LMSTUDIO_BASE_URL=http://localhost:1234/v1`
   - `LMSTUDIO_MODEL=local-model-name`
   - `LLM_REPORT_BASE_DIR=./reports/company`
3. 종목 브리핑 생성
   - `curl -X POST http://127.0.0.1:8000/analysis/stock-briefing -H "Content-Type: application/json" -d "{\"stock_id\":1,\"news_limit\":20,\"disclosure_limit\":20}"`
4. 리포트 목록 조회
   - `curl "http://127.0.0.1:8000/reports"`
5. 생성 파일 확인
   - `reports/company/*_llm_briefing.md`

- LM Studio 모델 context size가 작으면 `news_limit`, `disclosure_limit`을 줄여서 요청하세요.
- 권장 테스트:
  - `curl -X POST "http://127.0.0.1:8000/analysis/stock-briefing" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"news_limit\":5,\"disclosure_limit\":5}"`
- `LMSTUDIO_MODEL` 값은 LM Studio 화면의 API Model Identifier와 동일해야 합니다. 예: `google/gemma-4-e2b`

- LM Studio 모델 context size가 작으면 news_limit, disclosure_limit을 줄여야 합니다.
- 권장 테스트:
  - curl -X POST "http://127.0.0.1:8000/analysis/stock-briefing" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"news_limit\":5,\"disclosure_limit\":5}"
- LMSTUDIO_MODEL은 LM Studio 화면의 API Model Identifier와 동일하게 설정하세요. 예: LMSTUDIO_MODEL=google/gemma-4-e2b

- 리포트가 중간에 끊기면 LLM_MAX_OUTPUT_TOKENS를 늘리세요.
- 작은 모델에서는 입력량은 줄이고 출력 토큰은 1000~1500으로 설정하세요.
- 권장값:
  - LLM_MAX_OUTPUT_TOKENS=1200
  - LLM_MAX_INPUT_CHARS=4500
  - ANALYSIS_MAX_NEWS_LIMIT=100
  - ANALYSIS_MAX_DISCLOSURE_LIMIT=100
  - LLM_CHUNK_SIZE=5
  - LLM_CHUNK_MAX_OUTPUT_TOKENS=400
  - LLM_FINAL_MAX_OUTPUT_TOKENS=1200

## 22. 계층형 뉴스·공시 요약 (10C단계)
1. migration 적용
   - `sqlite3 db/drct_asset.sqlite3 < backend/app/sql/migrations/003_create_analysis_source_items.sql`
2. 후보 자료 조회
   - `GET /analysis/stock-briefing/candidates?stock_id=1`
3. 브리핑 생성 모드
   - `incremental`: 기존 리포트에 사용된 자료 제외
   - `full`: 사용 여부와 무관하게 최근 자료 사용
   - `selected`: 지정한 `news_ids`, `disclosure_ids`만 사용
   - `news_limit`: 전체 사용할 뉴스 개수
   - `disclosure_limit`: 전체 사용할 공시 개수
   - `chunk_size`: LLM에 한 번에 전달할 묶음 크기
4. 브리핑 생성 예시
   - `curl -X POST http://127.0.0.1:8000/analysis/stock-briefing -H "Content-Type: application/json" -d "{\"stock_id\":1,\"mode\":\"incremental\",\"news_limit\":20,\"disclosure_limit\":20,\"chunk_size\":5}"`

## 23. LM Studio 빈 응답 장애 대응
- `LM Studio returned empty content` 발생 시:
1. LM Studio 모델을 Eject 후 다시 Load
2. `chunk_size`를 3으로 낮춰 재시도
3. `LLM_CHUNK_MAX_OUTPUT_TOKENS`를 700 이상으로 설정
4. 더 안정적인 instruct 계열 모델 사용 검토

## 24. KRX 종목 마스터 동기화 설정
1. 공공데이터포털에서 금융위원회_KRX상장종목정보 API 키 발급
2. 루트 `.env` 설정
   - `DATA_API_SERVICE_KEY=...`
   - `DATA_API_BASE_URL=https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo`
   - `DATA_API_KEY_MODE=encoded`
   - `DATA_API_TIMEOUT_SECONDS=15`
   - `DATA_API_MAX_PAGES=10`
3. 키 유형 주의
   - `DATA_API_KEY_MODE=encoded`: serviceKey를 URL query 문자열에 직접 부착(Encoding 키 권장)
   - `DATA_API_KEY_MODE=decoded`: serviceKey를 `requests params`로 전달(Decoding 키 권장)
4. 환경변수 구분
   - `DATA_API_SERVICE_KEY`: data.go.kr 공공데이터포털 전용
   - `DATA_API_BASE_URL`, `DATA_API_KEY_MODE`, `DATA_API_TIMEOUT_SECONDS`, `DATA_API_MAX_PAGES`: data.go.kr 전용 보조 설정
   - `KRX_OPEN_API_AUTH_KEY`: KRX Open API 전용
   - `KRX_API_SERVICE_KEY`: 더 이상 사용하지 않음
5. 동기화 API 호출 예시
   - `curl -X POST http://127.0.0.1:8000/stocks/sync -H "Content-Type: application/json" -d "{\"markets\":[\"KOSPI\"],\"dry_run\":true,\"deactivate_missing\":true}"`
6. `/v1/chat/completions`를 curl로 짧은 요청 테스트
7. 형식 검증 실패 시 `data/debug/llm_failed`의 실패 파일 확인

## 24. 10D 뉴스·공시 1건 단위 AI 요약
1. migration 적용
   - `sqlite3 db/drct_asset.sqlite3 < backend/app/sql/migrations/004_add_ai_summary_columns.sql`
2. 뉴스 AI 요약
   - `curl -X POST "http://127.0.0.1:8000/analysis/news/ai-summarize" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"limit\":5,\"only_unprocessed\":true,\"overwrite\":false}"`
3. 공시 AI 요약
   - `curl -X POST "http://127.0.0.1:8000/analysis/disclosures/ai-summarize" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"limit\":5,\"only_unprocessed\":true,\"overwrite\":false}"`
4. 통합 AI 요약
   - `curl -X POST "http://127.0.0.1:8000/analysis/source-items/ai-summarize" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"news_limit\":5,\"disclosure_limit\":5,\"only_unprocessed\":true,\"overwrite\":false}"`
5. 로컬 LLM이 JSON 형식을 지키지 못할 수 있습니다.
6. 이 경우 DrCT에셋은 LLM 응답 본문을 ai_summary로 fallback 저장합니다.
7. ai_summary_error가 `json parse fallback used`이면 요약은 되었지만 구조화 파싱은 실패한 상태입니다.
8. 관리화면에서는 ai_summary를 우선 표시하고, ai_summary_error는 품질 점검용으로 사용합니다.
9. 기존 Thinking Process 오염 데이터 정리 SQL:
   - `UPDATE news_items SET ai_summary = NULL, ai_sentiment = NULL, ai_importance_score = 0, ai_tags = NULL, ai_processed_at = NULL, ai_summary_error = NULL WHERE lower(ai_summary) LIKE '%thinking process%' OR lower(ai_summary) LIKE '%analyze the request%' OR lower(ai_summary) LIKE '%final json construction%' OR lower(ai_summary) LIKE '%determine sentiment%';`
   - `UPDATE disclosures SET ai_summary = NULL, ai_importance_score = 0, ai_tags = NULL, ai_risk_level = NULL, ai_event_type = NULL, ai_processed_at = NULL, ai_summary_error = NULL WHERE lower(ai_summary) LIKE '%thinking process%' OR lower(ai_summary) LIKE '%analyze the request%' OR lower(ai_summary) LIKE '%final json construction%';`

## 25. AI 요약 저장 품질 점검/정리
- 1건 요약 API는 JSON이 아닌 완성된 한국어 요약문만 저장합니다.
- Thinking Process, Analysis, Reasoning, JSON 조각 응답은 저장하지 않고 실패 처리합니다.
- 필요 시 기존 오염 데이터 정리 SQL:

```sql
UPDATE news_items
SET ai_summary = NULL,
    ai_sentiment = NULL,
    ai_importance_score = 0,
    ai_tags = NULL,
    ai_processed_at = NULL,
    ai_summary_error = NULL
WHERE ai_summary LIKE '{%'
   OR ai_summary LIKE '%"ai_summary"%'
   OR lower(ai_summary) LIKE '%thinking process%'
   OR lower(ai_summary) LIKE '%analyze the request%'
   OR lower(ai_summary) LIKE '%final json construction%'
   OR lower(ai_summary) LIKE '%reasoning%';

UPDATE disclosures
SET ai_summary = NULL,
    ai_importance_score = 0,
    ai_tags = NULL,
    ai_risk_level = NULL,
    ai_event_type = NULL,
    ai_processed_at = NULL,
    ai_summary_error = NULL
WHERE ai_summary LIKE '{%'
   OR ai_summary LIKE '%"ai_summary"%'
   OR lower(ai_summary) LIKE '%thinking process%'
   OR lower(ai_summary) LIKE '%analyze the request%'
   OR lower(ai_summary) LIKE '%final json construction%'
   OR lower(ai_summary) LIKE '%reasoning%';
```

## 26. 분류 규칙 관리 (10E)
- `classification_rules` 테이블로 뉴스/공시 분류 규칙을 DB에서 관리합니다.
- AI 요약 저장 직후 규칙 기반 자동 분류가 적용됩니다.
- 재분류 API
  - `POST /analysis/news/classify`
  - `POST /analysis/disclosures/classify`
  - `POST /analysis/source-items/classify`
- 규칙 관리 API
  - `GET /classification-rules`
  - `POST /classification-rules`
  - `PATCH /classification-rules/{rule_id}`
  - `POST /classification-rules/{rule_id}/deactivate`
- 초기 규칙 적용
  - `sqlite3 db/drct_asset.sqlite3 < backend/app/sql/migrations/005_create_classification_rules.sql`
