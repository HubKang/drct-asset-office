# DrCT에셋 DB 테이블 변경 내역 (2026-05-11)

기준 DB: `db/drct_asset.sqlite3`

## 1) 신규 테이블
### `stock_daily_prices` (신규 추가)
- 목적: 관심종목 일봉/가격/거래량/이동평균 저장
- 주요 컬럼
  - `id` (PK)
  - `stock_id` (FK -> `stocks.id`)
  - `trade_date`
  - `open_price`, `high_price`, `low_price`, `close_price`
  - `change_price`, `change_rate`
  - `volume`, `trading_value`
  - `ma5`, `ma10`, `ma20`, `ma60`, `ma120`, `ma240`
  - `source`, `created_at`, `updated_at`

## 2) 기존 테이블 컬럼 추가
### `watchlist`
- 추가 컬럼: `is_active INTEGER NOT NULL DEFAULT 1`
- 목적: 관심종목 활성/비활성 상태 관리

## 3) 인덱스/제약 추가
### `stock_daily_prices` 인덱스
- `ux_stock_daily_prices_stock_date` (UNIQUE: `stock_id`, `trade_date`)
- `idx_stock_daily_prices_stock_date` (`stock_id`, `trade_date`)
- `idx_stock_daily_prices_trade_date` (`trade_date`)

## 4) 스키마 코멘트 추가
- `schema_comments`에 아래 설명 추가
  - `stock_daily_prices` 테이블/컬럼 설명
  - `watchlist.is_active` 컬럼 설명

## 5) 적용 스크립트/파일
- `backend/app/sql/schema.sql`
- `scripts/init_db.py`

## 6) 현재 DB 반영 확인
- 테이블 목록 조회 결과: `stock_daily_prices` 존재 확인
- 확인 SQL
```sql
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name;
```

---
참고:
- 오늘 작업에서 SQLite 안정화를 위해 DB 연결 PRAGMA(`WAL`, `busy_timeout` 등) 설정이 추가되었으나, 이는 **테이블 구조 변경**이 아니라 **운영 설정 변경**입니다.
