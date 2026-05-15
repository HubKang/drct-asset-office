# Stage 18 Marcap Market Metrics Implementation

## Marcap Adoption
- Primary operating source: vendored `marcap` helper with GitHub raw parquet fetch
- Upstream reference: `FinanceData/marcap`
- Reason:
  - trading value
  - market cap
  - listed shares
  - market segmentation
  - daily rank-friendly dataset shape

## Additional Dependencies
- `pyarrow`
- `marcap` upstream is vendored locally because the repository is not pip-installable as a package

## Table
- `stock_daily_market_metrics`

## Key Columns
- `stock_id`
- `trade_date`
- `market`
- `close_price`
- `market_cap`
- `listed_shares`
- `trading_volume`
- `trading_value`
- `market_cap_rank`
- `trading_value_rank`
- `market_trading_value_rank`
- `trading_value_percentile`
- `market_trading_value_percentile`
- `source`

## Column Mapping
- `Code` -> normalized ticker
- `Name` -> source name
- `Close` -> `close_price`
- `Volume` -> `trading_volume`
- `Amount` -> `trading_value`
- `Marcap` -> `market_cap`
- `Stocks` -> `listed_shares`
- `Market` -> `market`
- `Rank` -> `market_cap_rank`

## API
- `POST /market-metrics/collect/daily`
- `GET /market-metrics/{stock_id}/latest`
- `GET /market-metrics/{stock_id}/summary`

### Request
```json
{
  "trade_date": "2026-05-12",
  "source": "marcap"
}
```

### Response Fields
- `trade_date`
- `source`
- `requested_count`
- `matched_count`
- `saved_count`
- `skipped_count`
- `failed_count`
- `message`

### Latest API
- `GET /market-metrics/{stock_id}/latest?source=marcap`
- returns the latest stored market metrics row for the given stock and source

### Summary API
- `GET /market-metrics/{stock_id}/summary?source=marcap`
- combines:
  - latest market metrics date
  - latest `pykrx` price trade date
  - staleness calculation
  - human-readable `data_note`

### Requested Date Behavior
- The collector targets the requested `trade_date` exactly.
- If upstream marcap data does not exist for that date, the API returns `404`.
- As of `2026-05-12`, the upstream `marcap-2026.parquet` snapshot available to this project only contains data through `2026-02-20`.
- Example failure message:
  - `No marcap data for requested date 2026-05-12. Latest available source date is 2026-02-20.`

## Ranking / Percentile Rules
- `trading_value_rank`
  - all collected rows with non-null and non-zero `Amount`
  - descending `Amount`
- `market_trading_value_rank`
  - same rule within each `Market`
- `trading_value_percentile`
  - `(total - rank + 1) / total * 100`
- `market_trading_value_percentile`
  - same rule within each market

## Collection Run Handling
- Current implementation records runs in `collection_runs`
- `collector_name`: `marcap_market_metrics_collector`
- `target`: `trade_date`

## Verification SQL
```sql
SELECT COUNT(*)
FROM stock_daily_market_metrics
WHERE source = 'marcap';
```

```sql
SELECT stock_id, trade_date, trading_value, market_cap, listed_shares, trading_value_rank, trading_value_percentile
FROM stock_daily_market_metrics
WHERE trade_date = '2026-02-20'
  AND source = 'marcap'
ORDER BY trading_value_rank
LIMIT 20;
```

```sql
SELECT source, COUNT(*), MIN(trade_date), MAX(trade_date)
FROM stock_daily_market_metrics
GROUP BY source;
```

## Notes
- This stage stores only stocks that already exist in the local `stocks` table
- Ranking is still computed against the full marcap day snapshot before local filtering
- `GET /market-metrics/{stock_id}/latest` returns the latest stored market metrics row by source.
- `GET /market-metrics/{stock_id}/summary` compares market metrics recency with the latest `pykrx` price date.
- `StockPricesPage` displays the market metrics summary card under the price summary card.
- Default UI source for market metrics is `marcap`.
- Staleness levels:
  - `fresh`: 0 days
  - `acceptable`: 1 to 3 days
  - `stale`: 4 to 20 days
  - `severely_stale`: 21 days or more
- UI guidance:
  - `acceptable`: light notice only
  - `stale`: caution notice
  - `severely_stale`: strong caution notice
- GPT package integration should always include:
  - `latest_market_metrics_date`
  - `latest_price_trade_date`
  - `stale_days`
  - `staleness_level`
  - `data_note`
- Stale market metrics must be interpreted as older supporting data, not as current-day liquidity facts.
- Do not present stale warnings as buy/sell language.

## Remaining Issues
- Upstream yearly parquet download is network-dependent on first use
- Future optimization can prefetch yearly files or add a local sync job

## Next Step
1. Add query API for latest market metrics by stock.
2. Expose a `market_metrics_summary` or `liquidity_summary` block.
3. Combine market metrics with `price_summary` in the GPT advisory package.
