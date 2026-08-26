# 일별/EOD 데이터 중복 적재 및 DB 사용성 조사 보고서

- 조사 기준 시각: 2026-08-26 08:55 KST
- 대상 DB: `db/drct_asset.sqlite3`
- 조사 방식: SQLite 읽기 전용 URI(`mode=ro`), `PRAGMA`, 실제 Business Key `GROUP BY`, 코드/스키마/테스트 정적 분석
- DB 변경: **없음**
- 코드 변경: **없음** (이 문서만 신규 작성)

## 1. 결론

현재 실DB에서 우선 대상 3개와 추가 일별/기간 스냅샷 후보 16개, 총 19개 테이블을 Business Key로 검사한 결과 **중복 Business Key와 초과 Row는 모두 0건**이었다. 핵심 3개 테이블의 최대 중복 횟수도 모두 1이다.

반복 수집이 없었던 것이 아니다. `market_theme_daily_returns`는 9,330행 중 4,241행이 한 번 이상 갱신되었고, `refresh_count - 1` 합계는 7,090회, 단일 행 최대 `refresh_count`는 8이다. 반복 수집이 INSERT 누적으로 이어지지 않고 기존 행 갱신으로 수렴했다는 직접적인 증거다.

따라서 현재 DB 용량 61,113,344바이트의 원인을 Business Key 중복 Row로 볼 근거는 없다. 대신 다음 사용성 개선 후보가 확인됐다.

1. 동일 컬럼을 중복 보관하는 일반/UNIQUE 인덱스가 있으며, 일별 핵심 테이블만 계산해도 제거 검토 대상 인덱스 엔트리가 약 221,799개다.
2. 국내 핵심 ORM 모델 3개(`StockDailyPrice`, `StockDailyTechnicalIndicator`, `StockDailyMarketMetric`)에는 실제 DB와 `schema.sql`에 있는 UNIQUE가 선언되어 있지 않다. 초기화 경로에 따라 스키마가 달라질 수 있는 TYPE 6 위험이다.
3. 일부 저장 경로는 원자적 UPSERT 대신 `SELECT → UPDATE/INSERT` 또는 `DELETE → INSERT`를 사용한다. 현재 UNIQUE가 중복 자체는 막지만, 동시 실행 시 충돌 오류·마지막 쓰기 우선·불필요한 쓰기 잠금 가능성이 있다.
4. Python SQLite 빌드에 `dbstat` 모듈이 없어 테이블/인덱스별 실제 바이트는 측정하지 못했다. 임의 바이트 추정은 하지 않았다.

## 2. DB 상태와 무결성

| 항목 | 결과 |
|---|---:|
| 메인 DB 파일 | 61,113,344 bytes (약 58.28 MiB) |
| WAL 파일(측정 시점) | 1,096,240 bytes |
| page size | 1,024 bytes |
| page count | 59,681 |
| freelist count | 0 |
| journal mode | WAL |
| `PRAGMA quick_check` | `ok` |
| 전체 사용자 테이블 | 145개 |
| 전체 테이블 Row 합계 | 228,819 |

조사 중 WAL과 일부 Row 수가 증가했다. 예를 들어 `us_stock_daily_prices`는 첫 측정 29,076행에서 최종 스냅샷 29,077행으로 바뀌었다. 즉 다른 실행 주체가 DB를 사용 중이었으며, 본 보고서의 수치는 08:55 읽기 스냅샷 기준이다. 조사 연결은 읽기 전용이었고 DELETE, migration, index 생성, VACUUM은 수행하지 않았다.

`stock_investor_flows.raw_json`과 `market_indicator_values.raw_payload_json`의 비NULL 값은 각각 0건으로, 데이터 보존 정책의 원천 응답 비영구화 원칙에도 부합한다.

## 3. 핵심 및 추가 후보 정량 결과

`정상 Key`는 해당 Business Key의 distinct 그룹 수이며, `초과 Row = 전체 Row - 정상 Key`다.

