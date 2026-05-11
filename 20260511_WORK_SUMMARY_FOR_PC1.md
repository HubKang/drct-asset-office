# TODAY WORK SUMMARY (PC2 -> PC1)

작성일: 2026-05-11  
작성위치: `D:\21. Codex\04. DrCT에셋\drct-asset-office`

## 1. 프로젝트 기본 정보
- 프로젝트명: DrCT에셋
- GitHub: https://github.com/HubKang/drct-asset-office.git
- PC2 작업 폴더: `D:\21. Codex\04. DrCT에셋\drct-asset-office`
- Backend: Python FastAPI
- Frontend: React + Vite + TypeScript
- DB: SQLite
- Local LLM: LM Studio
- 최종 투자 자문: GPT Plus
- 문서/이력 관리: Markdown + GitHub

핵심 운영 원칙:
- 로컬 LLM은 최종 투자판단용이 아니라 뉴스/공시 1건 요약용으로만 사용
- 최종 투자 판단/리스크 검토/종합 자문은 GPT Plus 담당
- 자동 매수/매도 판단은 하지 않음
- 최종 판단은 GPT Plus 자문 + 사용자 판단

## 2. 오늘 작업 전까지의 상태
구현 주요 기능:
1. 종목 관리
2. KRX 종목 마스터 갱신
3. 관심종목 Pool 관리
4. 네이버 뉴스 수집
5. DART 공시 수집
6. 뉴스/공시 목록 조회
7. 뉴스/공시 AI 요약
8. classification_rules 기반 분류
9. GPT 자문 패키지 생성
10. 수집 이력 관리

중요 테이블:
- `stocks`
- `watchlist`
- `news_items`
- `disclosures`
- `collection_runs`
- `research_reports`
- `analysis_source_items`
- `classification_rules`

`stocks` 주요 컬럼:
- `stock_code`, `stock_name`, `market`, `security_type`
- `isin_code`, `corp_name`, `corp_reg_no`
- `source`, `last_synced_at`, `is_active`

`security_type` 값:
- `common_stock`, `preferred_stock`, `etf`, `etn`, `spac`, `reit`, `other`

## 3. 오늘 진행한 주요 작업 요약
### A. 관심종목 Pool 화면 개선
- 관심종목을 즐겨찾기 개념이 아닌 분석 대상 Pool로 명확화
- 전체 종목 검색 영역 + 관심종목 Pool 목록 영역 구성
- 전체 종목에서 선택 후 관심종목 bulk 추가 플로우 강화
- 관심종목 목록 선택 기능 유지/보강
- 상단 설명/통계/빠른작업 영역 구조 개편

### B. 빠른 작업 영역 개선
- 전체 뉴스/전체 공시 버튼은 Pool 화면에서 제거 방향으로 정리
- 선택 중심 버튼 구성:
  - 선택 뉴스 수집
  - 선택 공시 수집
  - 선택 캔들 수집(또는 준비/갱신)
  - GPT 자문 패키지
- 선택 종목 없을 때 disabled 처리

### C. 관심종목 Pool UI 조정
- Analysis Pool 세로폭 축소
- 통계 카드(4개) compact 조정
- 통계 카드 중앙 정렬 스타일 적용
- 해제 버튼 compact 스타일 적용
- 작은 해상도에서 검색/초기화 버튼 레이아웃 튐 현상 보정

### D. 선택 뉴스/공시 수집 기능
- 선택 관심종목(stock_id 배열) 대상 수집 API 연동
- 실행 결과 메시지를 빠른 작업 영역에 노출
- 선택 0건일 때 실행 방지

### E. 뉴스/공시 수집 결과 점검
- 뉴스: `saved_count=0`, `skipped_count>0` 케이스 확인
- 공시: `corp_code not found`/`collected_count=0` 케이스 확인
- DART 조회용 코드 정규화 필요성 확인 (`A277810 -> 277810`)
- 공시 비대상/코드미존재는 failed보다 skipped 처리 방향 권장

### F. 뉴스/공시 관리 화면 개선
- 목록 기본 정렬을 최근 수집순(created_at DESC, id DESC)으로 맞추는 방향 적용
- 종목 컬럼은 코드 중심이 아닌 종목명 중심 표시

### G. DB 문제 대응
- PC2에서 `disk I/O error`, hot journal 반복 발생
- recover DB 우회도 동일 패턴 전이
- PC1 최신 `drct_asset.sqlite3` 교체 후 재검증 진행
- `init_db.py`가 하드코딩 경로를 쓰던 문제 수정: `DATABASE_URL` 기반으로 변경

