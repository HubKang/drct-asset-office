CREATE TABLE IF NOT EXISTS market_theme_realtime_returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    theme_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    change_rate REAL NOT NULL,
    trading_value INTEGER,
    collected_at TEXT NOT NULL,
    UNIQUE(trade_date, theme_id, stock_id),
    FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_market_theme_realtime_theme_date
    ON market_theme_realtime_returns(theme_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_market_theme_realtime_stock_date
    ON market_theme_realtime_returns(stock_id, trade_date);
