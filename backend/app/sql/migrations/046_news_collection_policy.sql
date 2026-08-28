-- News collection policy cursor. Runtime counters remain transient.
CREATE TABLE IF NOT EXISTS news_collection_cursors (
    stock_id INTEGER PRIMARY KEY,
    last_completed_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

-- Existing SQLite databases may still have a UNIQUE constraint on news_items.url.
-- The runtime schema migration rebuilds that table so the same article can be linked
-- independently to every stock whose official name appears in the title.
