-- Migration 012: Canonical Bar Fingerprint & Forward De-duplication Hardening
-- Applied to Production on 2026-10-27 (Phase 7.3)

-- 1. Create robust get_canonical_bar_open function
create or replace function get_canonical_bar_open(as_of timestamptz, interval_str text)
returns timestamptz as $$
declare
    norm timestamptz;
    h int;
    m int;
    s int;
begin
    if extract(microsecond from as_of) > 900000 then
        norm := as_of + ((1000000 - extract(microsecond from as_of)) * interval '1 microsecond');
    else
        norm := as_of;
    end if;

    h := extract(hour from norm)::int;
    m := extract(minute from norm)::int;
    s := extract(second from norm)::int;

    case interval_str
        when '15m' then
            if m % 15 = 0 and s = 0 then
                return norm - interval '15 minutes';
            else
                return date_trunc('hour', norm) + ((m / 15) * 15) * interval '1 minute';
            end if;
        when '1h' then
            if m = 0 and s = 0 then
                return norm - interval '1 hour';
            else
                return date_trunc('hour', norm);
            end if;
        when '4h' then
            if h % 4 = 0 and m = 0 and s = 0 then
                return date_trunc('day', norm) + ((h - 4) * interval '1 hour');
            else
                return date_trunc('day', norm) + (((h / 4) * 4) * interval '1 hour');
            end if;
        when '1d' then
            if h = 0 and m = 0 and s = 0 then
                return norm - interval '1 day';
            else
                return date_trunc('day', norm);
            end if;
        else
            if h % 4 = 0 and m = 0 and s = 0 then
                return date_trunc('day', norm) + ((h - 4) * interval '1 hour');
            else
                return date_trunc('day', norm) + (((h / 4) * 4) * interval '1 hour');
            end if;
    end case;
end;
$$ language plpgsql immutable;

-- 2. Add columns to signals
alter table signals add column if not exists bar_open_time timestamptz;
alter table signals add column if not exists direction text;
alter table signals add column if not exists scan_phase text;
alter table signals add column if not exists is_duplicate boolean not null default false;

-- 3. Create partial unique index to permanently block forward duplicates
create unique index if not exists idx_signals_unique_fingerprint
on signals (symbol, interval, coalesce(strategy, 'core'), direction, bar_open_time)
where is_duplicate = false;
