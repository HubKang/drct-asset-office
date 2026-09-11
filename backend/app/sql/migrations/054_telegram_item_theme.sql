-- Telegram briefing representative KRX theme. Existing rows remain unassigned.
ALTER TABLE telegram_items
ADD COLUMN theme_id INTEGER REFERENCES market_themes(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_telegram_items_theme_id ON telegram_items(theme_id);
