-- Add market + AI-debate outcome fields to signals so the self-learning loop can use them.
-- Idempotent: safe to run repeatedly.

alter table signals add column if not exists market text;
alter table signals add column if not exists agreement text;          -- agree | caution | disagree
alter table signals add column if not exists conviction numeric;       -- 0..100 (risk-manager)
alter table signals add column if not exists final_confidence numeric; -- blended 0..100
alter table signals add column if not exists debate_source text;       -- openrouter | fallback

create index if not exists signals_market_time on signals (market, as_of desc);
