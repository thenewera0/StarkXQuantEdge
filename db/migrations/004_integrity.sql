-- Blueprint v2 §11 — idempotency / ingest integrity.
-- One signal per (symbol, interval, closed-bar). Prevents a re-scan or a double /decision call
-- from logging the same bar twice (which would double-count P&L). Verified 0 existing duplicates
-- before adding this, so the unique index builds cleanly.

create unique index if not exists signals_symbol_interval_asof
    on signals (symbol, interval, as_of);
