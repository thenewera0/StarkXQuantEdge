-- Richer per-signal detail so the UI can show the full "why" behind each trade.
-- Idempotent.

alter table signals add column if not exists tier text;
alter table signals add column if not exists reward_risk numeric;
alter table signals add column if not exists size_pct numeric;
alter table signals add column if not exists invalidation text;
alter table signals add column if not exists target2 numeric;
alter table signals add column if not exists target3 numeric;
alter table signals add column if not exists psychology text;
