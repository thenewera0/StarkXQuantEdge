import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import db

with db.get_conn() as conn, conn.cursor() as cur:
    for tbl in ["signals", "outcomes"]:
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}' ORDER BY ordinal_position")
        print(f"\n=== {tbl} ===")
        for r in cur.fetchall():
            print(f"  {r[0]:25s} {r[1]}")
