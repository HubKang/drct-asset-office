# 테마 맥락별 연결 종목 수급 이력

## 목적

시장 테마 관리의 연결 종목 상세는 특정 테마 목록에서 열린다. 수급 이력 패널은 현재 조회 테마의 수급 이력과 종목 전체 이력을 동시에 제공하되 두 범위를 명확하게 구분한다.

원천 `market_trend_events`와 `market_trend_event_theme_links`는 수정하거나 재분류하지 않는다. 화면용 집계만 조회 시 생성하며 별도 JSON·시계열 상세를 저장하지 않는다.

## 집계 범위

### 현재 조회 테마

- 최근 30일 고유 수급일 수
- 전체 기간 고유 수급일 수
- 최초·최근 수급일
- 전체 수급 날짜 목록

테마별 중복 제거 키는 `(theme_id, stock_id, detected_date)`이다. 같은 날짜에 같은 테마로 여러 조건검색 이벤트가 발생해도 1회다.

### 종목 전체

- 현재 활성 연결 테마별 고유 수급일 수
- 테마 중복을 제거한 종목 전체 고유 수급일 수
- 종목의 전체 메모

종목 전체 중복 제거 키는 `(stock_id, detected_date)`다. 같은 날짜가 여러 테마에 연결되어도 종목 전체에서는 1회다.

## 과거 연결과 현재 연결

테마별 날짜는 이벤트가 저장될 당시의 `market_trend_event_theme_links`를 사용한다. 링크 테이블이 없는 구형 이벤트만 `market_trend_events.theme_id`로 보완한다. 현재 활성 `market_theme_stocks`는 패널에 표시할 테마 목록을 정하는 데 사용한다.

따라서 현재 활성 테마마다 모든 과거 날짜를 복제하지 않으며, 과거의 테마별 수급 구분을 유지한다.

## 응답 구조

`GET /market-themes/{theme_id}/stocks/{stock_id}/supply-summary`는 다음 정보를 함께 반환한다.

- `current_theme`
- `linked_theme_supply_summaries`
- `period_start_date`, `period_end_date`
- `recent_30d_theme_supply_count`
- `current_theme_supply_count`
- `overall_stock_supply_count`
- `latest_current_theme_supply_date`, `first_current_theme_supply_date`
- `current_theme_supply_dates`
- `overall_stock_supply_dates`
- `stock_memos[].is_current_theme_supply_date`

기존 응답 필드는 호환성을 위해 유지한다.

## 화면 강조 정책

기본 강조색은 `#dc2626`이다. 다음 요소에 같은 빨간 계열의 옅은 배경과 테두리를 적용한다.

- 현재 테마 칩
- 현재 테마 기준 요약 카드
- 현재 테마 수급 날짜 칩
- 현재 테마 수급일과 같은 날짜의 종목 메모

다른 테마 칩, 전체테마 수급횟수 카드, 다른 테마 날짜의 메모는 중립색으로 표시한다. 메모는 강조 여부와 관계없이 모두 유지한다.

수급 날짜는 10개까지 기본 표시하고 초과분은 전체 보기로 펼친다. 제목의 건수는 항상 전체 날짜 수다.

## 서진시스템 사례

2026-07-27 기준:

- 전력인프라: 3회 (`2026-07-15`, `2026-07-10`, `2026-06-29`)
- 신재생에너지/ESS: 2회 (`2026-07-23`, `2026-07-01`)
- 종목 전체 고유 수급일: 5회

전력인프라에서 상세를 열면 세 날짜와 해당 메모만 강조한다. 신재생에너지/ESS에서 열면 두 날짜와 해당 메모만 강조한다. 두 화면 모두 전체 메모 5개를 표시한다.

## 진단 로그

서비스는 `[THEME CONTEXT SUPPLY HISTORY]` 로그에 종목코드, 현재 테마, 테마별 횟수, 현재 테마 날짜, 종목 전체 날짜, 메모 수를 기록한다.