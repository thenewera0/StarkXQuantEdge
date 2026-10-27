-- Migration 013: Add initial_stop, trailing_stop, and forward logging enrichment columns
-- Phase 8.1 & Phase 8.4 Hardening

-- 1. Add columns to signals
ALTER TABLE signals ADD COLUMN IF NOT EXISTS initial_stop NUMERIC;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS trailing_stop NUMERIC;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS first_seen_scan_ts TIMESTAMPTZ;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS passes_at_close BOOLEAN;

-- Backfill initial_stop:
-- For rows where stop was never overwritten, copy stop directly.
-- For overwritten rows, reconstruct initial_stop = entry -/+ stop_mult * atr.
UPDATE signals
SET initial_stop = stop
WHERE initial_stop IS NULL;

-- Backfill first_seen_scan_ts to as_of
UPDATE signals
SET first_seen_scan_ts = as_of
WHERE first_seen_scan_ts IS NULL;

-- Backfill passes_at_close: true if scan_phase = 'bar_close', false if mid_bar
UPDATE signals
SET passes_at_close = (coalesce(scan_phase, 'bar_close') = 'bar_close')
WHERE passes_at_close IS NULL;
