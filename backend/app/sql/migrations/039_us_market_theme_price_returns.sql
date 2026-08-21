PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS us_stock_daily_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    us_stock_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    volume INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'KIWOOM',
    collected_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(us_stock_id, trade_date),
    FOREIGN KEY(us_stock_id) REFERENCES us_stocks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_us_stock_daily_prices_date ON us_stock_daily_prices(trade_date);

CREATE TABLE IF NOT EXISTS us_theme_daily_returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    simple_return REAL NOT NULL,
    theme_strength REAL NOT NULL,
    trimmed_mean_return REAL NOT NULL,
    median_return REAL NOT NULL,
    breadth_ratio REAL NOT NULL,
    valid_stock_count INTEGER NOT NULL,
    up_count INTEGER NOT NULL,
    down_count INTEGER NOT NULL,
    flat_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(theme_id, trade_date),
    FOREIGN KEY(theme_id) REFERENCES us_themes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_us_theme_daily_returns_date ON us_theme_daily_returns(trade_date);
