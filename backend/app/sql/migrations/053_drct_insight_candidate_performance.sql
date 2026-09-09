-- Phase 4-A: minimal Gate snapshot and compact D+N outcome columns.
-- Existing rows remain NULL where the original decision snapshot was not retained.
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN focus_rank INTEGER;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN theme_gate TEXT;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN flow_gate TEXT;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN pattern_status TEXT;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN us_lead_status TEXT;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN insight_rule_version TEXT;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN d0_return REAL;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN d1_return REAL;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN d3_return REAL;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN d5_return REAL;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN mfe_5d REAL;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN mae_5d REAL;
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN outcome_status TEXT NOT NULL DEFAULT 'PENDING';
ALTER TABLE drct_insight_candidate_evaluations ADD COLUMN outcome_evaluated_at TEXT;

CREATE INDEX IF NOT EXISTS idx_drct_insight_candidate_outcome
ON drct_insight_candidate_evaluations(outcome_status, analysis_date DESC);
