CREATE TABLE IF NOT EXISTS drct_stock_signal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    marker_id INTEGER NOT NULL,
    signal_date TEXT NOT NULL,
    last_seen_date TEXT NOT NULL,
    ended_date TEXT,
    d0_close REAL NOT NULL,
    similarity_score REAL NOT NULL,
    similarity_percentile REAL,
    similarity_level TEXT NOT NULL,
    candidate_policy_version INTEGER NOT NULL,
    pattern_signature_version INTEGER NOT NULL,
    feature_schema_version INTEGER NOT NULL,
    improvement_candidate INTEGER NOT NULL DEFAULT 0,
    improvement_policy_version TEXT,
    evaluation_status TEXT NOT NULL DEFAULT 'PENDING',
    d5_date TEXT,
    d5_return_pct REAL,
    d10_date TEXT,
    d10_return_pct REAL,
    d20_date TEXT,
    d20_return_pct REAL,
    max_rise_20_pct REAL,
    max_fall_20_pct REAL,
    evaluated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(evaluation_status IN ('PENDING','D5_READY','D10_READY','COMPLETE')),
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE RESTRICT,
    FOREIGN KEY(marker_id) REFERENCES chart_markers(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_drct_stock_signal_events_date
ON drct_stock_signal_events(signal_date);

CREATE INDEX IF NOT EXISTS idx_drct_stock_signal_events_pair
ON drct_stock_signal_events(stock_id, marker_id, signal_date);

CREATE INDEX IF NOT EXISTS idx_drct_stock_signal_events_status
ON drct_stock_signal_events(evaluation_status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_drct_stock_signal_events_active_pair
ON drct_stock_signal_events(stock_id, marker_id)
WHERE ended_date IS NULL;
