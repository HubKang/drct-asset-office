BEGIN IMMEDIATE;

ALTER TABLE market_calendar_events
ADD COLUMN period_type TEXT NOT NULL DEFAULT 'D' CHECK(period_type IN ('D', 'M'));

UPDATE market_calendar_events
SET period_type = 'D'
WHERE period_type IS NULL OR period_type NOT IN ('D', 'M');

COMMIT;
