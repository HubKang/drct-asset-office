# 59-I-3 Market index daily price incremental collection

## Purpose

`market-indexes/collect` previously used a service-level default window of the recent two years whenever the request did not include `start_date` or `end_date`. That meant every active index repeatedly requested the full two-year range even when the DB already had recent daily prices.

This step reduces only the requested collection window. Existing index rows and index daily price rows are preserved.

## Request options

`MarketIndexCollectRequest` now supports these optional fields while keeping existing callers compatible:

- `index_codes`: optional selected index codes
- `start_date`: optional manual range start
- `end_date`: optional manual range end
- `period_years`: default `2`
- `overlap_days`: default `7`
- `force_full_refresh`: default `false`

The frontend does not need to send the new fields for normal incremental behavior.

## Window selection

For each active market index:

1. If `start_date` or `end_date` is provided, the service uses manual range mode.
   - `start_date` missing: defaults to `end_date - period_years * 365`, preserving prior end-date-only behavior.
   - `end_date` missing: defaults to today.
   - mode: `manual_range`
2. If `force_full_refresh=true`, request `today - period_years * 365` through today.
   - mode: `full_refresh`
3. If no existing daily price is found in `market_index_daily_prices`, request `today - period_years * 365` through today.
   - mode: `initial_backfill`
4. If existing daily prices are found, request `latest_price_date - overlap_days` through today.
   - mode: `incremental_overlap`

`overlap_days` is calendar-day based. Weekends and holidays naturally fall out when the provider returns no rows for those dates.

## Latest Date Lookup

Latest index price lookup uses:

```sql
SELECT MAX(price_date)
FROM market_index_daily_prices
WHERE index_code = :code
```

The lookup is per index code, so each index receives its own collection window.

## Response and Logs

Collect results can now include:

- `collection_mode`
- `latest_price_date_before`
- `from_date`
- `to_date`
- `overlap_days`
- `force_full_refresh`
- `collected_count`
- `saved_count`

The backend log also records these values with `[MARKET INDEX PRICE DEBUG]`.

## Persistence

`market_index_daily_prices` saving still uses the existing row-by-row execute upsert in `MarketIndexService._upsert_daily_rows`. The conflict key remains `(index_code, price_date)`. Batch upsert is intentionally left for a later step.

## Scope Exclusions

This change does not modify:

- frontend code
- `TradeTrainingPage.tsx`
- Kiwoom REST provider internals
- FRED provider
- ECOS provider
- `market_indicators` or `market_indicator_values`
- `stock-prices/collect/selected` from 59-I-1
- `stock-tracking/items/collect-prices` from 59-I-2
- existing DB rows