| Table | 성격 | Business Key | 전체 Row | 정상 Key | 초과 Row | 최대 중복 | UNIQUE | 실제 저장 방식 | 판정 |
|---|---|---|---:|---:|---:|---:|---|---|---|
| `stock_daily_prices` | TYPE A 일봉 | `stock_id, trade_date` | 29,533 | 29,533 | 0 | 1 | 있음 | 배치 `ON CONFLICT DO UPDATE` | NORMAL |
| `market_theme_daily_returns` | TYPE A 테마 일별 | `theme_id, return_date` | 9,330 | 9,330 | 0 | 1 | 있음 | UPSERT 및 일부 SELECT→UPDATE/INSERT | NORMAL/구조개선 |
| `market_theme_stock_daily_returns` | TYPE B 테마-종목 일별 | `theme_id, stock_id, return_date` | 29,126 | 29,126 | 0 | 1 | 있음 | UPSERT 및 일부 삭제 후 SELECT→UPDATE/INSERT | NORMAL/구조개선 |
| `stock_daily_technical_indicators` | TYPE A 일별 계산값 | `stock_id, trade_date` | 29,533 | 29,533 | 0 | 1 | 있음 | 배치 `ON CONFLICT DO UPDATE` | NORMAL |
| `stock_investor_flows` | TYPE A 종목 일별 수급 | `stock_id, flow_date` | 24,960 | 24,960 | 0 | 1 | 있음 | 부분필드 보존 UPSERT | NORMAL |
| `market_indicator_values` | TYPE B 지표 관측값 | `indicator_code, value_date` | 28,629 | 28,629 | 0 | 1 | 있음 | 배치 UPSERT, 수정시각 보존 | NORMAL |
| `us_stock_daily_prices` | TYPE A 미국 일봉 | `us_stock_id, trade_date` | 29,077 | 29,077 | 0 | 1 | 있음 | `ON CONFLICT DO UPDATE` | NORMAL |
| `us_theme_daily_returns` | TYPE A 미국 테마 일별 | `theme_id, trade_date` | 7,565 | 7,565 | 0 | 1 | 있음 | 삭제 후 UPSERT | NORMAL/구조개선 |
| `market_index_daily_prices` | TYPE A 시장/업종 일봉 | `index_code, price_date` | 11,163 | 11,163 | 0 | 1 | 있음 | 배치 UPSERT | NORMAL |
| `stock_daily_market_metrics` | TYPE B 종목-소스 일별 | `stock_id, trade_date, source` | 26 | 26 | 0 | 1 | 있음 | 배치 UPSERT | NORMAL |
| `daily_theme_flow_ranks` | TYPE B 테마별 일간 순위 | `trade_date, market_theme_id` | 28 | 28 | 0 | 1 | 있음 | SELECT→UPDATE/INSERT | NORMAL/구조개선 |
| `price_daily` | TYPE A 레거시 일봉 | `stock_id, trade_date` | 0 | 0 | 0 | 0 | 있음 | 현재 운영 쓰기 경로 없음 | NORMAL/정리검토 |
| `telegram_daily_summaries` | TYPE B 소스별 일일 요약 | `summary_date, source_id` | 1 | 1 | 0 | 1 | 있음 | SELECT→ORM UPDATE/INSERT | NORMAL/구조개선 |
| `market_theme_realtime_returns` | TYPE B 당일 최신 스냅샷 | `trade_date, theme_id, stock_id` | 38 | 38 | 0 | 1 | 있음 | `ON CONFLICT DO UPDATE` | NORMAL |
| `stock_financial_snapshots` | TYPE B 소스별 스냅샷 | `stock_id, snapshot_date, source_method` | 14 | 14 | 0 | 1 | 있음 | UPSERT | NORMAL |
| `stock_shareholder_snapshots` | TYPE B 소스별 스냅샷 | `stock_id, snapshot_date, source_method` | 6 | 6 | 0 | 1 | 있음 | UPSERT | NORMAL |
| `stock_financial_statements` | TYPE B 기간 재무 | `stock_id, statement_type, fiscal_year, fiscal_quarter, source_method` | 74 | 74 | 0 | 1 | 있음 | UPSERT | NORMAL |
| `stock_shareholder_changes` | TYPE B 공시 변경 | `stock_id, report_date, source_method, receipt_no` | 62 | 62 | 0 | 1 | 있음 | UPSERT | NORMAL |
| `market_trend_events` | TYPE B 일별 이벤트 종류 | `trade_date, stock_id, event_type` | 634 | 634 | 0 | 1 | 있음 | UPDATE/INSERT 및 `DO NOTHING` | NORMAL/구조개선 |

