-- Migration 012: Canonical Bar Fingerprint & Scan De-duplication (Proposed / Audit Archive)
-- DO NOT APPLY TO PRODUCTION LEDGER WITHOUT FOUR-WAY INSTITUTIONAL SIGN-OFF
-- Purpose: Prevent duplicate signal emission across multiple scans within the same bar interval.

-- 1. Helper function to compute canonical bar open timestamp from any as_of timestamp and interval
create or replace function get_canonical_bar_open(as_of timestamptz, interval_str text)
returns timestamptz as $$
declare
    clean_close timestamptz;
    step interval;
begin
    -- Normalize 999 millisecond Binance timestamps
    if extract(microsecond from as_of) > 500000 then
        clean_close := as_of + ((1000000 - extract(microsecond from as_of)) * interval '1 microsecond');
    else
        clean_close := as_of;
    end if;

    case interval_str
        when '15m' then step := interval '15 minutes';
        when '1h'  then step := interval '1 hour';
        when '4h'  then step := interval '4 hours';
        when '1d'  then step := interval '1 day';
        else step := interval '4 hours';
    end case;

    return clean_close - step;
end;
$$ language plpgsql immutable;

-- 2. Add canonical_bar_open column to signals (generated or populated)
-- alter table signals add column if not exists canonical_bar_open timestamptz;
-- update signals set canonical_bar_open = get_canonical_bar_open(as_of, interval);

-- 3. Unique index enforcing exactly one signal per (symbol, interval, strategy, direction, canonical_bar_open)
-- create unique index if not exists idx_signals_canonical_fingerprint
-- on signals (symbol, interval, strategy, (case when label in ('Buy', 'Strong Buy') then 'long' when label in ('Sell', 'Strong Sell') then 'short' else 'neutral' end), get_canonical_bar_open(as_of, interval));
