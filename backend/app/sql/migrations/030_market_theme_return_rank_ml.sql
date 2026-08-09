ALTER TABLE market_theme_return_prediction_models ADD COLUMN target_type TEXT NOT NULL DEFAULT 'RAW_RETURN';
ALTER TABLE market_theme_return_prediction_models ADD COLUMN parent_model_version TEXT;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN selection_gate_status TEXT NOT NULL DEFAULT 'NOT_EVALUATED';
ALTER TABLE market_theme_return_prediction_models ADD COLUMN selection_reason TEXT;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN shadow_selected_at TEXT;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN validation_improving_fold_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE market_theme_return_prediction_models ADD COLUMN metric_version TEXT NOT NULL DEFAULT 'THEME_RETURN_METRIC_V1';
ALTER TABLE market_theme_return_prediction_items ADD COLUMN top5_probability REAL;
ALTER TABLE market_theme_return_prediction_method_metrics ADD COLUMN metric_version TEXT NOT NULL DEFAULT 'THEME_RETURN_METRIC_V1';

CREATE INDEX IF NOT EXISTS idx_theme_prediction_models_gate
ON market_theme_return_prediction_models(selection_gate_status, validation_ndcg_at_5 DESC);