### H. 13단계 가격/캔들 수집 준비
- 신규 구조 파일 추가:
  - `stock_daily_prices` 엔티티/스키마/리포지토리/서비스
  - mock price collector
  - stock prices API 라우트
- 목표: 관심종목 Pool 기준 일봉 + MA 계산 기반
- 운영 데이터는 향후 증권사 API로 교체 예정(현재 mock 검증 단계)

## 4. 오늘 확인된 문제와 원인
1. 한글 깨짐 (`\uXXXX` 노출)
- 원인: 문자열이 escape 형태로 저장된 상태
- 조치: TSX/JSON 문자열을 실제 한글로 복구

2. 공시 수집 후 화면 미노출
- `corp_code not found` 또는 `collected_count=0`
- `collected_count=0`은 “조회기간 내 공시 없음”일 수 있음
- 메시지 개선 필요

3. 뉴스 저장 0건
- 수집 자체는 되었지만 저장 시 skipped
- skip reason(duplicate/filter/missing fields) 노출 필요

4. SQLite `disk I/O` / hot journal 반복
- 원본/우회 DB 모두 저널 상태가 꼬이면 재발
- WAL 운용 + busy_timeout + 단일 writer 운영 필요

## 5. 오늘 수정되었거나 수정 가능성이 있는 파일
### 실제 변경 파일 (git status 기준, 주요)
- Backend
  - `backend/app/core/config.py`
  - `backend/app/core/database.py`
  - `backend/app/sql/schema.sql`
  - `scripts/init_db.py`
  - `backend/app/api/routes_watchlist.py`
  - `backend/app/api/routes_collectors.py`
  - `backend/app/api/routes_stock_prices.py` (신규)
  - `backend/app/services/stock_price_service.py` (신규)
  - `backend/app/repositories/stock_price_repository.py` (신규)
  - `backend/app/entities/stock_daily_price.py` (신규)
  - `backend/app/schemas/stock_price_schema.py` (신규)
  - `backend/app/collectors/prices/mock_price_collector.py` (신규)
  - `backend/app/main.py`
- Frontend
  - `frontend/src/pages/WatchlistPage.tsx`
  - `frontend/src/pages/NewsPage.tsx`
  - `frontend/src/pages/DisclosuresPage.tsx`
  - `frontend/src/index.css`
  - `frontend/src/services/api/watchlistApiRepository.ts`
  - `frontend/src/services/api/newsApiRepository.ts`
  - `frontend/src/services/api/disclosureApiRepository.ts`
  - `frontend/src/services/api/stockPriceApiRepository.ts` (신규)
  - `frontend/src/services/mock/stockPriceMockRepository.ts` (신규)
  - `frontend/src/types/stockPrice.ts` (신규)
  - `frontend/src/services/index.ts`
  - `frontend/src/types/watchlist.ts`
  - `frontend/src/types/news.ts`
  - `frontend/src/types/disclosure.ts`

### 후보(확인 필요)
- 테스트/샘플 JSON 및 일부 라우터/서비스 파일들이 함께 변경 상태라 PC1에서 커밋 전 diff 재검토 필요

## 6. DB 상태 점검 결과 (현재 시점)
- 현재 `DATABASE_URL`: `sqlite:///./db/drct_asset.sqlite3`
- 실제 연결 경로: `D:\21. Codex\04. DrCT에셋\drct-asset-office\db\drct_asset.sqlite3`
- 파일 존재/크기: 존재, `920,576 bytes`
- `drct_asset.sqlite3-journal`: 없음
- `drct_asset.sqlite3-wal`: 있음 (`0 bytes`)
- `drct_asset.sqlite3-shm`: 있음 (`32,768 bytes`)
- `PRAGMA integrity_check`: `ok`

주요 테이블 count:
- `stocks`: 2550
- `watchlist`: 0
- `news_items`: 28
- `disclosures`: 40
- `collection_runs`: 21
- `classification_rules`: 262

## 7. 현재 반드시 확인해야 할 회귀 테스트 (체크리스트)
### Backend/API
- [ ] `GET /stocks?limit=20&offset=0`
- [ ] `GET /watchlist?limit=20&offset=0`
- [ ] `GET /news?limit=20&offset=0`
- [ ] `GET /disclosures?limit=20&offset=0`
- [ ] `GET /collection-runs?limit=20&offset=0`
- [ ] `GET /classification-rules`

### Frontend
- [ ] 종목관리 화면 정상
- [ ] 관심종목 Pool 화면 정상
- [ ] 뉴스관리 화면 정상
- [ ] 공시관리 화면 정상
- [ ] 수집이력 화면 정상
- [ ] 분류규칙 화면 정상
- [ ] GPT 자문 패키지 화면 정상

