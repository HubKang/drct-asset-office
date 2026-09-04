-- Phase 6-A: marker review code standardization.
-- Back up the database before applying. Runtime schema initialization performs
-- the SQLite table rebuild when the legacy CHECK constraint is present.
UPDATE chart_marker_events SET review_result = 'S' WHERE review_result = 'SUCCESS';
UPDATE chart_marker_events SET review_result = 'F' WHERE review_result = 'FAILURE';
