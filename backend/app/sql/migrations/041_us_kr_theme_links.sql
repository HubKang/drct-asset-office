CREATE TABLE IF NOT EXISTS us_kr_theme_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    us_theme_id INTEGER NOT NULL UNIQUE,
    kr_theme_id INTEGER NOT NULL UNIQUE,
    memo TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(us_theme_id) REFERENCES us_themes(id) ON DELETE RESTRICT,
    FOREIGN KEY(kr_theme_id) REFERENCES market_themes(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_us_kr_theme_links_active ON us_kr_theme_links(active);
