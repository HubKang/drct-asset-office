# DrCT 종목 시그널 2단계

## 역할과 경계

Kiwoom HTS 검색식은 매매훈련 대상 종목을 찾고 차트마커 사례를 축적하기 위한 참조 원본이다. DrCT 종목 시그널 실행 시 HTS 조건검색 API를 호출하지 않는다. 향후 DrCT 검색식은 활성 국내 테마 연결 종목을 현재 저장 가격으로 직접 검사하는 내부 Rule이며, HTS 문자열을 실행식으로 해석하지 않는다.

2단계는 검색식 관리, HTS 참조식 보존, Version 이력, 검색식과 차트마커 정의의 연결, 기존 복기 판정 집계까지만 구현한다. Rule 실행, 후보 탐지, Feature 생성, 모델 학습과 시그널 생성은 포함하지 않는다.

## 데이터 구조

- `drct_signal_searches`: 검색식 Master. 변경 가능한 이름, 설명, 표시 순서, Lifecycle과 활성 상태를 보관한다. `search_key`는 초기 Seed와 시스템 식별을 위한 안정 키다.
- `drct_signal_search_versions`: HTS 참조 조건, HTS 최종 조건식, 사람이 읽는 DrCT Rule Draft와 변경 메모를 불변 Version으로 보관한다. 검색식마다 `is_current=1`인 행은 하나뿐이다.
- `drct_signal_search_marker_links`: 검색식 Master와 `chart_markers` 정의의 N:M 연결만 보관한다. 개별 `chart_marker_events`는 연결하지 않는다.

검색식 내용 변경은 기존 Version을 수정하지 않고 다음 `version_no`를 생성한다. Marker 연결은 Version별로 복제하지 않는다. 비활성화는 Master 상태만 바꾸며 Version과 Marker 연결을 삭제하지 않는다.

## HTS 참조식 보존

초기 3개 검색식은 `D:/21. Codex/04. DrCT에셋/DrCT 검색식.txt`에 존재하는 문자열만 사용한다. 원본에서 끝이 끊긴 상세이평비교, 거래대금 등의 문구도 추측으로 보완하지 않는다. 쌍바닥의 최종 조건식은 원본의 `A and B and C and D and E and F and G and H and I`을 그대로 유지한다.

## 차트마커와 학습 사례

연결 대상은 마커 Master인 `chart_markers.id`다. 기존 `chart_marker_events.review_result`의 실제 값인 `SUCCESS`, `FAILURE`, `NULL`을 각각 성공, 실패, 미판정으로 집계한다. 전체 건수, 상태별 건수와 최근 사례일은 API 요청마다 JOIN 집계하며 신규 테이블에 복제 저장하지 않는다. OHLCV, 기술지표, Feature Matrix도 2단계에서 저장하지 않는다.

## API

Base URL은 `/drct-stock-signals`이다.

- `GET /searches`, `GET /searches/{id}`
- `POST /searches`, `PATCH /searches/{id}`
- `GET /searches/{id}/versions`, `POST /searches/{id}/versions`
- `PUT /searches/{id}/marker-links`
- `GET /marker-options`
- `GET /searches/{id}/training-summary`

물리 삭제 API는 제공하지 않는다.

## 초기 Seed와 재실행

`DOUBLE_BOTTOM_TREND_REVERSAL`, `MA_ADJUSTMENT_5_10_20_60`, `DRCT_PULLBACK` 세 안정 키를 사용한다. 동일 `search_key` 또는 이름이 이미 있으면 아무 값도 덮어쓰지 않는다. 새 행에만 `REFERENCE`, v1과 원본 문자열을 등록하므로 초기화 재실행 시 중복되지 않는다.

## 3단계 Rule Engine 준비 조사

- 활성 국내 테마는 `market_themes.is_active=1`과 `theme_level='THEME'`, 연결은 활성 `market_theme_stocks`를 기준으로 조회할 수 있다. `RealtimeThemeService`는 연결 행을 읽은 뒤 `stock_id` 딕셔너리로 동일 종목을 중복 제거한다.
- 가격은 `stock_daily_prices(stock_id, trade_date)`를 기준으로 날짜 내림차순과 `LIMIT`을 사용하는 기존 조회가 있다. `ChartMarkerService.review_chart`와 가격 Repository 패턴을 재사용하면 기준일 이전 240봉을 조회할 수 있다.
- `stock_daily_prices`에는 OHLCV, 거래대금과 MA5/10/20/60/120/240 저장값이 있다. 최신 완료 일봉은 종목별 `MAX(trade_date)` 패턴을 사용한다.
- `stock_daily_technical_indicators`는 종목·거래일 단위 upsert Repository가 있고 RSI14, MACD, Bollinger Band, ATR14, MA 이격도, 거래량 비율을 저장한다.
- 시가총액은 일자별 `stock_daily_market_metrics.market_cap`이 주 데이터 후보이며, 일부 금융 Snapshot과 시장 탐지 Snapshot에도 존재한다. Rule Engine에서는 기준일 정합성을 위해 일별 시장지표를 우선해야 한다.
- 현재 세 검색식에서 단순 가격/MA 비교, MA 배열, 등락률, 기간 내 조건은 기존 가격·MA로 계산 가능하다. HTS의 불완전한 상세이평비교 문장과 정확한 거래대금 임계치는 원본 보완 전에는 실행 Rule로 확정할 수 없다.
- 최소 연산자 후보는 `GT`, `GTE`, `LT`, `LTE`, `BETWEEN`, `MA_COMPARE`, `PRICE_MA_COMPARE`, `MA_TREND`, `PRICE_CHANGE`, `CROSS_UP`, `WITHIN_RANGE`, `N_BARS_LOOKBACK`, `AND`, `OR`다. 2단계에서는 Schema나 실행 코드를 만들지 않는다.

## 다음 단계

3단계에서 현재 세 검색식을 정확히 표현하는 최소 Rule Schema, 기준일과 데이터 준비 조건, 활성 테마 Universe 조회, 실행 결과의 일시 응답 구조를 별도로 설계한다.
