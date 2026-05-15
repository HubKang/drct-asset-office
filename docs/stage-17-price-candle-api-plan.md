# Stage 17 Price Candle API Plan

## Purpose
- Organize the deprecated price candle API surface after Stage 16 stabilization
- Keep production rules explicit around `source='pykrx'`
- Prepare a price-summary API shape for future GPT advisory packaging

## Deprecated API Direction
- Standard collection API: `POST /stock-prices/collect/selected`
- Removed API: `POST /stock-prices/update/selected`
- Removed frontend remnants:
  - `updateSelected`
  - `SelectedStockPriceUpdateRequest`
- Current frontend screens use `collectSelected` only

## Production Source Rule
- Operational daily price queries must use `source='pykrx'`
- `source='mock'` is structural-test data only
- Operational SQL, reports, and summaries should exclude non-`pykrx` rows by default

## Current trading_value Policy
- DB keeps missing `trading_value` as `NULL`
- UI shows `-`
- Summary or aggregate SQL may use `COALESCE` only when the business question requires it
- Price-summary API should exclude trading-value-based metrics for now

## Price Summary API Candidate
- Implemented route: `GET /stock-prices/{stock_id}/summary`
- Rejected alternative for now: `GET /analysis/price-summary/{stock_id}`

## Implemented Direction
- `GET /stock-prices/{stock_id}/summary`
- Reason:
  - it is a direct extension of the existing stock price domain
  - the response is still factual market data, not a generated interpretation
  - it keeps future GPT analysis layers separate from source data endpoints

## UI Connection Status
- `StockPricesPage` is now connected to `GET /stock-prices/{stock_id}/summary`
- When a user selects a stock in the left list, the detail panel loads:
  - latest close
  - recent 5 trading-day change rate
  - average volume over the latest 20 trading days
  - price position versus 52-week high
  - latest trade date
  - 52-week high
  - 52-week high date
  - MA5 / MA20 / MA60
  - price row count
  - collection date range
  - source
- `trading_value` remains excluded from the summary panel
- The daily table also avoids showing `trading_value` in the current operating view
- This summary block is intended to be reused later in the GPT advisory package as factual grounding data

## Backend Test Status
- Added API-level smoke tests for `GET /stock-prices/{stock_id}/summary`
- Covered cases:
  - `stock_id=10010` returns `200`
  - `stock_id=10803` returns `200`
  - missing `stock_id=99999999` returns `404`
- Verified response conditions:
  - `source` is `pykrx`
  - `price_count` is greater than zero for seeded examples
  - `latest_trade_date` and `latest_close_price` exist
  - `latest_ma5`, `latest_ma20`, `latest_ma60` fields exist
  - `trading_value` fields are absent
  - buy/sell wording is absent

## Frontend Test Status
- No dedicated frontend test runner is configured yet in `frontend/package.json`
- Current project does not include `vitest`, `jest`, or Testing Library
- For Stage 17, UI stability is covered by:
  - manual browser verification
  - build verification with `npm run build`

## Frontend Manual Checklist
1. Open `/#/stock-prices`.
2. Select `동화약품` or `stock_id=10010`.
3. Confirm summary card loading state appears before data is shown.
4. Confirm summary card shows latest close, 5-day change, 20-day average volume, and 52-week-high position near the top.
5. Confirm `NULL` values render as `-`.
6. Confirm no `trading_value` text is shown in the summary card or operating daily table.
7. Confirm no buy/sell wording is shown.
8. Select `두산로보틱스` or `stock_id=10803`.
9. Confirm summary card values update for the new stock.
10. Refresh the page and confirm the summary block loads again without breaking the screen.

## Implemented Fields
- `stock_id`
- `stock_code`
- `stock_name`
- `source`
- `price_count`
- `min_trade_date`
- `max_trade_date`
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

## Calculation Rules
- `source` default is `pykrx`
- `recent_5d_change_rate`
  - compares latest close with the close from 5 trading days earlier
  - returns `NULL` when fewer than 6 rows exist or the base close is missing
- `avg_volume_20d`
  - uses up to the most recent 20 trading-day rows
  - when fewer than 20 rows exist, averages the available non-null rows
- `high_52w`
  - uses the highest `high_price` within the most recent 252 trading-day rows
- `high_52w_date`
  - stores the trade date for the selected `high_52w`
- `price_position_vs_52w_high`
  - calculates `latest_close_price / high_52w * 100`
  - returns `NULL` when `high_52w` is missing or zero
- `trading_value`
  - excluded because the current PyKRX adjusted path does not provide stable source values

## Implemented Structure
- repository:
  - added stock summary window lookup by `stock_id` and `source`
  - added recent-row lookup for up to 252 trading days
- service:
  - enforces `source='pykrx'` by default
  - returns factual summary only
  - returns `404` when the stock or source-specific daily prices do not exist
- schema:
  - added a focused one-stock fact summary response model

## Next Work Suggestions
1. Add a lightweight frontend test runner when the team is ready to maintain UI tests.
2. Consider adding `latest_ma120` and `latest_ma240` later if the GPT advisory package needs longer trend context.
3. Reuse this factual summary API in GPT advisory packaging rather than duplicating SQL in prompts.
4. Add composition logic that merges price summary, news, disclosures, and theme data into one GPT package payload.
