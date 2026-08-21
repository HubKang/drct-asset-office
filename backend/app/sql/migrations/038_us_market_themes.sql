CREATE TABLE IF NOT EXISTS us_theme_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 100,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS us_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_group_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    keywords TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 100,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(theme_group_id, name),
    FOREIGN KEY(theme_group_id) REFERENCES us_theme_groups(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS us_theme_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id INTEGER NOT NULL,
    us_stock_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'RELATED' CHECK(role IN ('LEADER','CORE','RELATED','ETF')),
    is_representative INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 100,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(theme_id, us_stock_id),
    FOREIGN KEY(theme_id) REFERENCES us_themes(id) ON DELETE CASCADE,
    FOREIGN KEY(us_stock_id) REFERENCES us_stocks(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_us_themes_group_active ON us_themes(theme_group_id, active);
CREATE INDEX IF NOT EXISTS idx_us_theme_stocks_theme_active ON us_theme_stocks(theme_id, active);
CREATE INDEX IF NOT EXISTS idx_us_theme_stocks_stock_active ON us_theme_stocks(us_stock_id, active);
