-- Migration 010: Add r_net and cost_r to outcomes table
-- Phase 0 Institutional Measurement & Truth-First Rehabilitation

ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS r_net NUMERIC;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS cost_r NUMERIC;

CREATE INDEX IF NOT EXISTS idx_outcomes_r_net ON outcomes(r_net);
