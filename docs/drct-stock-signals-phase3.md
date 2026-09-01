# DrCT 종목 시그널 3단계

## 범위와 역할

3단계는 활성 국내 테마 연결 종목 Universe를 공통 분석일 기준으로 검사하는 Structured Rule Engine, Rule Builder, Runtime Preview와 종목별 진단을 제공한다. 성공패턴 Feature, 유사도, ML, 상승 확률, 최종 시그널 생성과 저장은 포함하지 않는다.

Kiwoom HTS 조건식은 매매훈련 후보 선정과 사람이 비교할 Reference다. 불완전한 HTS 문장을 자동 파싱·보정하지 않는다. DrCT Rule은 사용자가 별도로 구성하며, 운영 시 Kiwoom 조건검색 API를 호출하지 않고 내부 가격·시장가치 데이터만 평가한다.

## 저장 구조와 Version 정책

- `drct_signal_search_rules`: `search_version_id`당 하나의 소형 설정 JSON, schema version, `DRAFT/VALID/INVALID` 상태만 저장한다. Condition Type별 명시적 params allow-list를 통과한 필드만 영속화한다.
- Rule을 최초 구성하거나 수정할 때 현재 Search Version을 변경하지 않고 HTS Reference를 복사한 새 Version을 만든다.
- 기존 세 검색식 v1은 모두 Rule 미구성 상태로 유지한다. 자동 Rule Seed는 없다.
- Search Lifecycle과 Rule Validation은 독립적이며 VALID이 되어도 Lifecycle을 자동 변경하지 않는다.
- Preview 목록, 종목별 Condition 결과, 가격 시계열, Feature Matrix와 Preview History는 저장하지 않는다.

## Structured Rule Schema

```json
{
  "schema_version": 1,
  "conditions": [
    {
      "code": "A",
      "type": "PRICE_COMPARE_VALUE",
      "label": "종가 1,000원 이상",
      "configured": true,
      "params": {"price_field": "CLOSE", "offset": 0, "operator": "GTE", "value": 1000}
    }
  ],
  "expression": "A AND B"
}
```

지원 Condition Type은 `MARKET_CAP_COMPARE`, `PRICE_COMPARE_VALUE`, `PRICE_COMPARE_PRICE`, `MA_COMPARE`, `PRICE_MA_COMPARE`, `MA_TREND`, `CROSS_UP`, `CROSS_DOWN`, `PCT_CHANGE`, `DISTANCE_PCT`, `PERIOD_EXISTS_PRICE_CHANGE`, `PERIOD_VALUE_COMPARE`다. MA는 5/10/20/60/120/240만 지원한다. 봉 offset은 양수 하나로 통일하며 0은 분석 기준일, N은 N거래봉 전이다.

Boolean Expression은 Condition Code, `AND`, `OR`, 괄호만 토큰화하고 shunting-yard 방식으로 RPN 변환 후 평가한다. Python/JavaScript `eval`은 사용하지 않는다. 중복·미존재 코드, 미구성 조건, 잘못된 괄호·토큰·연산자·MA 기간을 검증한다.

## Universe와 분석일

Universe는 활성 `market_themes` 중 `theme_level='THEME'`인 행과 활성 `market_theme_stocks`, 활성 `stocks`의 교집합이다. 같은 종목이 여러 테마에 있어도 `stock_id`로 한 행만 만들고 모든 테마명을 유지한다.

기본 `analysis_date`는 이 Universe가 보유한 `stock_daily_prices`의 공통 단일 기준 최신일이다. 현재 데이터에서는 2026-08-31이다. 모든 종목을 이 날짜로 평가하며 종목별 다른 MAX 날짜를 사용하지 않는다. 명시 날짜가 있으면 그 날짜를 그대로 기준으로 삼는다.

