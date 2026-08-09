CREATE TABLE IF NOT EXISTS market_theme_observation_validation_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_date TEXT NOT NULL,
    theme_id INTEGER NOT NULL,
    calculation_mode TEXT NOT NULL,
    observation_rule_version TEXT NOT NULL,
    model_version TEXT NOT NULL DEFAULT '',
    metric_version TEXT NOT NULL,
    observation_score REAL,
    observation_rank INTEGER NOT NULL,
    status_code TEXT,
    data_coverage_rate REAL,
    actual_rank INTEGER,
    actual_top20 INTEGER,
    rank_error INTEGER,
    rank_gap INTEGER,
    top20_hit INTEGER,
    refresh_score_delta REAL,
    refresh_rank_improvement INTEGER,
    refresh_effect INTEGER,
    evaluation_status TEXT NOT NULL DEFAULT 'PENDING',
    evaluated_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(target_date, theme_id, calculation_mode, observation_rule_version, model_version),
    FOREIGN KEY(theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS market_theme_observation_validation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_date TEXT NOT NULL,
    calculation_mode TEXT NOT NULL,
    observation_rule_version TEXT NOT NULL,
    model_version TEXT NOT NULL DEFAULT '',
    metric_version TEXT NOT NULL,
    total_theme_count INTEGER NOT NULL,
    evaluable_theme_count INTEGER NOT NULL,
    evaluation_coverage_rate REAL NOT NULL,
    precision_top20 REAL,
    recall_top20 REAL,
    f1_top20 REAL,
    precision_at_5 REAL,
    ndcg_at_5 REAL,
    spearman REAL,
    mean_rank_error REAL,
    top5_actual_top20_count INTEGER NOT NULL DEFAULT 0,
    improved_theme_count INTEGER,
    worsened_theme_count INTEGER,
    unchanged_theme_count INTEGER,
    mean_rank_error_current REAL,
    mean_rank_error_refreshed REAL,
    mean_refresh_effect REAL,
    current_precision_top20 REAL,
    refreshed_precision_top20 REAL,
    current_ndcg_at_5 REAL,
    refreshed_ndcg_at_5 REAL,
    evaluation_status TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(target_date, calculation_mode, observation_rule_version, model_version)
);

CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_samples_date
ON market_theme_observation_validation_samples(target_date);
CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_samples_theme_date
ON market_theme_observation_validation_samples(theme_id, target_date);
CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_samples_date_mode
ON market_theme_observation_validation_samples(target_date, calculation_mode);
CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_metrics_date
ON market_theme_observation_validation_metrics(target_date);
CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_metrics_mode_date
ON market_theme_observation_validation_metrics(calculation_mode, target_date);
