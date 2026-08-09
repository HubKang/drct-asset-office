CREATE TABLE IF NOT EXISTS market_theme_observation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_date TEXT NOT NULL UNIQUE,
    data_cutoff_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    method TEXT NOT NULL,
    model_version TEXT,
    feature_version TEXT NOT NULL,
    display_mode TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    evaluated_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_theme_observation_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    theme_id INTEGER NOT NULL,
    observation_rank INTEGER,
    relative_strength_probability REAL,
    relative_strength_score REAL,
    top20_probability REAL,
    status_code TEXT NOT NULL,
    confidence_level TEXT NOT NULL,
    data_coverage_rate REAL NOT NULL DEFAULT 0,
    base_change_rate REAL,
    price_score REAL,
    flow_score REAL,
    breadth_score REAL,
    liquidity_score REAL,
    technical_score REAL,
    market_environment_score REAL,
    penalty_score REAL NOT NULL DEFAULT 0,
    actual_change_rate REAL,
    actual_rank INTEGER,
    actual_top20 INTEGER,
    rank_gap INTEGER,
    probability_error REAL,
    evaluation_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(run_id, theme_id),
    FOREIGN KEY (run_id) REFERENCES market_theme_observation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS market_theme_observation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL UNIQUE,
    theme_count INTEGER NOT NULL,
    evaluable_theme_count INTEGER NOT NULL,
    precision_top20 REAL,
    recall_top20 REAL,
    f1_top20 REAL,
    precision_at_5 REAL,
    ndcg_at_5 REAL,
    spearman_rank_correlation REAL,
    mean_rank_error REAL,
    brier_score REAL,
    log_loss REAL,
    calibration_error REAL,
    evaluation_status TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES market_theme_observation_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_theme_observation_runs_cutoff ON market_theme_observation_runs(data_cutoff_date, status);
CREATE INDEX IF NOT EXISTS idx_theme_observation_items_rank ON market_theme_observation_items(run_id, observation_rank);

ALTER TABLE market_theme_return_prediction_models ADD COLUMN validation_precision_top20 REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN validation_recall_top20 REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN validation_f1_top20 REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN validation_brier REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN validation_log_loss REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN validation_calibration_error REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN raw_validation_brier REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN raw_validation_log_loss REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN raw_validation_calibration_error REAL;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN calibration_status TEXT NOT NULL DEFAULT 'NOT_EVALUATED';
ALTER TABLE market_theme_return_prediction_models ADD COLUMN probability_display_mode TEXT NOT NULL DEFAULT 'SCORE';
