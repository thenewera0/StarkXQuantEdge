"""Verify the Confluence Engine end-to-end for a few symbols."""

from __future__ import annotations

import json

from app.signal_service import compute_signal


def show(symbol: str, interval: str, market: str) -> None:
    s = compute_signal(symbol, interval, market=market)
    print(f"\n=== {symbol} {interval} [{market}] ===")
    print(f"regime={s['regime']} label={s['label']} tier={s['tier']} composite={s['composite']} "
          f"conf={s['confidence']} agree={s['agreement']} actionable={s['actionable']} "
          f"silence={s['silence_reason']}")
    print(f"factors: {json.dumps(s['categories'])}")
    print(f"levels: {json.dumps(s['levels'])} targets={s['targets']} RR={s['reward_risk']} size%={s['size_pct']}")
    print(f"psychology: {s['psychology']} (mod {s['psychology_modifier']}, veto {s['crowd_veto']})")
    print(f"derivatives: {json.dumps(s['derivatives'])}")
    print(f"fear_greed: {json.dumps(s['fear_greed'])}  onchain: {json.dumps(s['onchain'])}")
    print(f"invalidation: {s['invalidation']}")


def main() -> None:
    show("BTCUSDT", "4h", "crypto")
    show("ETHUSDT", "1h", "crypto")
    show("EUR/USD", "1h", "forex")


if __name__ == "__main__":
    main()
