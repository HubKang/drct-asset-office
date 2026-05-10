# Windows 환경 세팅 (PC1/PC2)

## 1. 공통 준비
- Git 설치
- Python 3.11+ 설치
- Node.js LTS 설치
- (선택) VS Code 설치

## 2. PC1 (주 개발 PC)
1. 저장소 클론
2. 루트에서 가상환경 생성: `python -m venv .venv`
3. 가상환경 활성화 후 의존성 설치: `pip install -r requirements.txt`
4. frontend 폴더에서 의존성 설치: `npm install` (추후 UI 작업 시)
5. `.env.example`를 참고해 로컬 `.env` 생성
6. SQLite 파일은 루트 `db/` 아래에 생성/유지

## 3. PC2 (보조 운영 PC)
1. 저장소 동기화(클론 또는 pull)
2. 동일 버전 Python/Node 환경 구성
3. `.env`는 PC1 값을 안전하게 복사(공개 저장소 업로드 금지)
4. 필요 시 `db/` 로컬 파일 백업/복제

## 4. 운영 원칙
- 코드/문서는 Git으로 동기화
- `.env`, `db/*.db`, `data/raw`, `reports/private`는 Git 제외
- DB 스키마 변경은 SQL 파일 기준으로만 반영

## 5. DB 초기화 방법
1. 프로젝트 루트로 이동
2. 아래 명령 실행: `python scripts/init_db.py`
3. 생성 확인: `db/drct_asset.sqlite3`

### research_reports 마이그레이션(10B.1)
- 신규 컬럼: `markdown_content` (리포트 전문 저장)
- 수동 적용(SQL 파일):
  - `sqlite3 db/drct_asset.sqlite3 < backend/app/sql/migrations/002_add_markdown_content_to_research_reports.sql`
- 또는 DBeaver에서 실행:
  - `ALTER TABLE research_reports ADD COLUMN markdown_content TEXT;`

## 6. API 실행 및 점검
1. 서버 실행: `uvicorn backend.app.main:app --reload`
2. Swagger 접속: `http://127.0.0.1:8000/docs`
3. 헬스체크: `GET /health`
4. 종목 API: `POST /stocks`, `GET /stocks`, `PUT /stocks/{stock_id}`, `DELETE /stocks/{stock_id}`
5. 관심종목 API: `POST /watchlist`, `GET /watchlist`, `PUT /watchlist/{watchlist_id}`, `DELETE /watchlist/{watchlist_id}`
6. 스키마 코멘트 API: `GET /schema-comments`

## 7. Frontend 실행
1. `cd frontend`
2. `npm install`
3. `.env` 생성: `copy .env.example .env`
4. `npm run dev`
5. 접속: `http://127.0.0.1:5173`

## 8. Frontend API 모드
1. backend 선실행
   - `python scripts/init_db.py`
   - `uvicorn backend.app.main:app --reload`
2. `frontend/.env`에서 `VITE_DATA_SOURCE=api` 설정
3. CORS 오류 발생 시 backend CORS 설정 필요(별도 단계에서 처리)

## 9. 실제 뉴스 수집기 실행 (Naver)
1. 네이버 개발자센터에서 Client ID / Client Secret 발급
2. `.env`에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 입력
3. backend 실행
   - `python scripts/init_db.py`
   - `uvicorn backend.app.main:app --reload`
4. 뉴스 수집 호출
   - `POST /collectors/news`
5. 뉴스 조회
   - `GET /news`
6. 원본 JSON 확인
   - `data/raw/news/naver`
7. 수집 건수가 0건이어도 `*_response.json` 파일이 저장되어 API 응답 원문을 점검할 수 있음
8. Collector 직접 테스트
   - `python -c "from backend.app.collectors.news.naver_news_collector import NaverNewsCollector; c=NaverNewsCollector(); result=c.collect_by_keyword('삼성전자', display=5, sort='date'); print(result['total']); print(len(result['items'])); print(result['items'][:1])"`

## 10. 뉴스 관리 화면 확인
1. backend 실행
2. `cd frontend && npm run dev`
3. 브라우저: `http://127.0.0.1:5173/#/news`
4. `VITE_DATA_SOURCE=api`에서 `GET /news` 호출 확인
5. CORS 오류 발생 시 backend CORS 설정 필요(본 단계에서는 backend 미수정)

## 11. API 연결 점검 순서
1. backend 실행
2. `curl http://127.0.0.1:8000/health`
3. `curl "http://127.0.0.1:8000/news?stock_id=1"`
4. frontend 실행
5. `http://127.0.0.1:5173` 접속
6. 화면 우측 상단 `API: 온라인` 표시 확인

## 12. /news 화면에서 종목별 수집 실행
1. `VITE_DATA_SOURCE=api` 확인
2. `/news` 이동
3. 종목/건수/정렬 선택 후 `뉴스 수집 실행`
4. 결과 요약(수집/저장/중복제외) 확인
5. 목록 자동 갱신 확인


