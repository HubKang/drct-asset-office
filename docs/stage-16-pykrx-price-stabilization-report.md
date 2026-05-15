# DrCT Asset Stage 16 Closing Report Draft

## Stage
- Stage 16: PyKRX daily price collection stabilization

## Purpose
- Simplify the production daily-price flow around `source=pykrx`
- Stabilize the Watchlist Pool and Stock Prices screens for operations
- Verify the unified `POST /stock-prices/collect/selected` flow for initial backfill, incremental collection, and latest refresh

## Changed Files
- `backend/app/api/routes_stock_prices.py`
- `backend/app/collectors/prices/pykrx_price_collector.py`
- `backend/app/repositories/stock_price_repository.py`
- `backend/app/schemas/stock_price_schema.py`
- `backend/app/services/stock_price_service.py`
- `frontend/src/index.css`
- `frontend/src/pages/StockPricesPage.tsx`
- `frontend/src/pages/WatchlistPage.tsx`
- `frontend/src/services/api/apiClient.ts`
- `frontend/src/services/api/stockPriceApiRepository.ts`
- `frontend/src/services/mock/stockPriceMockRepository.ts`
- `frontend/src/types/stockPrice.ts`

## Verified Screens
- `/#/watchlist`
- `/#/stock-prices`
- `/#/collection-runs`
- `/#/news`
- `/#/disclosures`

## Verified APIs
- `GET /health`
- `POST /stock-prices/collect/selected`
- `POST /stock-prices/update/selected` (deprecated header check at Stage 16 time)
- `GET /stock-prices/summary`
- `GET /stock-prices/{stock_id}/daily`

## DB Validation Results
- `stock_daily_prices` by source:
  - `pykrx`: 970 rows
  - `mock`: 0 rows after manual cleanup
- `pykrx` stored ranges:
  - `stock_id=10010`: `2024-05-13 ~ 2026-05-12`, `485 rows`
  - `stock_id=10803`: `2024-05-13 ~ 2026-05-12`, `485 rows`
- Recent collection behavior:
  - `watchlist_selected_price_backfill_collector`
  - `requested=2 success=2 failed=0 skipped=0 saved=10 source=pykrx`

## Trading Value Policy
- Keep source missing values as `NULL` in DB
- Show `-` in the UI for missing values
- Do not convert missing values to `0` in business logic
- Use `COALESCE(trading_value, 0)` only in aggregate queries when needed

## Trading Value Root Cause
- The current collector calls `pykrx.stock.get_market_ohlcv_by_date(..., adjusted=True)`.
- In the PyKRX adjusted path, the library uses the Naver wrapper.
- That raw DataFrame contains `date/open/high/low/close/volume` and derived `change_rate`.
- A raw `trading_value` column is not provided in that path.
- As a result, `trading_value` remains `NULL` naturally.
- Repository, schema, and upsert logic are not dropping `trading_value`.

## Deprecated update/selected Policy
- Production recommended API: `POST /stock-prices/collect/selected`
- At Stage 16 time, `POST /stock-prices/update/selected` remained for backward compatibility
- Applied signals:
  - FastAPI `deprecated=True`
  - Response header `Deprecation: true`
  - Response header `Warning: 299 - "Use POST /stock-prices/collect/selected instead."`
- Frontend screens no longer called `updateSelected`
- Repository methods remained with deprecated comments for staged removal

## Mock Data Review
- Manual cleanup removed remaining `mock` data before Stage 17 work
- Production UI and current production requests use `source=pykrx`
- Risk of mixing exists only when ad-hoc SQL or APIs omit the source filter
- Reference SQL used for manual cleanup:

```sql
DELETE FROM stock_daily_prices
WHERE source = 'mock';
```

## Open Issues
- Stage 16 ended before deprecated `updateSelected` removal work started
- If `trading_value` becomes a hard requirement, a different PyKRX path or supplemental source review is needed
- Mock cleanup is complete, but operational SQL should still default to `source='pykrx'`

## Next Step Proposal
1. Remove `/stock-prices/update/selected` in Stage 17 after the impact review is complete.
2. Make `source='pykrx'` a default-safe filter in operational SQL and reports.
3. Review alternate collection options if `trading_value` must be filled.
4. Consider exposing last collection mode in the Stock Prices screen for operators.