모든 표 대상에서 Business Key NULL도 0건이었다. 중복 Key가 없으므로 중복 최초/최근 날짜와 대표 중복 샘플, 완전 동일 중복/값 변경 중복 분류는 모두 **해당 없음**이다.

## 4. 핵심 3개 상세

### 4.1 `stock_daily_prices`

- Business Key: `(stock_id, trade_date)`
- 기간: 2024-05-27 ~ 2026-08-25
- PK: surrogate `id`; 중복 방지는 `ux_stock_daily_prices_stock_date`가 담당한다.
- 저장: `StockPriceRepository.upsert_daily_rows()`가 `ON CONFLICT(stock_id, trade_date) DO UPDATE`를 사용한다.
- 경로: 종목 선택수집, 최근 7일/전체 매매훈련 수집, 종목추적 수집, 테마 가격·수급 갱신, 공급 상위 종목 가격 갱신이 모두 `StockPriceService._collect_and_upsert_with_stats()`를 거쳐 같은 repository UPSERT로 수렴한다.
- 재갱신 흔적: `updated_at > created_at` 29,103행. 반복 수집에도 초과 Row 0.
- 조회 영향: 현재 중복이 없어 COUNT, 최신값 JOIN, 이동평균 재계산 왜곡은 없다.
- 개선점: ORM 모델에는 UNIQUE 선언이 없고, 같은 `(stock_id, trade_date)` 일반 인덱스 2개와 선두 컬럼만의 인덱스 1개가 UNIQUE 인덱스와 겹친다.

### 4.2 `market_theme_daily_returns`

- Business Key: `(theme_id, return_date)`
- 기간: 2024-05-28 ~ 2026-08-25
- UNIQUE: SQLite autoindex로 실제 존재한다.
- 당일 갱신 helper: SELECT 후 있으면 UPDATE, 없으면 INSERT. UNIQUE가 중복을 막지만 원자적 UPSERT보다 동시성 오류 여지가 크다.
- 기간 재계산: `ON CONFLICT(theme_id, return_date) DO UPDATE`로 원자적 UPSERT.
- 재갱신 흔적: 4,241행 갱신, 총 추가 refresh 7,090회, 최대 refresh 8회. 초과 Row 0.
- 조회 영향: 월별 합계/평균, 관찰·예측 학습 입력, 최신 등락률 조회 모두 현재는 왜곡 없음. 중복이 생기면 다수 쿼리가 DISTINCT 없이 직접 읽으므로 실제 왜곡 가능성이 크며 UNIQUE 유지가 필수다.
- 개선점: UNIQUE와 완전히 같은 일반 인덱스 `idx_market_theme_daily_returns_theme_date`는 중복 후보다.

### 4.3 `market_theme_stock_daily_returns`

- Business Key: `(theme_id, stock_id, return_date)`
- 기간: 2024-05-28 ~ 2026-08-25
- UNIQUE: SQLite autoindex로 실제 존재한다.
- 당일 갱신: 해당 테마/일자의 기존 상세를 DELETE한 뒤 각 행을 SELECT→UPDATE/INSERT한다.
- 기간 재계산: 먼저 기존 행을 inactive로 바꾸고 배치 `ON CONFLICT(... ) DO UPDATE`한다.
- 재갱신 흔적: `updated_at > created_at` 16,589행. 초과 Row 0.
- 조회 영향: 현재 왜곡 없음. 중복이 생기면 테마 거래대금 합계, 종목 순위 window, 수급 JOIN이 부풀 수 있다. `market_theme_flow_trend_service` 일부 쿼리가 `MAX(trading_value)`/GROUP BY로 중복을 우연히 숨기지만 다른 소비자는 그렇지 않다.
- 개선점: 당일 경로를 DELETE+행별 SELECT 방식 대신 단일 UPSERT 배치와 명시적 stale-row 처리로 통일하면 잠금 시간과 race surface를 줄일 수 있다.

