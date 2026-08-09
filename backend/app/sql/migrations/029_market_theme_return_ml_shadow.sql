ALTER TABLE market_theme_return_prediction_items ADD COLUMN model_version TEXT;

CREATE TABLE IF NOT EXISTS market_theme_return_prediction_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT, model_version TEXT NOT NULL UNIQUE, model_type TEXT NOT NULL,
    feature_version TEXT NOT NULL, status TEXT NOT NULL, trained_at TEXT NOT NULL, train_start_date TEXT NOT NULL,
    train_end_date TEXT NOT NULL, distinct_train_dates INTEGER NOT NULL, train_row_count INTEGER NOT NULL,
    validation_fold_count INTEGER NOT NULL, validation_mae REAL, validation_rmse REAL,
    validation_mean_signed_gap REAL, validation_direction_accuracy REAL, validation_precision_at_3 REAL,
    validation_precision_at_5 REAL, validation_precision_at_10 REAL, validation_spearman REAL,
    validation_ndcg_at_5 REAL, validation_mean_rank_error REAL, rule_validation_mae REAL,
    rule_validation_precision_at_5 REAL, rule_validation_ndcg_at_5 REAL, baseline_validation_mae REAL,
    baseline_validation_precision_at_5 REAL, baseline_validation_ndcg_at_5 REAL, artifact_path TEXT NOT NULL,
    sklearn_version TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_theme_return_prediction_method_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, prediction_method TEXT NOT NULL,
    model_version TEXT NOT NULL DEFAULT '', theme_count INTEGER NOT NULL, evaluable_theme_count INTEGER NOT NULL,
    return_mae REAL, return_rmse REAL, mean_signed_gap REAL, mean_rank_error REAL, top1_hit REAL,
    precision_at_3 REAL, precision_at_5 REAL, precision_at_10 REAL, direction_accuracy REAL,
    spearman_rank_correlation REAL, ndcg_at_5 REAL, evaluated_at TEXT NOT NULL, created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL, UNIQUE(run_id,prediction_method,model_version),
    FOREIGN KEY (run_id) REFERENCES market_theme_return_prediction_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_theme_prediction_models_status ON market_theme_return_prediction_models(status, trained_at);
CREATE INDEX IF NOT EXISTS idx_theme_prediction_method_metrics_run ON market_theme_return_prediction_method_metrics(run_id, prediction_method);
