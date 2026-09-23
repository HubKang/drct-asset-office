PRAGMA foreign_keys = OFF;

CREATE TABLE us_kr_theme_links_pair_unique (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    us_theme_id INTEGER NOT NULL,
    kr_theme_id INTEGER NOT NULL,
    memo TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(us_theme_id, kr_theme_id),
    FOREIGN KEY(us_theme_id) REFERENCES us_themes(id) ON DELETE RESTRICT,
    FOREIGN KEY(kr_theme_id) REFERENCES market_themes(id) ON DELETE RESTRICT
);

INSERT INTO us_kr_theme_links_pair_unique
    (id, us_theme_id, kr_theme_id, memo, active, created_at, updated_at)
SELECT id, us_theme_id, kr_theme_id, memo, active, created_at, updated_at
FROM us_kr_theme_links;

DROP TABLE us_kr_theme_links;
ALTER TABLE us_kr_theme_links_pair_unique RENAME TO us_kr_theme_links;
CREATE INDEX idx_us_kr_theme_links_active ON us_kr_theme_links(active);

PRAGMA foreign_keys = ON;