## 5. API → Service → DB 쓰기 흐름

주요 흐름은 다음과 같다.

```text
POST /stock-prices/collect/selected
POST /trade-training/stocks/{id}/collect-prices
POST /stock-tracking/items/collect-prices
테마 가격·수급 갱신 내부 가격 수집
  → StockPriceService._collect_and_upsert_with_stats
  → StockPriceRepository.upsert_daily_rows
  → INSERT ... ON CONFLICT(stock_id, trade_date) DO UPDATE

POST /external/kiwoom/market-themes/returns/refresh
  → ExternalKiwoomService.refresh_market_theme_returns
  → _upsert_market_theme_daily_return
  → _delete_market_theme_stock_daily_returns
  → _upsert_market_theme_stock_daily_return

POST /external/kiwoom/market-themes/{id}/recalculate-returns
  → ExternalKiwoomService.recalculate_market_theme_returns
  → 두 테이블 배치 INSERT ... ON CONFLICT DO UPDATE

POST /external/kiwoom/market-themes/returns-and-flows/refresh
  → MarketThemePriceFlowCollectionService.refresh
  → StockPriceService + TechnicalIndicatorService + StockInvestorFlowService
  → 위 공용 UPSERT repositories

POST /us-stocks/prices/collect
POST /us-market-themes/refresh 또는 /returns/recalculate
  → UsMarketDataService
  → 미국 일봉/테마 일별 ON CONFLICT DO UPDATE
```

운영 코드에서 핵심 일별 테이블로 가는 `dataframe.to_sql(append)`, `bulk_insert_mappings`, `bulk_save_objects` 우회 경로는 발견되지 않았다. 테스트 코드의 plain INSERT는 격리 테스트 fixture이며 운영 write path가 아니다.

## 6. Append-only/History로 제외한 테이블

다음은 같은 날짜의 여러 Row가 정상일 수 있어 EOD 최종값 중복으로 판정하지 않았다.

- `collection_runs`, `market_data_collection_runs`, `market_data_collection_run_items`: 실행 및 항목 이력
- `market_signal_evaluations`, `market_signal_events`, `market_signal_episodes`: 평가/상태전이 이벤트
- `market_theme_observation_runs`, `market_theme_observation_items`, validation samples/metrics: run, mode, model/version 차원을 가진 검증 이력
- `market_theme_return_prediction_runs/items/models/metrics`: 예측 run·방법·모델 버전 이력
- `backtest_runs`, `backtest_trades`, `backtest_equity_curve`: 백테스트 실행별 결과
- `simulation_sessions`, `simulation_snapshots`, `simulation_trades`: 시뮬레이션 세션별 이력
- `chart_marker_events`, `news_items`, `disclosures`, `telegram_items`: 이벤트/수집 항목
- `watchlist_evaluation_runs/scores/factors`: 평가 run별 결과
- `trade_journals`, `trade_reviews`, 위험 이벤트/원장 테이블: 거래·훈련 이력

`market_price_snapshots`는 별도 주의 대상이다. 현재 pykrx 수집은 기존 `source='pykrx'` 행 전체를 삭제한 뒤 현재 스냅샷을 plain INSERT하며, 실제 20행에서 `(source, stock_code)` 중복은 0이다. 그러나 UNIQUE가 없어 동시 수집에는 구조적으로 취약하다. 이 테이블을 “소스별 현재 스냅샷”으로 유지할지 “시간별 이력”으로 바꿀지 먼저 결정해야 Business Key를 확정할 수 있으므로 TYPE C/현재값 혼합으로 본 조사 표에서는 제외했다.

## 7. 인덱스 사용성 및 용량 영향

`dbstat`이 제공되지 않아 객체별 바이트는 측정하지 않았다. 대신 실제 Row 수를 기준으로 동일 키 인덱스의 엔트리 중복을 확인했다.

