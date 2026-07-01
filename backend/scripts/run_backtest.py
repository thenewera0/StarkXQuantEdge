"""Run the Phase 1a backtest from the command line.

Usage (from backend/):
    python -m scripts.run_backtest --symbol BTCUSDT --interval 1h --limit 1000
    python -m scripts.run_backtest --symbol ETHUSDT --interval 4h
"""

from __future__ import annotations

import argparse
import sys

from app.backtest import backtest
from app.data import fetch_klines
from app.indicators import compute_indicators


def main() -> int:
    ap = argparse.ArgumentParser(description="Universal Signal Cockpit — backtest runner")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--fee", type=float, default=0.0004)
    ap.add_argument("--slippage", type=float, default=0.0002)
    ap.add_argument("--atr-mult", type=float, default=1.5)
    ap.add_argument("--reward-risk", type=float, default=2.0)
    ap.add_argument("--show-trades", type=int, default=8, help="print the last N trades")
    args = ap.parse_args()

    print(f"Fetching {args.symbol} {args.interval} (limit {args.limit}) ...")
    df = fetch_klines(args.symbol, args.interval, args.limit)
    print(f"  {len(df)} bars  [{df.index[0]}  ->  {df.index[-1]}]")

    ind = compute_indicators(df)
    res = backtest(
        ind,
        args.symbol.upper(),
        args.interval,
        fee_rate=args.fee,
        slippage=args.slippage,
        atr_mult=args.atr_mult,
        reward_risk=args.reward_risk,
    )

    s = res.summary()
    print("\n=== Backtest summary ===")
    for k, v in s.items():
        print(f"  {k:>14}: {v}")

    if args.show_trades and res.trades:
        print(f"\n=== Last {min(args.show_trades, res.n_trades)} trades ===")
        print(f"  {'dir':<5} {'entry_time':<26} {'reason':<8} {'bars':>4} {'net%':>8} {'conf':>5}")
        for t in res.trades[-args.show_trades:]:
            print(
                f"  {t.direction:<5} {str(t.entry_time):<26} {t.exit_reason:<8} "
                f"{t.bars_held:>4} {t.net_return * 100:>7.2f}% {t.confidence:>5.0f}"
            )

    print(
        "\nReminder: this is a no-lookahead, cost-aware replay of a FIXED-weight scorer. "
        "Edge here is necessary but not sufficient — it is decision-support, not advice."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
