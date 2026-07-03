# 59-I-1 Kiwoom REST stock daily price incremental collection

## Purpose

`stock-prices/collect/selected` previously requested the full `period_years` window for `source="kiwoom_rest"` and `source="mock"` on every run. With the default `period_years=2`, existing stocks repeatedly requested the recent two-year range even when only the latest days needed refresh.

This step changes the collection window only. The existing DB upsert behavior is preserved.

## Request options

`SelectedStockPriceCollectRequest` now supports these optional fields while keeping existing callers compatible:

- `period_years`: default `2`
- `source`: default `kiwoom_rest`
- `overlap_days`: default `7`
- `force_full_refresh`: default `false`
- `start_date`: optional manual range start, `YYYY-MM-DD`
- `end_date`: optional manual range end, `YYYY-MM-DD`

## Window selection

For each selected stock:

1. If both `start_date` and `end_date` are provided, the service uses that exact manual range.
2. If `force_full_refresh=true`, the service requests `today - period_years * 365` through `today`.
3. If no existing daily price is found for the selected `source`, the service runs the initial backfill window: `today - period_years * 365` through `today`.
4. For `kiwoom_rest` and `mock`, if existing daily prices are found, the service requests `latest_trade_date - overlap_days` through `today`.
5. Existing `pykrx` behavior is preserved: first backfill uses the full period, stale data starts from the latest trade date, and already-current data refreshes the latest seven calendar days.

`overlap_days` is calendar-day based. Weekends and holidays naturally fall out when the provider returns no rows for those dates.

## Persistence

`stock_daily_prices` still uses the existing batch upsert path in `StockPriceRepository.upsert_daily_rows`. The conflict key remains `(stock_id, trade_date)`. No historical price rows are deleted.

## Logging

Collection logs include:

- `stock_id`
- `stock_name`
- `stock_code`
- normalized code
- collection mode
- requested start/end dates
- latest trade date before collection
- `overlap_days`
- `force_full_refresh`
- fetched and saved counts

## Scope exclusions

This change does not modify:

- frontend code
- `TradeTrainingPage.tsx`
- Kiwoom REST provider internals
- stock tracking price collection
- market index collection
- DB schema or existing stored data