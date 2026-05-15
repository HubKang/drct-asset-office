# Price Candle Operational SQL

## Principles
- All operational queries must use `p.source = 'pykrx'`.
- `source='mock'` is for structural testing only and must be excluded from operational counts and reports.
- `trading_value` is currently expected to be `NULL` in the PyKRX adjusted collection path.

## Stock Price Detail By Stock

```sql
SELECT
  s.id AS stock_id,
  s.stock_code,
  s.stock_name,
  p.trade_date,
  p.open_price,
  p.high_price,
  p.low_price,
  p.close_price,
  p.change_price,
  p.change_rate,
  p.volume,
  p.trading_value,
  p.ma5,
  p.ma20,
  p.ma60,
  p.source
FROM stock_daily_prices p
JOIN stocks s ON s.id = p.stock_id
WHERE p.source = 'pykrx'
  AND p.stock_id = :stock_id
ORDER BY p.trade_date DESC
LIMIT 100;
```

## Collection Range By Stock

```sql
SELECT
  s.id AS stock_id,
  s.stock_code,
  s.stock_name,
  MIN(p.trade_date) AS min_trade_date,
  MAX(p.trade_date) AS max_trade_date,
  COUNT(*) AS price_count,
  p.source
FROM stock_daily_prices p
JOIN stocks s ON s.id = p.stock_id
WHERE p.source = 'pykrx'
  AND p.stock_id = :stock_id
GROUP BY s.id, s.stock_code, s.stock_name, p.source;
```

## Source Row Count Check

```sql
SELECT
  p.source,
  COUNT(*) AS row_count
FROM stock_daily_prices p
WHERE p.source = 'pykrx'
GROUP BY p.source;
```

## trading_value NULL Check

```sql
SELECT
  s.id AS stock_id,
  s.stock_code,
  s.stock_name,
  COUNT(*) AS total_rows,
  SUM(CASE WHEN p.trading_value IS NULL THEN 1 ELSE 0 END) AS null_rows,
  SUM(CASE WHEN p.trading_value IS NOT NULL THEN 1 ELSE 0 END) AS non_null_rows
FROM stock_daily_prices p
JOIN stocks s ON s.id = p.stock_id
WHERE p.source = 'pykrx'
GROUP BY s.id, s.stock_code, s.stock_name
ORDER BY null_rows DESC, s.stock_code ASC;
```

## Recent 20 Candles

```sql
SELECT
  s.id AS stock_id,
  s.stock_code,
  s.stock_name,
  p.trade_date,
  p.close_price,
  p.volume,
  p.change_rate,
  p.source
FROM stock_daily_prices p
JOIN stocks s ON s.id = p.stock_id
WHERE p.source = 'pykrx'
  AND p.stock_id = :stock_id
ORDER BY p.trade_date DESC
LIMIT 20;
```

## Moving Average Snapshot

```sql
SELECT
  s.id AS stock_id,
  s.stock_code,
  s.stock_name,
  p.trade_date,
  p.close_price,
  p.ma5,
  p.ma20,
  p.ma60,
  p.ma120,
  p.ma240,
  p.source
FROM stock_daily_prices p
JOIN stocks s ON s.id = p.stock_id
WHERE p.source = 'pykrx'
  AND p.stock_id = :stock_id
ORDER BY p.trade_date DESC
LIMIT 20;
```

## Latest Daily Summary By Stock

```sql
SELECT
  s.id AS stock_id,
  s.stock_code,
  s.stock_name,
  latest.trade_date,
  latest.close_price,
  latest.ma5,
  latest.ma20,
  latest.ma60,
  latest.ma120,
  latest.ma240,
  latest.volume,
  latest.source
FROM stocks s
JOIN (
  SELECT
    p.stock_id,
    p.trade_date,
    p.close_price,
    p.ma5,
    p.ma20,
    p.ma60,
    p.ma120,
    p.ma240,
    p.volume,
    p.source
  FROM stock_daily_prices p
  WHERE p.source = 'pykrx'
    AND p.trade_date = (
      SELECT MAX(p2.trade_date)
      FROM stock_daily_prices p2
      WHERE p2.source = 'pykrx'
        AND p2.stock_id = p.stock_id
    )
) latest ON latest.stock_id = s.id
WHERE latest.source = 'pykrx'
  AND s.id = :stock_id;
```

## Summary API Validation SQL

```sql
WITH recent_252 AS (
  SELECT
    p.stock_id,
    p.trade_date,
    p.close_price,
    p.high_price,
    p.ma5,
    p.ma20,
    p.ma60,
    p.volume,
    ROW_NUMBER() OVER (
      PARTITION BY p.stock_id
      ORDER BY p.trade_date DESC
    ) AS rn
  FROM stock_daily_prices p
  WHERE p.source = 'pykrx'
    AND p.stock_id = :stock_id
),
summary_window AS (
  SELECT
    p.stock_id,
    COUNT(*) AS price_count,
    MIN(p.trade_date) AS min_trade_date,
    MAX(p.trade_date) AS max_trade_date
  FROM stock_daily_prices p
  WHERE p.source = 'pykrx'
    AND p.stock_id = :stock_id
  GROUP BY p.stock_id
),
high_52w AS (
  SELECT
    r.stock_id,
    r.high_price AS high_52w,
    r.trade_date AS high_52w_date
  FROM recent_252 r
  WHERE r.rn <= 252
    AND r.high_price IS NOT NULL
  ORDER BY r.high_price DESC, r.trade_date DESC
  LIMIT 1
)
SELECT
  s.id AS stock_id,
  s.stock_code,
  s.stock_name,
  'pykrx' AS source,
  w.price_count,
  w.min_trade_date,
  w.max_trade_date,
  latest.trade_date AS latest_trade_date,
  latest.close_price AS latest_close_price,
  latest.ma5 AS latest_ma5,
  latest.ma20 AS latest_ma20,
  latest.ma60 AS latest_ma60,
  CASE
    WHEN base5.close_price IS NULL OR base5.close_price = 0 OR latest.close_price IS NULL THEN NULL
    ELSE ROUND(((latest.close_price - base5.close_price) / base5.close_price) * 100, 4)
  END AS recent_5d_change_rate,
  (
    SELECT ROUND(AVG(CAST(r20.volume AS REAL)), 4)
    FROM recent_252 r20
    WHERE r20.rn <= 20
      AND r20.volume IS NOT NULL
  ) AS avg_volume_20d,
  h.high_52w,
  h.high_52w_date,
  CASE
    WHEN h.high_52w IS NULL OR h.high_52w = 0 OR latest.close_price IS NULL THEN NULL
    ELSE ROUND((latest.close_price / h.high_52w) * 100, 4)
  END AS price_position_vs_52w_high
FROM stocks s
JOIN summary_window w ON w.stock_id = s.id
JOIN recent_252 latest ON latest.stock_id = s.id AND latest.rn = 1
LEFT JOIN recent_252 base5 ON base5.stock_id = s.id AND base5.rn = 6
LEFT JOIN high_52w h ON h.stock_id = s.id
WHERE s.id = :stock_id;
```
