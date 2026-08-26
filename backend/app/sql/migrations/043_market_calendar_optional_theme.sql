PRAGMA foreign_keys = OFF;

BEGIN IMMEDIATE;

CREATE TABLE market_calendar_events_optional_theme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    theme_id INTEGER,
    title TEXT NOT NULL,
    summary TEXT,
    news_url TEXT,
    event_type TEXT NOT NULL DEFAULT 'news',
    importance TEXT NOT NULL DEFAULT 'medium',
    memo TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE SET NULL
);

INSERT INTO market_calendar_events_optional_theme
    (id, start_date, end_date, theme_id, title, summary, news_url, event_type, importance, memo, is_active, created_at, updated_at)
SELECT id, start_date, end_date, theme_id, title, summary, news_url, event_type, importance, memo, is_active, created_at, updated_at
FROM market_calendar_events;

DROP TABLE market_calendar_events;
ALTER TABLE market_calendar_events_optional_theme RENAME TO market_calendar_events;

CREATE INDEX idx_market_calendar_events_range ON market_calendar_events(start_date, end_date);
CREATE INDEX idx_market_calendar_events_theme ON market_calendar_events(theme_id, is_active);

COMMIT;

PRAGMA foreign_keys = ON;
PRAGMA foreign_key_check;
