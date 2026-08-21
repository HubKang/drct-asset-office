ALTER TABLE us_stocks ADD COLUMN historical_price_status TEXT NOT NULL DEFAULT 'NOT_COLLECTED';
ALTER TABLE us_stocks ADD COLUMN historical_price_completed_at TEXT;

UPDATE us_stocks
SET historical_price_status = 'COMPLETE',
    historical_price_completed_at = COALESCE(historical_price_completed_at, last_synced_at, updated_at)
WHERE EXISTS (
    SELECT 1 FROM us_stock_daily_prices p WHERE p.us_stock_id = us_stocks.id
);
