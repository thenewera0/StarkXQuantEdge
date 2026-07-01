"""Apply db/migrations/*.sql in order against DATABASE_URL.

Usage (from backend/, after putting the real password in .env's DATABASE_URL):
    python -m scripts.migrate

Migrations use `if not exists`, so re-running is safe.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app import db

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"


def main() -> int:
    if not db.enabled():
        print("DATABASE_URL is not configured (or still has the [YOUR-PASSWORD] placeholder).")
        print("Edit backend/.env -> DATABASE_URL with your Supabase DB password, then re-run.")
        return 1

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"No .sql migrations found in {MIGRATIONS_DIR}")
        return 1

    print(f"Connecting to database and applying {len(files)} migration(s)...")
    try:
        with db.get_conn() as conn:
            for f in files:
                sql = f.read_text(encoding="utf-8")
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
                print(f"  applied {f.name}")
    except Exception as exc:  # noqa: BLE001 - surface the real reason to the operator
        print(f"Migration failed: {exc}")
        print("Check the password, and that your network allows outbound 5432 to Supabase.")
        return 1

    print("Done. Schema is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
