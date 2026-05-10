ALTER TABLE news_items ADD COLUMN ai_summary TEXT;
ALTER TABLE news_items ADD COLUMN ai_sentiment TEXT;
ALTER TABLE news_items ADD COLUMN ai_importance_score INTEGER DEFAULT 0;
ALTER TABLE news_items ADD COLUMN ai_tags TEXT;
ALTER TABLE news_items ADD COLUMN ai_processed_at TEXT;
ALTER TABLE news_items ADD COLUMN ai_summary_error TEXT;

ALTER TABLE disclosures ADD COLUMN ai_summary TEXT;
ALTER TABLE disclosures ADD COLUMN ai_importance_score INTEGER DEFAULT 0;
ALTER TABLE disclosures ADD COLUMN ai_tags TEXT;
ALTER TABLE disclosures ADD COLUMN ai_risk_level TEXT;
ALTER TABLE disclosures ADD COLUMN ai_event_type TEXT;
ALTER TABLE disclosures ADD COLUMN ai_processed_at TEXT;
ALTER TABLE disclosures ADD COLUMN ai_summary_error TEXT;
