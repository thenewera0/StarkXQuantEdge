"""7.3 Production Migration & Logging Hardening:
1. Takes a verified backup of signals, outcomes, factor_logs.
2. Applies migration 012 to production:
   - Adds get_canonical_bar_open function.
   - Adds bar_open_time, direction, scan_phase, is_duplicate columns to signals.
   - Populates columns accurately from existing data.
   - Flags exactly 15 historical duplicate rows with is_duplicate = true.
   - Creates partial UNIQUE index on (symbol, interval, strategy, direction, bar_open_time) WHERE is_duplicate = false.
3. Verifies counts and integrity.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parents[2]
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app import db


def run_production_migration():
    print("=" * 80)
    print("PHASE 7.3: APPLYING MIGRATION 012 TO PRODUCTION LEDGER")
    print("=" * 80)

    with db.get_conn() as conn, conn.cursor() as cur:
        # Step 1: Verified Backups
        print("\nStep 1: Creating verified production backups...")
        cur.execute("drop table if exists signals_backup_phase7 cascade;")
        cur.execute("create table signals_backup_phase7 as select * from signals;")
        cur.execute("select count(*) from signals_backup_phase7;")
        sig_bk_count = cur.fetchone()[0]

        cur.execute("drop table if exists outcomes_backup_phase7 cascade;")
        cur.execute("create table outcomes_backup_phase7 as select * from outcomes;")
        cur.execute("select count(*) from outcomes_backup_phase7;")
        out_bk_count = cur.fetchone()[0]

        cur.execute("drop table if exists factor_logs_backup_phase7 cascade;")
        cur.execute("create table factor_logs_backup_phase7 as select * from factor_logs;")
        cur.execute("select count(*) from factor_logs_backup_phase7;")
        fac_bk_count = cur.fetchone()[0]

        print(f"[VERIFIED BACKUP]: signals={sig_bk_count}, outcomes={out_bk_count}, factor_logs={fac_bk_count}")
        assert sig_bk_count == 1146, f"Expected 1146 signals, got {sig_bk_count}"
        assert out_bk_count == 1146, f"Expected 1146 outcomes, got {out_bk_count}"

        # Step 2: Canonical Bar Open Function
        print("\nStep 2: Creating get_canonical_bar_open function...")
        cur.execute("""
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
        """)

        # Step 3: Add Columns
        print("\nStep 3: Adding production columns (bar_open_time, direction, scan_phase, is_duplicate)...")
        cur.execute("""
            alter table signals add column if not exists bar_open_time timestamptz;
            alter table signals add column if not exists direction text;
            alter table signals add column if not exists scan_phase text;
            alter table signals add column if not exists is_duplicate boolean not null default false;
        """)

        # Step 4: Populate bar_open_time and direction
        print("\nStep 4: Populating bar_open_time and direction...")
        cur.execute("""
            update signals
            set bar_open_time = get_canonical_bar_open(as_of, interval),
                direction = case
                    when label in ('Buy', 'Strong Buy') then 'long'
                    when label in ('Sell', 'Strong Sell') then 'short'
                    else 'neutral'
                end;
        """)

        # Step 5: Populate scan_phase (mid_bar vs bar_close)
        print("\nStep 5: Populating scan_phase...")
        cur.execute("""
            update signals
            set scan_phase = case
                when extract(minute from as_of) not in (0, 59)
                     or (created_at is not null and created_at < (bar_open_time + case interval
                         when '15m' then interval '12 minutes'
                         when '1h'  then interval '50 minutes'
                         when '4h'  then interval '3 hours 30 minutes'
                         when '1d'  then interval '23 hours'
                         else interval '3 hours 30 minutes'
                     end))
                then 'mid_bar'
                else 'bar_close'
            end;
        """)

        # Step 6: Identify and Flag Historical Duplicates (without deleting)
        print("\nStep 6: Flagging historical duplicates with is_duplicate = true...")
        cur.execute("""
            update signals set is_duplicate = false;
            
            with earliest_signals as (
                select min(id) as first_id
                from signals
                group by symbol, interval, coalesce(strategy, 'core'), direction, bar_open_time
            )
            update signals
            set is_duplicate = true
            where id not in (select first_id from earliest_signals);
        """)

        cur.execute("select count(*) from signals where is_duplicate = true;")
        dup_count = cur.fetchone()[0]
        cur.execute("select count(*) from signals where is_duplicate = false;")
        uniq_count = cur.fetchone()[0]
        print(f"[CONFIRMED]: is_duplicate=true: {dup_count} rows | is_duplicate=false: {uniq_count} rows")
        assert dup_count == 15, f"Expected exactly 15 duplicates, got {dup_count}"
        assert uniq_count == 1131, f"Expected exactly 1131 unique signals, got {uniq_count}"

        # Step 7: Create Partial Unique Index
        print("\nStep 7: Creating partial UNIQUE index on non-duplicate signals...")
        cur.execute("""
            create unique index if not exists idx_signals_unique_fingerprint
            on signals (symbol, interval, coalesce(strategy, 'core'), direction, bar_open_time)
            where is_duplicate = false;
        """)

        conn.commit()
        print("\n[SUCCESS]: Production migration 012 committed successfully!")


if __name__ == "__main__":
    run_production_migration()
