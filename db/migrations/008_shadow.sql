-- Decouple LEARNING from ACTING. The scanner now records every candidate it evaluates — including
-- the ones the live gates silenced — as SHADOW signals (paper-only). The resolver labels them like
-- any trade, so the learning layer (calibration, meta-model, drift, and the regime/direction/symbol
-- performance gates) feeds on the full candidate stream and keeps improving even when the engine is
-- correctly standing down on LIVE trades. Shadow rows are excluded from the user-facing P&L.

alter table signals add column if not exists shadow boolean not null default false;
create index if not exists signals_shadow on signals (shadow);
