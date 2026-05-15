# Stage 18 Advisory Evidence Package

## Purpose

Create a factual evidence package for GPT advisory workflows by reusing:

- `GET /stock-prices/{stock_id}/summary`
- `GET /market-metrics/{stock_id}/summary`

This package is grounding data only. It must not contain automatic buy/sell conclusions.

## API

- `GET /advisory/evidence-package/{stock_id}`

Query parameters:

- `price_source`
  - default: `pykrx`
- `market_metrics_source`
  - default: `marcap`

## Response Blocks

- `stock`
- `price_summary`
- `market_metrics_summary`
- `data_quality_notes`
- `instruction_guardrails`
- `generated_at`

## Included Fields

### stock

- `stock_id`
- `stock_code`
- `stock_name`

### price_summary

- `latest_trade_date`
- `latest_close_price`
- `latest_ma5`
- `latest_ma20`
- `latest_ma60`
- `recent_5d_change_rate`
- `avg_volume_20d`
- `high_52w`
- `high_52w_date`
- `price_position_vs_52w_high`
- `price_count`
- `source`

### market_metrics_summary

- `latest_market_metrics_date`
- `latest_price_trade_date`
- `is_stale`
- `stale_days`
- `staleness_level`
- `market`
- `trading_value`
- `market_cap`
- `listed_shares`
- `trading_volume`
- `trading_value_rank`
- `market_trading_value_rank`
- `trading_value_percentile`
- `market_trading_value_percentile`
- `source`
- `data_note`

## Excluded Items

- news summary
- disclosure summary
- theme summary
- telegram theme summary
- automatic buy/sell statements
- target price suggestions

## Reuse Policy

- `price_summary` is required
  - if missing, return `404`
- `market_metrics_summary` is optional
  - if missing, return `null`
  - add a note to `data_quality_notes`

## Staleness Handling

When market metrics are older than the latest price date:

- preserve `staleness_level`
- preserve `stale_days`
- add an explicit note to `data_quality_notes`
- keep the raw `data_note` from the market metrics summary

## Guardrails

The evidence package should always include guardrails equivalent to:

- Use this package as factual grounding data only.
- Do not generate automatic buy, sell, or target-price conclusions from this package alone.
- If market metrics are stale or missing, state that limitation explicitly before any interpretation.

## Future Expansion

Later advisory packaging can append:

- `news_summary`
- `disclosure_summary`
- `theme_summary`
- `telegram_theme_summary`

The current package is intentionally narrow so the price and market-metrics grounding path can be tested first.

## UI Connection

`StockPricesPage` now exposes the evidence package through a user-triggered flow:

- button: `GPT 근거 패키지 불러오기`
- card title: `GPT 자문 근거 패키지`
- default state: collapsed / not loaded

The card shows:

- stock name and code
- generated time
- latest price date
- latest market-metrics date
- staleness status
- included blocks
- `data_quality_notes`
- `instruction_guardrails`

## JSON View And Copy

The UI includes:

- `JSON 보기` / `JSON 숨기기`
- `GPT용 JSON 복사`

Copy behavior:

- copies the full pretty-printed evidence package JSON
- includes `data_quality_notes`
- includes `instruction_guardrails`
- preserves stale metadata

## Stale Display

When `market_metrics_summary.staleness_level` is stale:

- show the stale badge
- surface `data_quality_notes` near the top of the card
- do not convert stale status into buy/sell guidance

## User Checkpoints

- load the package only when needed
- verify stale status before reuse
- confirm `trading_value` exists only under `market_metrics_summary`
- confirm no automatic buy/sell wording exists in the JSON payload

## Korean UI Cleanup

- 화면 표시 문구는 한글 우선으로 유지한다.
- JSON 필드명은 기존 `snake_case`를 유지한다.
- `data_quality_notes`, `instruction_guardrails`, `scenario_questions_for_gpt` 값은 한글 문구를 기본으로 사용한다.
- `Data Quality Notes`, `Instruction Guardrails`, `swing weight`, `long-term weight` 같은 영문 안내 문구는 사용자 화면에서 사용하지 않는다.

## Option UI

`StockPricesPage` now includes a `GPT 자문 패키지 옵션` card between the market-metrics summary and the evidence-package result card.

Options exposed in the UI:

- `최근 1년 캔들 참조 포함` -> `include_candle_reference`
- `전체 252개 raw candle 포함` -> `include_raw_candles`
- `유사 패턴 분석 포함` -> `similar_case_limit > 0`
- `투자 관점` -> `strategy_horizon`
- `패턴 기준 기간` -> `pattern_window`
- `유사 사례 개수` -> `similar_case_limit`
- `시나리오 질문 포함` -> `include_scenario_questions`

Additional parameters currently kept at fixed defaults in the UI:

- `price_source=pykrx`
- `market_metrics_source=marcap`
- `lookback_days=252`
- `recent_candle_limit=60`

## Query Mapping

Example request:

`GET /advisory/evidence-package/{stock_id}?price_source=pykrx&market_metrics_source=marcap&include_candle_reference=true&lookback_days=252&recent_candle_limit=60&include_raw_candles=false&pattern_window=20&similar_case_limit=5&strategy_horizon=both&include_scenario_questions=true`

## JSON Toggle And Copy

The UI keeps JSON collapsed by default.

- `JSON 보기`
- `JSON 숨기기`
- `GPT용 JSON 복사`

The copy action uses `navigator.clipboard` first and falls back to a hidden textarea copy path when the browser focus policy blocks direct clipboard writes.

## Interpretation Rules

- Raw candle inclusion can make the JSON payload substantially larger.
- Similar-pattern analysis is presented as historical reference cases only.
- Similar-pattern follow-up returns are not predictions.
- The UI must not render automatic buy/sell language or target-price guidance.

## Browser E2E Checklist

1. Open `가격·캔들 관리`
2. Select `동화약품`
3. Load default GPT evidence package
4. Open JSON view
5. Copy GPT JSON
6. Enable candle reference
7. Enable similar-pattern analysis
8. Reload GPT evidence package
9. Confirm `price_candle_reference`
10. Confirm `similar_pattern_cases`
11. Confirm `scenario_questions_for_gpt`
12. Switch to `두산로보틱스`
13. Confirm package reset
14. Reload and copy again

## Test

- `GET /advisory/evidence-package/10010`
- `GET /advisory/evidence-package/10803`
- `GET /advisory/evidence-package/99999999`

Expected:

- `10010` -> `200`
- `10803` -> `200`
- `99999999` -> `404`
- `price_summary` present
- `market_metrics_summary` present for current `marcap` sample data
- `data_quality_notes` present
- `instruction_guardrails` present
- no automatic buy/sell wording
