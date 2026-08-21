# 미국 시장 테마 Phase 2: 가격·등락률·강도

## 구현 범위

- 미국 종목 전용 일봉 `us_stock_daily_prices`
- 미국 테마 전용 일별 집계 `us_theme_daily_returns`
- Kiwoom 미국 일봉 과거가격·증분 수집 및 종목별 부분 실패 요약
- 단순등락률, 20% 절사평균, 중앙값, 상승비율, 기존 실시간 테마강도식 집계
- 미국 종목 화면의 최신 종가·등락률·가격일·수집 상태
- 미국 테마 화면의 종가·테마 갱신, 최신 집계 열, 20/30/60일 히트맵·선그래프와 구성종목 상세

스케줄러는 이번 단계에서 추가하지 않았다. 공급자 원본 응답은 메모리에서 명시 필드만 파싱하며 DB와 응답에 저장·노출하지 않는다.

## Kiwoom 실제 계약

- Method/URL: `POST https://api.kiwoom.com/api/us/chart`
- API ID: `usa06012` (미국주식 일 차트)
- 요청 헤더: `authorization`, `api-id`; 연속조회 시 `cont-yn`, `next-key`
- 요청 Body: `stex_tp`, `stk_cd`, `strt_dt`, `upd_stkpc_tp=1`, `exrt_appl_tp=0`
- 사용 응답: `result_list[].dt`, `cur_prc`, `open_pric`, `high_pric`, `low_pric`, `acc_trde_qty`
- 연속조회: 응답 헤더 `cont-yn=Y`이면 응답 `next-key`를 다음 요청 헤더에 전달한다.
- 거래소 매핑: `NASDAQ -> ND`, `NYSE -> NY`, `NYSE_AMERICAN -> NA`; `OTHER`는 수집 대상에서 개별 실패 처리한다.

## 저장·계산 규칙

- `(us_stock_id, trade_date)` 및 `(theme_id, trade_date)` UNIQUE + UPSERT
- 공급자에 존재하지 않는 휴장일 행은 생성하지 않는다.
- 증분 수집은 종목별 `MAX(trade_date)` 이후 행만 저장한다.
- 활성 테마·연결·종목만 계산하고 연결 역할 또는 종목 유형이 ETF이면 제외한다.
- 종목 수익률은 종목별 직전 거래일 종가 대비 백분율이다.
- 단순등락률은 동일가중 평균이며 대표 종목 가중치는 추가하지 않는다.
- 유효 종목이 2개 미만인 테마·날짜는 집계하지 않는다.
- 테마강도는 `realtime_theme_service.calculate_theme_strength`를 직접 재사용한다.
- 현재 활성 연결 관계로 과거를 재계산하며 과거 구성 이력은 복원하지 않는다.

## API

- `POST /us-stocks/prices/collect`
- `GET /us-stocks/{stock_id}/prices`
- `POST /us-market-themes/refresh`
- `POST /us-market-themes/returns/recalculate`
- `GET /us-market-themes/returns/latest`
- `GET /us-market-themes/returns/trend?period=20|30|60`
- `GET /us-market-themes/themes/{theme_id}/returns/{trade_date}`

동시 실행은 프로세스 락으로 거절(`409`)한다. 가격 수집은 개별 종목 실패가 전체 성공 종목을 롤백하지 않으며 실패 종목·사유와 성공/실패/신규/갱신 건수만 반환한다.

## 2026-08-21 실데이터 확인

- 대상: NVDA, AMD, AVGO, AMAT, MSFT, CEG, IONQ, RKLB
- 결과: 8/8 성공, 종목당 260거래일, 총 2,080건
- 범위: 2025-08-08 ~ 2026-08-20
- 중복: 0건
- 주말 행: 0건
- 비정상 OHLCV: 0건
- 직후 증분 재실행: 신규 0건, 갱신 0건

운영 DB의 활성 미국 테마 12개를 현재 연결 관계로 재계산했다. 지정 8종목만 가격 검증 범위에 포함했기 때문에 최소 2종목 조건을 충족한 `AI 반도체/GPU`에서 259거래일 집계가 생성됐고, 나머지 부족 조합 1,295건은 제외됐다. ETF 제외, 최소 2종목, 등락률, 상승비율과 기존 강도식 일치는 격리 DB 자동 테스트에서도 별도로 검증했다.
