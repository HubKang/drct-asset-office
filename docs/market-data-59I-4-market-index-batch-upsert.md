# 59-I-4 Market index daily price batch upsert

## Purpose

After 59-I-3, `market-indexes/collect` requests a smaller incremental window for existing index data. The remaining write path still executed one upsert per row inside `MarketIndexService._upsert_daily_rows`.

This step changes only the persistence execution style for `market_index_daily_prices`: row-by-row execute is replaced with SQLAlchemy executemany-style batch execution.

## Previous Structure

The previous implementation looped over rows and called `self.db.execute(...)` once per valid row:

- skip rows without `price_date`
- skip rows without `close_price`
- execute `INSERT ... ON CONFLICT(index_code, price_date) DO UPDATE ...`
- increment saved count from rowcount
- commit after the loop

## New Structure

The updated implementation:

1. Builds `params: list[dict[str, Any]]` for valid rows.
2. Returns `0` immediately when there are no valid rows.
3. Executes the same upsert SQL once with the params list:

```python
self.db.execute(sql, params)
```

SQLAlchemy treats a list of dictionaries as executemany-style execution for the same statement.

4. Commits once after the batch execute.
5. Returns `len(params)` as the saved request count.

## Conflict Key

The conflict key is unchanged:

```sql
ON CONFLICT(index_code, price_date) DO UPDATE SET ...
```

## Columns

The insert/update column set is unchanged:

- `index_code`
- `price_date`
- `open_price`
- `high_price`
- `low_price`
- `close_price`
- `volume`
- `trading_value`
- `change_rate`
- `source_provider`
- `created_at`
- `updated_at`

## Relation To 59-I-3

This change does not alter the 59-I-3 collection window logic. The service still chooses one of:

- `manual_range`
- `full_refresh`
- `initial_backfill`
- `incremental_overlap`

The batch upsert receives whatever rows the existing collection flow returns.

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
- market index collection-window calculation from 59-I-3
- existing DB rows

## Logging

The upsert method logs:

- `index_code`
- input `rows_count`
- valid `saved_count`
- `upsert_mode=batch`