## 13. DB 일시 데이터 정규화
1. python scripts/normalize_datetime_format.py 실행
2. backend 서버 재시작
3. POST /stocks로 신규 종목 등록
4. POST /collectors/news로 뉴스 수집
5. DBeaver에서 created_at, collected_at, published_at 값이 YYYY-MM-DD HH:MM:SS 형식인지 확인


## 14. 수집 이력 관리 테스트
1. Backend API
   - `curl "http://127.0.0.1:8000/collection-runs"`
   - `curl "http://127.0.0.1:8000/collection-runs?status=success"`
   - `curl "http://127.0.0.1:8000/collection-runs?collector_name=naver_news_collector"`
2. Frontend 화면
   - 데이터관리 > 수집 이력 이동
   - 목록 표시, status 필터, target 검색 확인

## 15. 수집 이력 화면 운영 편의 기능 확인 (7.1)
1. 데이터관리 > 수집 이력 이동
2. 조건 입력 후 검색, 새로고침으로 같은 조건 재조회 확인
3. 실패/부분성공 행 강조 표시 확인
4. 긴 message가 축약되고 자세히로 전체 메시지 확인
5. 뉴스 관리 화면 수집 실행 후 수집 이력 확인 버튼으로 이동 확인

- 프론트엔드 파일은 UTF-8로 저장합니다.
- 한글이 깨져 보이면 VS Code에서 Reopen with Encoding 또는 Save with Encoding -> UTF-8을 사용합니다.


## 16. DART 공시 수집 테스트 (8단계)
1. OpenDART API Key 발급 후 `.env`에 `DART_API_KEY` 설정
2. backend 실행: `uvicorn backend.app.main:app --reload`
3. 단일 종목 수집
   - `curl -X POST http://127.0.0.1:8000/collectors/disclosures -H "Content-Type: application/json" -d "{\"stock_id\":1,\"days\":30,\"page_count\":100}"`
4. 목록 조회
   - `curl "http://127.0.0.1:8000/disclosures"`
5. 실행 이력 조회
   - `curl "http://127.0.0.1:8000/collection-runs?collector_name=dart_disclosure_collector"`
6. 원본 파일 확인
   - `data/raw/dart/disclosures`

- data/raw/dart/corp_codes/CORPCODE.xml이 존재하면 기본적으로 재사용합니다.
- 강제 재다운로드가 필요하면 코드에서 orce_download=True를 사용할 수 있습니다.
- DART_API_KEY는 .env에 저장하고 GitHub에 올리지 않습니다.


## 17. 공시 관리 화면 테스트 (9단계)
1. backend 실행: uvicorn backend.app.main:app --reload`n2. frontend 실행: cd frontend && npm run dev`n3. 브라우저: http://127.0.0.1:5173/#/disclosures`n4. 종목 선택 후 공시 수집 실행 테스트
5. 관심종목 전체 수집 테스트
6. 공시 목록/검색/원문 링크/수집 이력 확인 이동 테스트


## 18. 로컬 LLM 브리핑 테스트 (10B단계)
1. LM Studio 실행 및 API 서버 활성화
2. `.env`에 `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`, `LLM_REPORT_BASE_DIR` 설정
3. backend 실행: `uvicorn backend.app.main:app --reload`
4. 브리핑 생성
   - `curl -X POST http://127.0.0.1:8000/analysis/stock-briefing -H "Content-Type: application/json" -d "{\"stock_id\":1,\"news_limit\":20,\"disclosure_limit\":20}"`
5. 리포트 조회
   - `curl "http://127.0.0.1:8000/reports"`
6. 리포트 파일 확인
   - `reports/company`

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

## 19. 계층형 브리핑 파이프라인 테스트 (10C단계)
1. migration 적용
   - `sqlite3 db/drct_asset.sqlite3 < backend/app/sql/migrations/003_create_analysis_source_items.sql`
2. 후보 자료 조회
   - `curl "http://127.0.0.1:8000/analysis/stock-briefing/candidates?stock_id=1&news_limit=20&disclosure_limit=20"`
3. incremental 모드 실행
   - `curl -X POST http://127.0.0.1:8000/analysis/stock-briefing -H "Content-Type: application/json" -d "{\"stock_id\":1,\"mode\":\"incremental\",\"news_limit\":20,\"disclosure_limit\":20,\"chunk_size\":5}"`
4. full 모드 실행
   - `curl -X POST http://127.0.0.1:8000/analysis/stock-briefing -H "Content-Type: application/json" -d "{\"stock_id\":1,\"mode\":\"full\",\"news_limit\":20,\"disclosure_limit\":20,\"chunk_size\":5}"`
5. selected 모드 실행
   - `curl -X POST http://127.0.0.1:8000/analysis/stock-briefing -H "Content-Type: application/json" -d "{\"stock_id\":1,\"mode\":\"selected\",\"news_ids\":[1,2,3],\"disclosure_ids\":[1,2],\"chunk_size\":5}"`