가격·거래량·거래대금과 저장 MA는 `stock_daily_prices`에서 `trade_date<=analysis_date`로 먼저 제한한 뒤 종목별 필요한 Lookback만 bulk 조회한다. 시장가치는 `stock_daily_market_metrics.market_cap`의 `trade_date=analysis_date`만 사용하고 같은 날 복수 Source가 있으면 최종 갱신 행을 선택하며, 과거·미래 fallback은 하지 않는다. `stock_daily_technical_indicators`는 3단계 Rule 평가에 사용하지 않는다.

분석일 가격, 필요한 거래봉/MA/거래대금 또는 정확일 시장가치가 없으면 `NO_MATCH`가 아닌 `DATA_INCOMPLETE`다. Rule이 DRAFT/INVALID/미구성이면 Preview를 차단한다. Preview는 Universe, 가격, 시장가치를 bulk 조회한 뒤 Python에서 평가하여 조건 수에 비례한 SQL N+1을 만들지 않는다.

## API와 UI

- `GET /drct-stock-signals/rule-capabilities`
- `POST /drct-stock-signals/rules/validate`
- `POST /drct-stock-signals/searches/{id}/rule-versions`
- `POST /drct-stock-signals/searches/{id}/rule-preview`
- `POST /drct-stock-signals/searches/{id}/rule-diagnose`

Builder는 HTS Reference 옆에서 Condition Card 추가·수정·삭제, Boolean Expression 편집과 즉시 검증을 제공한다. 저장은 새 Version을 만든다. VALID Current Version만 검색식 테스트가 가능하다. Preview는 분석일, 전체/평가가능/데이터부족/조건만족 수와 종목·코드·테마·종가·상태를 표시하며, 종목 진단은 기준·실제값·PASS/FAIL/DATA_INCOMPLETE를 요청 시 조회한다.

## 미래 데이터 차단

가격 조회 CTE 안에서 먼저 `trade_date<=analysis_date`를 적용한 후 row number와 offset을 계산한다. 시장가치는 정확한 분석일만 허용한다. 미래 데이터를 포함해 지표를 계산한 뒤 잘라내는 방식은 사용하지 않는다.

## 4단계 준비 조사

- `chart_marker_events`의 D0 식별 컬럼은 `id`, `stock_id`, `marker_id`, `marker_date`, `review_result`다. Unique Key는 `(stock_id, marker_id, marker_date)`다.
- `ChartMarkerService.review_chart`는 D0 행을 찾고 이전 최대 60봉, 이후 최대 20봉을 각각 날짜 제한 Query로 조회한다.
- 기술지표는 `(stock_id, trade_date)` Unique인 `stock_daily_technical_indicators`의 D0 정확일 Row로 접근 가능하다.
- 현재 Marker 133건 중 D0 가격은 133건, D0 기술지표는 97건, D0 포함 이전 60봉 이상은 103건이다.
- 복기 판정은 SUCCESS 29건, FAILURE 21건, 미판정 83건이다. 현재 세 Search에는 Marker Link가 아직 없어 검색식별 사례는 0건이다.
- D+5/D+10/D+20 가격 가용 사례는 각각 133/132/130건이다. D0 이후 고가·저가 시계열로 MFE/MAE를 Runtime 계산할 수 있다.
- 동일 종목·동일 일자에 다른 Marker가 허용되므로 Event ID가 사례 단위다. 학습 중복 방지 후보는 `(search_id, search_version_id, chart_marker_event_id)`이며, 같은 종목·날짜의 복수 Marker를 합칠지는 4단계 Label 정책에서 결정해야 한다.
- 검색식별 사례는 Search → `drct_signal_search_marker_links.marker_definition_id` → `chart_marker_events.marker_id` JOIN으로 추출할 수 있다.

4단계에서는 이 원천을 기반으로 D0 이전 Feature Dataset과 해석 가능한 Baseline Algorithm을 설계하되, 원시 시계열과 재생성 가능한 Feature Matrix는 영속 저장하지 않는 정책을 유지한다.
