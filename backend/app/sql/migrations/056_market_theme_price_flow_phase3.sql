-- Version the compact Stage result without persisting transient feature matrices.
ALTER TABLE market_theme_observation_runs ADD COLUMN stage_version TEXT;
