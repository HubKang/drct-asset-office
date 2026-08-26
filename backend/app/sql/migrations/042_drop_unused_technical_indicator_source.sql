PRAGMA foreign_keys = ON;

BEGIN IMMEDIATE;

ALTER TABLE stock_daily_technical_indicators
DROP COLUMN source;

COMMIT;
