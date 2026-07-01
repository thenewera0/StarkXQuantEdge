"""Prove the resolver against REAL candles: log a backdated signal, resolve it, then clean up."""

from __future__ import annotations

from app import db, persistence, resolver
from app.data import fetch_klines
from app.indicators import compute_indicators


def main() -> None:
    if not db.enabled():
        print("DB not enabled; aborting.")
        return

    ind = compute_indicators(fetch_klines("BTCUSDT", "1h", 1000))
    idx = len(ind) - 300                      # 300 bars of "future" exist after this point
    bar = ind.iloc[idx]
    entry, atr = float(bar["close"]), float(bar["atr"])
    stop, target = entry - 1.5 * atr, entry + 3.0 * atr  # a long, 2:1 reward:risk

    sig = {
        "symbol": "BTCUSDT", "market": "crypto", "interval": "1h",
        "as_of": str(ind.index[idx]), "label": "Buy", "composite": 30.0, "confidence": 60.0,
        "regime": None, "price": entry, "atr": atr,
        "categories": {k: None for k in
                       ("trend", "momentum", "volatility", "structure", "flow", "sentiment", "macro", "consensus")},
        "levels": {"direction": "long", "entry": round(entry, 2), "stop": round(stop, 2),
                   "target": round(target, 2), "reward_risk": 2.0},
        "explanation": {"rationale": "BACKDATED RESOLVER TEST"},
        "final": {"agreement": "agree", "conviction": 60, "final_confidence": 60.0},
        "debate": {"source": "fallback"},
    }
    sid = persistence.log_decision(sig)
    print(f"backdated signal id={sid}  entry={entry:.2f} stop={stop:.2f} target={target:.2f} as_of={sig['as_of']}")

    summary = resolver.resolve_open_signals()
    print("resolver summary:", summary)

    # Read back the outcome.
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("select result, pnl, mfe, mae, bars_held from outcomes where signal_id=%s", (sid,))
        row = cur.fetchone()
        print("outcome:", dict(zip(["result", "pnl", "mfe", "mae", "bars_held"], row)) if row else "none")
        # Clean up the contrived test rows so live stats stay honest.
        cur.execute("delete from signals where id=%s", (sid,))
        conn.commit()
        print(f"cleaned up test signal id={sid}")


if __name__ == "__main__":
    main()
