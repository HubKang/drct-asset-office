# 월별 수급 테마 현재 분류 집계

## 목적

월별 수급 캘린더, 선택일 상세, 최근 1개월 히트맵·트리맵, 상단 요약은 같은 분류 기준을 사용한다. 저장 당시의 이벤트-테마 연결은 감사용 원천 이력으로 보존하고, 화면 집계에서는 조회 시점의 현재 활성 종목-테마 연결을 적용한다.

## 집계 기준

1. 기간 내 활성 수급 이벤트 후보를 조회한다.
2. 이벤트 종목을 `market_theme_stocks`의 현재 활성 연결로 해석한다.
3. 활성 `market_themes`와 활성 상위 테마그룹만 포함한다.
4. `(trade_date, theme_id, stock_id)` 단위로 중복을 제거한다.
5. 등락률 평균에서는 `NULL`을 제외하며 유효한 등락률이 없으면 `NULL`로 반환한다.
6. 기간 내 한 번이라도 종목이 감지된 모든 활성 테마를 반환한다. 화면의 히트맵도 임의 상위 N개로 자르지 않는다.

공통 구현은 `ExternalKiwoomService._build_supply_theme_aggregation`이며 월별 캘린더, 30일 요약, 월별 추이 API가 이 결과를 소비한다.

## 데이터 보존

- `market_trend_events`와 `market_trend_event_theme_links`의 과거 값은 갱신하거나 삭제하지 않는다.
- 현재 분류 결과를 별도 JSON이나 차트 시계열로 저장하지 않는다.
- 집계는 조회 시점에 생성하며 재현 가능한 상세 데이터를 추가 보관하지 않는다.

따라서 테마명 변경, 테마그룹 이동, 종목의 테마 재분류는 원천 이벤트를 훼손하지 않고 다음 조회부터 화면 전체에 반영된다.

## 진단 정보

월별 캘린더와 추이 응답은 `diagnostics`를 제공한다.

- `classification_basis`: `CURRENT_ACTIVE_THEME_MAPPING`
- `event_count`: 기간 내 원천 이벤트 수
- `unique_stock_count`: 기간 내 고유 이벤트 종목 수
- `active_theme_count`: 현재 분류로 연결된 활성 테마 수
- `reclassified_event_stock_count`: 저장 당시 연결과 현재 연결이 다른 날짜-종목 수
- `unclassified_stock_count`: 현재 활성 테마 연결이 없는 고유 종목 수
- `period_start_date`, `period_end_date`: 진단 대상 기간

운영 로그 `[monthly-supply-current-classification]`에도 같은 핵심 수치와 처리 시간이 기록된다.

## 검증 포인트

- 과거 테마에서 새 테마로 이동한 종목은 새 테마로 집계된다.
- 상위 그룹명 변경 및 그룹 이동은 현재 명칭과 구조로 표시된다.
- 같은 날짜·종목·테마의 이벤트가 중복되어도 한 번만 집계된다.
- 비활성 테마에만 연결된 종목은 테마 집계에서 제외되고 미분류 진단에 포함된다.
- 현재 `건설` 연결 종목은 2026-07-10, 2026-07-22, 2026-07-23의 월별 흐름에 반영된다.