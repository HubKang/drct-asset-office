ALTER TABLE market_theme_observation_runs ADD COLUMN calculation_mode TEXT NOT NULL DEFAULT 'CURRENT_MARKET_DATA';
ALTER TABLE market_theme_observation_runs ADD COLUMN market_refresh_requested INTEGER NOT NULL DEFAULT 0;
ALTER TABLE market_theme_observation_runs ADD COLUMN market_refresh_status TEXT NOT NULL DEFAULT 'NOT_REQUESTED';
ALTER TABLE market_theme_observation_runs ADD COLUMN market_indicator_refreshed_at TEXT;
ALTER TABLE market_theme_observation_runs ADD COLUMN market_indicator_data_asof_at TEXT;
ALTER TABLE market_theme_observation_runs ADD COLUMN market_indicator_updated_count INTEGER;
ALTER TABLE market_theme_observation_runs ADD COLUMN market_indicator_failed_count INTEGER;
ALTER TABLE market_theme_observation_runs ADD COLUMN market_collection_run_id INTEGER;
ALTER TABLE market_theme_observation_runs ADD COLUMN revision_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_theme_observation_runs_mode
ON market_theme_observation_runs(calculation_mode, status);
