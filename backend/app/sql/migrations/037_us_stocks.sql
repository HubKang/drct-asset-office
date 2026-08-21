CREATE TABLE IF NOT EXISTS us_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    name TEXT,
    name_ko TEXT,
    exchange TEXT NOT NULL,
    stock_type TEXT NOT NULL DEFAULT 'COMMON',
    naver_code TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_synced_at TEXT,
    historical_price_status TEXT NOT NULL DEFAULT 'NOT_COLLECTED',
    historical_price_completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(symbol, exchange)
);

CREATE INDEX IF NOT EXISTS idx_us_stocks_active_type ON us_stocks(is_active, stock_type);
CREATE INDEX IF NOT EXISTS idx_us_stocks_exchange ON us_stocks(exchange);
