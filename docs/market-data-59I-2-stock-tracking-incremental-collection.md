# 59-I-2 Stock tracking price incremental collection

## Purpose

`stock-tracking/items/collect-prices` previously requested prices from `price_collection_targets.start_date` through today every time. The DB upsert prevented duplicate rows, but existing tracking items still made unnecessarily wide provider requests.

This step reduces only the requested collection window. Existing tracking targets and stored price rows are preserved.

## Request options

`CollectStockTrackingPricesRequest` now supports these optional fields while keeping existing callers compatible:

- `source`: default `kiwoom_rest`
- `overlap_days`: default `7`
- `force_full_refresh`: default `false`

The frontend does not need to send the new fields for normal incremental behavior.

## Window selection

For each selected tracking item:

1. Resolve or create the existing `price_collection_targets` row.
2. Preserve `price_collection_targets.start_date` as the tracking target's original collection baseline.
3. Use today as the collection end date.
4. If `force_full_refresh=true`, request `target.start_date` through today with mode `full_refresh_from_target_start`.
5. If no existing daily price is found for the selected `source`, request `target.start_date` through today with mode `initial_tracking_backfill`.
6. If existing daily prices are found, request `max(target.start_date, latest_trade_date - overlap_days)` through today with mode `tracking_incremental_overlap`.

`overlap_days` is calendar-day based. Weekends and holidays naturally fall out when the provider returns no rows for those dates.

## Source alignment

Latest price lookup uses the same `source` as the collection request. For example, `source="kiwoom_rest"` checks the latest `stock_daily_prices.trade_date` where `source = 'kiwoom_rest'`.

## Response and logs

Successful and partial item responses can now include:

- `target_start_date`
- `latest_trade_date_before`
- `requested_start_date`
- `requested_end_date`
- `collection_mode`
- `overlap_days`
- `force_full_refresh`
- `saved_count`

The backend log also records these values for collection-window verification.

## Persistence

Price saving still uses `StockPriceService._collect_and_upsert`, which delegates to the existing stock daily price upsert path. No price rows are deleted. `price_collection_targets.start_date` is not changed.

## Scope exclusions

This change does not modify:

- frontend code
- `TradeTrainingPage.tsx`
- `stock-prices/collect/selected` behavior from 59-I-1
- Kiwoom REST provider internals
- market index collection
- FRED, ECOS, or market indicator collection
- DB schema or existing stored data