6. 파라미터 기준
   - `news_limit`: 전체 사용할 뉴스 개수
   - `disclosure_limit`: 전체 사용할 공시 개수
   - `chunk_size`: LLM에 한 번에 전달할 묶음 크기

## 20. LM Studio 빈 응답 장애 대응
1. LM Studio 모델을 Eject 후 다시 Load
2. `chunk_size`를 3으로 낮춰 재시도
3. `LLM_CHUNK_MAX_OUTPUT_TOKENS`를 700 이상으로 설정
4. 더 안정적인 instruct 계열 모델 사용 검토
5. `/v1/chat/completions`를 curl로 짧은 요청 테스트
6. 형식 검증 실패 시 `data/debug/llm_failed` 실패 파일 확인

## 21. 10D AI 요약 컬럼 마이그레이션 및 테스트
1. migration 적용
   - `sqlite3 db/drct_asset.sqlite3 < backend/app/sql/migrations/004_add_ai_summary_columns.sql`
2. LM Studio 서버 실행
3. 뉴스 AI 요약 실행
   - `curl -X POST "http://127.0.0.1:8000/analysis/news/ai-summarize" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"limit\":5,\"only_unprocessed\":true,\"overwrite\":false}"`
4. 공시 AI 요약 실행
   - `curl -X POST "http://127.0.0.1:8000/analysis/disclosures/ai-summarize" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"limit\":5,\"only_unprocessed\":true,\"overwrite\":false}"`
5. 통합 AI 요약 실행
   - `curl -X POST "http://127.0.0.1:8000/analysis/source-items/ai-summarize" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"news_limit\":5,\"disclosure_limit\":5,\"only_unprocessed\":true,\"overwrite\":false}"`
6. DB 확인 SQL
   - `SELECT id, title, ai_summary, ai_sentiment, ai_importance_score, ai_tags, ai_processed_at, ai_summary_error FROM news_items WHERE stock_id = 1 ORDER BY id DESC;`
   - `SELECT id, disclosure_title, ai_summary, ai_importance_score, ai_tags, ai_risk_level, ai_event_type, ai_processed_at, ai_summary_error FROM disclosures WHERE stock_id = 1 ORDER BY id DESC;`
7. 로컬 LLM이 JSON 형식을 지키지 못할 수 있습니다.
8. 이 경우 DrCT에셋은 LLM 응답 본문을 ai_summary로 fallback 저장합니다.
9. ai_summary_error가 `json parse fallback used`이면 요약은 되었지만 구조화 파싱은 실패한 상태입니다.
10. 관리화면에서는 ai_summary를 우선 표시하고, ai_summary_error는 품질 점검용으로 사용합니다.
11. 기존 Thinking Process 오염 데이터 정리 SQL:
    - `UPDATE news_items SET ai_summary = NULL, ai_sentiment = NULL, ai_importance_score = 0, ai_tags = NULL, ai_processed_at = NULL, ai_summary_error = NULL WHERE lower(ai_summary) LIKE '%thinking process%' OR lower(ai_summary) LIKE '%analyze the request%' OR lower(ai_summary) LIKE '%final json construction%' OR lower(ai_summary) LIKE '%determine sentiment%';`
    - `UPDATE disclosures SET ai_summary = NULL, ai_importance_score = 0, ai_tags = NULL, ai_risk_level = NULL, ai_event_type = NULL, ai_processed_at = NULL, ai_summary_error = NULL WHERE lower(ai_summary) LIKE '%thinking process%' OR lower(ai_summary) LIKE '%analyze the request%' OR lower(ai_summary) LIKE '%final json construction%';`

## 22. AI 요약 저장 품질 점검/정리
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

## 23. 분류 규칙 관리(10E)
1. 마이그레이션 적용
   - `sqlite3 db/drct_asset.sqlite3 < backend/app/sql/migrations/005_create_classification_rules.sql`
2. 규칙 조회
   - `curl "http://127.0.0.1:8000/classification-rules"`
3. 규칙 등록
   - `curl -X POST "http://127.0.0.1:8000/classification-rules" -H "Content-Type: application/json" -d "{\"rule_group\":\"tag\",\"target_type\":\"news\",\"rule_name\":\"뉴스_HBM\",\"keywords\":\"HBM,고대역폭메모리\",\"output_field\":\"ai_tags\",\"output_value\":\"HBM\",\"score_delta\":10,\"priority\":10,\"is_active\":true,\"description\":\"HBM 관련 뉴스 태그\"}"`
4. 뉴스 재분류
   - `curl -X POST "http://127.0.0.1:8000/analysis/news/classify" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"limit\":100}"`
5. 공시 재분류
   - `curl -X POST "http://127.0.0.1:8000/analysis/disclosures/classify" -H "Content-Type: application/json" -d "{\"stock_id\":1,\"limit\":100}"`
6. 관리화면 확인
   - 데이터관리 > 분류 규칙 관리
   - 규칙 목록/등록/수정/비활성화 동작 확인