| Table | UNIQUE와 겹치는 인덱스 | 추가 검토할 prefix 인덱스 | 대략적인 중복 엔트리 수* |
|---|---|---|---:|
| `stock_daily_prices` | 동일 복합키 일반 인덱스 2개 | `stock_id` 1개 | 88,599 |
| `stock_daily_technical_indicators` | 동일 복합키 일반 인덱스 1개 | `stock_id` 1개 | 59,066 |
| `market_indicator_values` | 동일 복합키 일반 인덱스 1개 | 없음 | 28,629 |
| `stock_investor_flows` | 동일 복합키 일반 인덱스 1개 | 없음 | 24,960 |
| `market_index_daily_prices` | 동일 복합키 일반 인덱스 1개 | 없음 | 11,163 |
| `market_theme_daily_returns` | 동일 복합키 일반 인덱스 1개 | 없음 | 9,330 |
| `stock_daily_market_metrics` | 동일 복합키 일반 인덱스 1개 | `stock_id` 1개 | 52 |
| 합계 |  |  | **221,799** |

\* 인덱스별 Row당 엔트리 1개로 센 논리 엔트리 수이며 바이트 추정이 아니다.

UNIQUE B-tree는 동일 선두 컬럼 검색에도 사용할 수 있으므로 위 exact/prefix 인덱스는 제거 후보지만, 실제 변경 전 `EXPLAIN QUERY PLAN`, 주요 API 응답시간, 쓰기 성능을 비교해야 한다. 전체 DB에서는 이 밖에도 `stocks(stock_code)`, provider mapping, `price_collection_targets` 등 동일 키 중복 인덱스가 확인됐다.

중복 초과 Row Top 10은 대상 전부 0이므로 순위를 만들 수 없다. 대신 전체 Row 상위는 기술지표 29,533, 국내 일봉 29,533, 테마-종목 일별 29,126, 미국 일봉 29,077, 시장지표 28,629, 수급 24,960, 시장지수 일봉 11,163, 테마 일별 9,330, 미국 테마 일별 7,565 순이다. 이들은 정상 고유 Row이므로 삭제 대상이 아니다.

## 8. Root Cause 및 심각도

| 심각도 | 분류 | 대상 | 판정 |
|---|---|---|---|
| NORMAL | 정상 | 핵심 3개 및 표의 19개 | 실중복 0, UNIQUE 유효, 대부분 UPSERT |
| MEDIUM | TYPE 6 모델/스키마 불일치 | 국내 일봉·기술지표·시장메트릭 ORM 모델 | 모델에는 UNIQUE 없음, 실제 DB/초기화 SQL에는 있음 |
| MEDIUM | TYPE 9 인덱스 중복 | 핵심 일별 및 기타 여러 테이블 | 조회 이득 없이 쓰기·파일 공간 비용 가능 |
| LOW | TYPE 9 동시성/가용성 | 테마 당일 갱신, daily rank, Telegram 요약 | SELECT→INSERT race는 UNIQUE 위반 오류가 될 수 있으나 중복은 방지됨 |
| LOW | TYPE 1 + TYPE 3 구조 위험 | `market_price_snapshots` | UNIQUE 없이 DELETE→plain INSERT; 현재 실중복은 없음 |

CRITICAL/HIGH 데이터 중복 문제는 발견되지 않았다. 현재 UNIQUE를 제거하거나 초기화 경로가 달라지면 `ON CONFLICT`가 실패하거나 plain INSERT 경로에서 문제가 생길 수 있으므로 스키마 parity 개선은 선제적으로 필요하다.

## 9. 테스트 결과와 공백

기존 격리/인메모리 테스트 중 관련 14개를 실행했고 모두 통과했다.

- 국내 테마 기간 재계산 UPSERT
- 미국 일봉을 같은 데이터로 두 번 수집했을 때 첫 실행 INSERT 9, 두 번째 실행 UPDATE 9
- 수급 부분 UPSERT 순서가 바뀌어도 1행 유지 및 필드 보존
- 실시간 테마 UPSERT/실패 시 기존 스냅샷 보존

테스트 결과: `14 passed`. pytest cache 경로 권한 경고 1건은 테스트 결과와 무관하다.

