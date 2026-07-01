"""Prove the persistence chain end-to-end against live Supabase."""

from __future__ import annotations

from app import db, persistence
from app.signal_service import compute_signal


def main() -> None:
    print("db.enabled:", db.enabled(), "| db.ping:", db.ping())

    sig = compute_signal("BTCUSDT", "4h", market="crypto", with_news=False)
    print(f"signal: {sig['symbol']} {sig['label']} composite={sig['composite']}")

    sid = persistence.log_decision(sig)
    print("logged signal_id:", sid)

    ok = persistence.record_outcome(sid, "target", pnl=0.021, mfe=0.03, mae=-0.008, bars_held=12)
    print("outcome recorded:", ok)

    recent = persistence.recent_signals(3)
    print("recent rows:", len(recent))
    if recent:
        r = recent[0]
        print(f"  latest -> id={r['id']} {r['symbol']} {r['label']} result={r['result']} pnl={r['pnl']}")

    print("stats:", persistence.accuracy_stats())


if __name__ == "__main__":
    main()
