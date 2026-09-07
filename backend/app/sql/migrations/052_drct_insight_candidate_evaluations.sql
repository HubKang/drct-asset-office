-- Phase 3-C: compact candidate identity for deterministic post-market review.
-- No raw source response, feature vector, intraday snapshot, or generated text is retained.
CREATE TABLE IF NOT EXISTS drct_insight_candidate_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    stock_id INTEGER NOT NULL,
    theme_id INTEGER,
    candidate_level TEXT NOT NULL CHECK(candidate_level IN ('FOCUS','FINAL')),
    observation_rank INTEGER,
    success_similarity REAL,
    failure_similarity REAL,
    pattern_edge REAL,
    user_status TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(analysis_date, stock_id),
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE RESTRICT,
    FOREIGN KEY(theme_id) REFERENCES market_themes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_drct_insight_candidate_date_level
ON drct_insight_candidate_evaluations(analysis_date, candidate_level);
