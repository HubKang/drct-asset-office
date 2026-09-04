CREATE TABLE IF NOT EXISTS chart_marker_learning_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_marker_event_id INTEGER NOT NULL UNIQUE,
    decision TEXT NOT NULL CHECK(decision IN ('INCLUDE', 'EXCLUDE')),
    decision_reason TEXT,
    pattern_algorithm_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(chart_marker_event_id) REFERENCES chart_marker_events(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_marker_learning_decision
ON chart_marker_learning_decisions(decision);