보완해야 할 테스트는 다음과 같다.

1. 핵심 3개에 동일 키를 3회 저장: 최초 1행, 동일값 1행, 수정값 1행 및 최신값 반영.
2. 종목 선택/최근7일/전체/종목추적/테마수집/매매훈련이 같은 stock/date로 수렴하는 교차 경로 테스트.
3. 두 Session의 동시 UPSERT/동시 refresh 테스트와 busy timeout/재시도 검증.
4. ORM metadata, `schema.sql`, runtime ensure, migration, 실DB conflict target이 모두 같은지 검사하는 schema parity 테스트.
5. 모든 TYPE A/B 테이블의 Business Key 중복을 CI에서 검사하는 read-only invariant test.
6. `market_price_snapshots` 보존 의미 확정 후 반복/동시 수집 테스트.

## 10. 권장 수정안과 우선순위

### 1순위 — MEDIUM: 스키마 정의 단일화

- 국내 `StockDailyPrice`, `StockDailyTechnicalIndicator`, `StockDailyMarketMetric` 모델에 실제 Business Key UNIQUE를 명시한다.
- `schema.sql`, `scripts/init_db.py`, runtime schema, ORM 모델, SQL migration을 비교하는 자동 테스트를 둔다.
- 기존 실DB에는 이미 UNIQUE가 있으므로 이 단계에서 중복 정리나 신규 인덱스 생성은 불필요하다.

### 2순위 — MEDIUM: 중복 인덱스 정리

- 먼저 DB 백업 및 무결성 검사.
- 후보 인덱스별 `EXPLAIN QUERY PLAN`과 주요 API 성능을 기록.
- UNIQUE와 exact duplicate인 일반 인덱스를 우선 제거 검토.
- composite UNIQUE의 선두 컬럼과 같은 단일 인덱스는 쿼리 플랜 검증 후 제거 검토.
- 파일 공간 회수는 인덱스 제거와 무결성 확인 후 별도 승인으로 `VACUUM INTO`를 우선 고려한다.

### 3순위 — LOW: 저장 경로 원자화

- 테마 당일 집계/상세, daily rank, Telegram 요약을 `INSERT ... ON CONFLICT DO UPDATE`로 통일한다.
- 테마 상세의 “현재 멤버에서 제외된 행” 처리는 트랜잭션 내 명시적 stale update/delete로 분리한다.
- `market_price_snapshots`의 보존 정책을 확정한 뒤 적절한 UNIQUE+UPSERT 또는 명시적 history key를 적용한다.

### 안전한 향후 변경 순서

1. 실행 중 수집 작업 중지 또는 쓰기 창구 통제
2. DB와 WAL 상태를 포함한 백업 또는 SQLite backup API/`VACUUM INTO` 백업
3. 백업본 및 원본 `quick_check`/foreign key 검사
4. Business Key와 보존 규칙 재확인
5. 중복 재측정(현재는 0이므로 dedup 생략 가능)
6. 스키마/모델 parity 수정 및 원자적 UPSERT 정리
7. 인덱스 변경은 별도 migration으로 수행
8. 회귀·동시성·교차 수집 경로 테스트
9. 운영 반영 후 row 수/DB 크기/쿼리 성능 비교
10. 물리 공간 회수는 최종 검증 뒤 별도 승인

## 11. 사용자 승인 후 수행할 수 있는 작업

이번 조사에서는 DB와 운영 코드를 변경하지 않았다. 승인 후에는 다음을 작은 migration 단위로 나눠 수행할 수 있다.

1. ORM/스키마 UNIQUE parity 수정과 자동 검사 추가
2. 핵심 3개 반복 수집 불변조건 테스트 추가
3. SELECT→INSERT 저장 경로의 원자적 UPSERT 전환
4. 중복 인덱스의 쿼리 플랜 벤치마크 및 안전 제거
5. `market_price_snapshots` 보존 정책 확정과 키 설계
6. 백업·무결성 검증 후 필요 시 물리 공간 회수

현 상태에서는 데이터 dedup DELETE, UNIQUE 신규 생성, VACUUM을 즉시 수행할 이유가 없다.