### 특히 확인
- [ ] 뉴스 목록 최근 수집순 정렬(created_at DESC)
- [ ] 공시 목록 최근 수집순 정렬(created_at DESC)
- [ ] 뉴스 목록 종목명 중심 표시
- [ ] 공시 목록 종목명 중심 표시
- [ ] 선택 뉴스 수집 결과 메시지
- [ ] 선택 공시 수집 결과 메시지

## 8. 다음 개발 작업: 13단계 캔들 수집
목표: 관심종목 Pool 종목의 일봉/캔들 저장 구조 구축

필요 작업:
1. `stock_daily_prices` 테이블 생성/반영 확인
2. `StockDailyPrice` entity/schema/repository/service
3. mock price collector
4. `POST /stock-prices/collect/selected`
5. `POST /stock-prices/update/selected`
6. `GET /stock-prices/{stock_id}/daily`
7. `ma5/10/20/60/120/240` 계산 저장
8. `collection_runs` 이력 기록
9. WatchlistPage 빠른 작업에 선택 캔들 수집/갱신 연결
10. `source=mock` 저장
11. GPT 자문 패키지에는 mock 가격 미연동

원칙:
- 실제 증권사 API 연동은 다음 단계
- 이번 단계는 구조 검증
- 전체 종목이 아닌 관심종목 Pool 기준
- 기존 뉴스/공시/관심종목 기능 회귀 방지

## 9. PC1 Codex 새 스레드 시작용 요약문
아래를 PC1 새 Codex 스레드에 그대로 붙여넣기:

```text
프로젝트: DrCT에셋
폴더: D:\21. Codex\04. DrCT에셋\drct-asset-office

현재 상태:
- Backend(FastAPI), Frontend(React+Vite+TS), SQLite 구조.
- 종목관리/KRX 갱신/관심종목 Pool/뉴스·공시 수집/AI 요약/GPT 자문 패키지/수집이력 기능 구현 상태.
- 관심종목 Pool 화면은 선택 중심 작업(선택 뉴스/선택 공시/선택 캔들 방향)으로 개편 중.
- 뉴스/공시 목록은 종목명 중심 표시 및 최근 수집순(created_at DESC) 정렬 기준으로 맞추는 작업 진행됨.

오늘 PC2 작업:
- WatchlistPage/스타일/UI 조정(한글 깨짐 복구, compact화, 버튼 상태, 빠른작업 문구/동작 보정)
- 선택 뉴스/공시 수집 연계 보강
- 13단계 준비 코드 추가:
  - stock_daily_prices 엔티티/스키마/리포지토리/서비스
  - mock price collector
  - /stock-prices API(collect/update/daily)
- init_db.py를 DATABASE_URL 기반으로 수정(하드코딩 제거)
- SQLite 안정화 설정(WAL/busy_timeout/synchronous) 코드 반영

DB 관련:
- PC1 최신 drct_asset.sqlite3로 교체해 사용 중.
- 기준 DB는 반드시 db/drct_asset.sqlite3.
- recover DB는 기준으로 쓰지 않음.
- 새 DB 기준 integrity_check/회귀/API 검증을 먼저 수행해야 함.

남은 이슈:
- 뉴스 saved_count=0/skipped 발생 시 skip reason 메시지 고도화 필요.
- 공시 corp_code not found 및 collected_count=0(조회기간 무공시) 구분 메시지 필요.
- DART 조회용 stock_code A-prefix 정규화(A277810->277810) 정책 반영 필요.

다음 목표(13단계):
- 관심종목 Pool 대상 가격/캔들 수집 기반 완성
- stock_daily_prices 반영 확인, 선택 캔들 수집/갱신 API 실검증
- MA(5/10/20/60/120/240) 계산 검증
- collection_runs 이력 검증
- UI 버튼과 결과 메시지까지 확인

주의:
- .env, SQLite 파일(.sqlite3/.journal/.wal/.shm)은 GitHub에 절대 커밋 금지.
```

## 10. Git 주의사항
- `.env`, `db/*.sqlite3`, `db/*.sqlite3-journal`은 `.gitignore`에 포함됨
- 추가 필요: `db/*.sqlite3-wal`, `db/*.sqlite3-shm`, `*.sqlite3-wal`, `*.sqlite3-shm`
- 현재 `git status`에서 `db/drct_asset.sqlite3-wal`, `db/drct_asset.sqlite3-shm`가 untracked로 잡히고 있으므로 반드시 ignore 보강 필요
