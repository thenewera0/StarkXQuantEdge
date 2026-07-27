-- Flash Bot: a separate high-frequency strategy family with its own P&L track record.
-- 'core' = the patient confluence engine (1h/4h swing), 'flash' = the fast 5m/15m scalper.
-- Keeping them tagged means neither contaminates the other's statistics, gates, or learning.

alter table signals add column if not exists strategy text not null default 'core';
create index if not exists signals_strategy on signals (strategy);
