-- Compact, durable price-flow signal fields. Raw feature matrices remain transient.
ALTER TABLE market_theme_observation_items ADD COLUMN stage_code TEXT;
ALTER TABLE market_theme_observation_items ADD COLUMN flow_acceleration_score REAL;
ALTER TABLE market_theme_observation_items ADD COLUMN sustainability_score REAL;
ALTER TABLE market_theme_observation_items ADD COLUMN price_flow_gap REAL;
ALTER TABLE market_theme_observation_validation_samples ADD COLUMN stage_code TEXT;
