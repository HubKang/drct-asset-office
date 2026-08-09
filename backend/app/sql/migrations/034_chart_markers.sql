PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS chart_marker_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT, color TEXT NOT NULL DEFAULT '#64748b',
    sort_order INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS chart_markers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, marker_group_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT, symbol TEXT NOT NULL DEFAULT '◆',
    sort_order INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(marker_group_id, name),
    FOREIGN KEY(marker_group_id) REFERENCES chart_marker_groups(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS chart_marker_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, stock_id INTEGER NOT NULL, marker_id INTEGER NOT NULL, marker_date TEXT NOT NULL, memo TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, marker_id, marker_date), FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    FOREIGN KEY(marker_id) REFERENCES chart_markers(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_chart_marker_events_stock_date ON chart_marker_events(stock_id, marker_date);
CREATE INDEX IF NOT EXISTS idx_chart_marker_events_marker_stock_date ON chart_marker_events(marker_id, stock_id, marker_date DESC);
