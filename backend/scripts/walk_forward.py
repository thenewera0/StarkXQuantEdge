"""Walk-forward parameter sweep — does ANY fixed-weight config beat costs out-of-sample?

Why walk-forward: a plain sweep over (atr_mult, reward_risk, interval) and reporting the best
result is curve-fitting — you'd be reading noise. Instead we roll a window forward:

    [ in-sample (choose best params) ][ out-of-sample (score them) ] -> step -> repeat

Only the OUT-OF-SAMPLE trades count toward the reported result. If the chosen params keep
working on data they were not selected on, that's a (weak) signal of real edge. If OOS is
negative while in-sample looked great, the baseline has no edge and we should NOT pile an LLM
and a learning loop on top of it.

Usage (from backend/):
    python -m scripts.walk_forward --symbols BTCUSDT ETHUSDT --intervals 1h 4h
"""

from __future__ import annotations

import argparse
import itertools
import sys

from app.backtest import backtest
from app.data import fetch_klines_history
from app.indicators import compute_indicators

ATR_MULTS = [1.0, 1.5, 2.0, 2.5]
REWARD_RISKS = [1.0, 1.5, 2.0, 3.0]


def _oos_buy_hold(df, oos_start: int, oos_end: int) -> float:
    c0 = df["close"].iloc[oos_start]
    c1 = df["close"].iloc[min(oos_end, len(df)) - 1]
    return c1 / c0 - 1.0


def run_symbol(symbol: str, interval: str, total: int, is_bars: int, oos_bars: int, min_trades: int) -> dict:
    df = fetch_klines_history(symbol, interval, total)
    ind = compute_indicators(df)
    n = len(ind)
    warmup = 200

    combos = list(itertools.product(ATR_MULTS, REWARD_RISKS))

    # Aggregate OOS results across folds.
    oos_trades: list = []
    oos_buyhold = 0.0
    fold_count = 0
    chosen_params: list[tuple[float, float]] = []

    fold_start = warmup
    while fold_start + is_bars + oos_bars <= n:
        is_lo, is_hi = fold_start, fold_start + is_bars
        oos_lo, oos_hi = is_hi, is_hi + oos_bars

        # Choose best params on in-sample by total return, requiring enough trades.
        best = None
        for atr_mult, rr in combos:
            r = backtest(ind, symbol, interval, atr_mult=atr_mult, reward_risk=rr,
                         start_idx=is_lo, end_idx=is_hi, warmup=warmup)
            if r.n_trades < min_trades:
                continue
            score = r.total_return
            if best is None or score > best[0]:
                best = (score, atr_mult, rr)

        if best is None:
            fold_start += oos_bars
            continue

        _, atr_mult, rr = best
        chosen_params.append((atr_mult, rr))
        oos = backtest(ind, symbol, interval, atr_mult=atr_mult, reward_risk=rr,
                       start_idx=oos_lo, end_idx=oos_hi, warmup=warmup)
        oos_trades.extend(oos.trades)
        oos_buyhold += _oos_buy_hold(ind, oos_lo, oos_hi)
        fold_count += 1
        fold_start += oos_bars

    wins = sum(1 for t in oos_trades if t.net_return > 0)
    nt = len(oos_trades)
    total_ret = sum(t.net_return for t in oos_trades)
    gains = sum(t.net_return for t in oos_trades if t.net_return > 0)
    losses = -sum(t.net_return for t in oos_trades if t.net_return < 0)
    pf = gains / losses if losses > 0 else float("inf")

    return {
        "symbol": symbol,
        "interval": interval,
        "bars": n,
        "folds": fold_count,
        "oos_trades": nt,
        "oos_hit_rate": round(wins / nt, 4) if nt else 0.0,
        "oos_total_return": round(total_ret, 4),
        "oos_avg_return": round(total_ret / nt, 5) if nt else 0.0,
        "oos_profit_factor": round(pf, 3) if pf != float("inf") else None,
        "oos_buy_hold": round(oos_buyhold, 4),
        "param_drift": _drift(chosen_params),
    }


def _drift(params: list[tuple[float, float]]) -> str:
    """Did the in-sample-optimal params keep changing? Unstable params => fragile edge."""
    if not params:
        return "n/a"
    uniq = len(set(params))
    return f"{uniq} distinct / {len(params)} folds"


def main() -> int:
    ap = argparse.ArgumentParser(description="Walk-forward sweep (OOS-only reporting)")
    ap.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    ap.add_argument("--intervals", nargs="+", default=["1h", "4h"])
    ap.add_argument("--total", type=int, default=2500, help="bars of history per symbol/interval")
    ap.add_argument("--is-bars", type=int, default=700, help="in-sample window size")
    ap.add_argument("--oos-bars", type=int, default=250, help="out-of-sample window size")
    ap.add_argument("--min-trades", type=int, default=8, help="min in-sample trades to pick a config")
    args = ap.parse_args()

    rows: list[dict] = []
    for symbol in args.symbols:
        for interval in args.intervals:
            print(f"Walk-forward {symbol} {interval} ...", flush=True)
            try:
                rows.append(run_symbol(symbol.upper(), interval, args.total, args.is_bars,
                                       args.oos_bars, args.min_trades))
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"  failed: {exc}")

    if not rows:
        print("No results.")
        return 1

    hdr = ["symbol", "interval", "folds", "oos_trades", "oos_hit_rate",
           "oos_total_return", "oos_profit_factor", "oos_buy_hold", "param_drift"]
    print("\n=== Out-of-sample results (the only ones that matter) ===")
    print("  " + "  ".join(f"{h:>16}" for h in hdr))
    for r in rows:
        print("  " + "  ".join(f"{str(r.get(h, '')):>16}" for h in hdr))

    beat = [r for r in rows if r["oos_total_return"] > 0]
    beat_bh = [r for r in rows if r["oos_total_return"] > r["oos_buy_hold"]]
    print(f"\nConfigs with positive OOS return: {len(beat)}/{len(rows)}")
    print(f"Configs beating buy & hold OOS:   {len(beat_bh)}/{len(rows)}")
    print(
        "\nVerdict guide: if most rows are negative or below buy & hold, the fixed-weight "
        "baseline has NO reliable edge yet — fix the strategy before adding LLM/learning layers."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
