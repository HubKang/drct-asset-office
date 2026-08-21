# 미국 종목 Universe 1차 구현

## 범위

- 기존 국내 `stocks` 및 KRX 동기화 흐름은 변경하지 않는다.
- 선택적으로 추적할 미국 종목만 신규 `us_stocks` 테이블에 저장한다.
- 미국 가격, 차트, 테마, 한·미 테마 연결은 이 단계에 포함하지 않는다.

## 데이터 모델

`us_stocks`는 `symbol + exchange`를 중복 기준으로 사용한다. 운영 필드만 저장하며 외부 API 원문 JSON은 저장하지 않는다.

- `symbol`, `name`, `name_ko`
- `exchange`, `stock_type`
- `naver_code` (nullable)
- `is_active`, `last_synced_at`
- `created_at`, `updated_at`

스키마는 `backend/app/sql/migrations/037_us_stocks.sql`과 런타임의 비파괴적 `CREATE TABLE IF NOT EXISTS` 경로에 반영한다.

## API

- `GET /us-stocks`: 검색, 거래소/유형/활성 필터, 서버 페이지네이션
- `GET /us-stocks/summary`: 등록/활성/보통주/ETF 집계
- `POST /us-stocks`: 단건 등록
- `PATCH /us-stocks/{id}`: Ticker를 제외한 정보 수정 및 활성/비활성
- `POST /us-stocks/bulk/preview`: 입력 정규화, 중복 및 형식 오류 미리보기
- `POST /us-stocks/bulk`: 미리보기 기준 신규 Ticker만 등록

## 외부 종목 조회

현재 저장소에서 공식 정의와 실제 동작이 확인된 Kiwoom 미국 종목정보 조회 TR을 찾지 못했으므로 Ticker 자동조회는 구현하지 않았다. 회사명, 거래소, 유형은 수동 입력을 지원하며 Naver Code는 suffix를 추측 생성하지 않는다.
