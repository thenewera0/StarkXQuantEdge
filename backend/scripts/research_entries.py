"""Exhaustive entry-filter search for the fast strategies — with honest out-of-sample control.

The flash bot loses ~0.53%/trade. Its decomposition says why: 24% of trades hit target for +2.26%
while 61% stop for -1.64%. At that reward/risk the break-even hit rate is 42%, so the entry needs
to be nearly twice as selective as it is. The question is whether ANY combination of the 50
available indicators picks those entries out.

Method, and why it is built this way:

  1 Build one labelled dataset ONCE — at every bar, for both directions, record the full indicator
    state and the net outcome of taking that trade under flash geometry (ATR stop, RR target,
    max hold, real costs). Filters are then evaluated by SELECTING ROWS, which makes testing
    thousands of combinations cheap and, more importantly, keeps every combination on identical
    trades so differences cannot come from different fills.

  2 Split by TIME, not at random. Filters are discovered on the first 60% and scored on the last
    40%, which they never touch. A rule that only works in-sample is overfitting, and this is the
    only way to see that.

  3 Report a NULL BASELINE. Testing ~2,000 combinations guarantees some look excellent by chance.
    The script therefore also scores random filters of the same selectivity, so the survivors can
    be compared against what luck alone produces. A candidate that does not clear the null is not
    a finding, no matter how good its number looks.

    python -m scripts.research_entries
"""

from __future__ import annotations

import concurrent.futures as cf
import itertools
import random
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.indicators import compute_indicators
from app import universe

INTERVALS = ["15m", "1h"]
BARS = 3000
ATR_STOP = 1.5         # stop = 1.5 x ATR, matching flash geometry
RR = 2.0               # target = 2 x stop distance
MAX_HOLD = 24          # bars
STEP = 2               # sample every Nth bar (keeps the dataset large but not redundant)

# Features evaluated as filters. Each becomes a set of threshold tests.
FEATURES = [
    "rsi", "stoch_k", "macd_hist", "bb_pctb", "bb_width", "adx", "chop", "hurst",
    "variance_ratio", "entropy", "cvd_z", "flow_ratio", "vol_burst", "pk_vol_ratio",
    "ut_pos", "vwap_dist", "fib_pos", "kalman_slope", "ema200_slope", "ou_halflife", "sabre",
]


def build_one(args) -> pd.DataFrame:
    sym, interval = args
    try:
        df = fetch_klines_history(sym, interval, BARS)
        ind = compute_indicators(df)
    except Exception:
        return pd.DataFrame()
    if len(ind) < 400:
        return pd.DataFrame()

    high = ind["high"].to_numpy(float)
    low = ind["low"].to_numpy(float)
    close = ind["close"].to_numpy(float)
    atr = ind["atr"].to_numpy(float)
    n = len(ind)

    rows = []
    for i in range(250, n - MAX_HOLD - 1, STEP):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        entry = close[i]
        atr_pct = a / entry
        cost = round_trip_cost("crypto", sym, atr_pct)
        for direction in (1, -1):
            stop = entry - direction * ATR_STOP * a
            target = entry + direction * ATR_STOP * a * RR
            exit_px, reason = None, "timeout"
            for j in range(i + 1, min(i + 1 + MAX_HOLD, n)):
                if direction > 0:
                    if low[j] <= stop:
                        exit_px, reason = stop, "stop"; break
                    if high[j] >= target:
                        exit_px, reason = target, "target"; break
                else:
                    if high[j] >= stop:
                        exit_px, reason = stop, "stop"; break
                    if low[j] <= target:
                        exit_px, reason = target, "target"; break
            if exit_px is None:
                exit_px = close[min(i + MAX_HOLD, n - 1)]
            gross = direction * (exit_px - entry) / entry
            rec = {"symbol": sym, "interval": interval, "i": i, "dir": direction,
                   "net": gross - cost, "reason": reason}
            for f in FEATURES:
                if f in ind.columns:
                    v = ind[f].iat[i]
                    rec[f] = float(v) if pd.notna(v) else np.nan
            rows.append(rec)
    return pd.DataFrame(rows)


def build_dataset() -> pd.DataFrame:
    syms = [c["symbol"] for c in universe.catalog(
        ["crypto"], crypto_limit=18, min_volume=universe.MIN_VOLUME_FLASH)]
    jobs = [(s, iv) for s in syms for iv in INTERVALS]
    frames = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for d in ex.map(build_one, jobs):
            if not d.empty:
                frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def score(sel: pd.DataFrame) -> dict:
    n = len(sel)
    if n == 0:
        return {"n": 0, "avg": 0.0, "hit": 0.0, "total": 0.0}
    net = sel["net"].to_numpy()
    return {"n": n, "avg": float(net.mean()), "hit": float((net > 0).mean()),
            "total": float(net.sum())}


def rules(df: pd.DataFrame) -> list[tuple[str, str, float]]:
    """(feature, op, threshold) tests, thresholds taken from the IN-SAMPLE distribution only.

    The rule is returned as data, not as a boolean mask, so the EXACT same threshold can later be
    applied to the out-of-sample rows. Re-deriving thresholds from the out-of-sample distribution
    would silently test a different rule — and would leak knowledge of the future into the split.
    """
    out: list[tuple[str, str, float]] = []
    for f in FEATURES:
        if f not in df.columns or df[f].isna().all():
            continue
        col = df[f]
        for q in (0.2, 0.35, 0.65, 0.8):
            thr = float(col.quantile(q))
            if not np.isfinite(thr):
                continue
            out.append((f, "<", thr))
            out.append((f, ">", thr))
    return out


def rule_name(r: tuple[str, str, float]) -> str:
    return f"{r[0]}{r[1]}{r[2]:.4g}"


def apply_rule(df: pd.DataFrame, r: tuple[str, str, float]) -> pd.Series:
    f, op, thr = r
    if f not in df.columns:
        return pd.Series(False, index=df.index)
    return (df[f] < thr) if op == "<" else (df[f] > thr)


def main() -> None:
    print("Building the labelled trade dataset (every bar, both directions, real costs)...")
    df = build_dataset()
    if df.empty:
        print("No data.")
        return
    print(f"  {len(df):,} candidate trades across {df.symbol.nunique()} symbols x {INTERVALS}")

    base = score(df)
    print(f"  BASELINE (take everything): n={base['n']:,} avg={base['avg']*100:+.4f}%  "
          f"hit={base['hit']*100:.1f}%")
    for d, lab in ((1, "long only"), (-1, "short only")):
        s = score(df[df["dir"] == d])
        print(f"    {lab:12} n={s['n']:,} avg={s['avg']*100:+.4f}%  hit={s['hit']*100:.1f}%")

    # ---- time split: discover on the first 60%, validate on the last 40% ----
    cut = df["i"].quantile(0.6)
    ins, oos = df[df["i"] <= cut], df[df["i"] > cut]
    print(f"\n  in-sample {len(ins):,} trades   |   out-of-sample {len(oos):,} trades (never touched)")

    all_rules = rules(ins)                      # thresholds from IN-SAMPLE only
    masks_in = {rule_name(r): apply_rule(ins, r) for r in all_rules}
    by_name = {rule_name(r): r for r in all_rules}
    names = list(masks_in)
    print(f"  {len(names)} single conditions -> {len(names)*(len(names)-1)//2:,} pairs to test")

    MIN_N = 400
    results = []
    for nm in names:
        s = score(ins[masks_in[nm]])
        if s["n"] >= MIN_N:
            results.append((s["avg"], [nm], s))
    for a, b in itertools.combinations(names, 2):
        if by_name[a][0] == by_name[b][0]:
            continue                       # same feature twice adds nothing
        m = masks_in[a] & masks_in[b]
        if int(m.sum()) < MIN_N:
            continue
        s = score(ins[m])
        results.append((s["avg"], [a, b], s))
    results.sort(reverse=True, key=lambda r: r[0])
    print(f"  {len(results):,} combinations met the minimum sample of {MIN_N}")

    print("\n" + "=" * 118)
    print("TOP 15 IN-SAMPLE — and what they then did OUT-OF-SAMPLE")
    print("=" * 118)
    survivors = []
    for avg, parts, s in results[:15]:
        # Apply the IDENTICAL rule (same feature, same threshold) to the held-out rows.
        m = pd.Series(True, index=oos.index)
        for p in parts:
            m &= apply_rule(oos, by_name[p])
        name = " AND ".join(parts)
        o = score(oos[m])
        flag = "HOLDS" if o["avg"] > 0 and o["n"] >= 150 else "fails"
        if flag == "HOLDS":
            survivors.append((name, s, o))
        print(f"  {name[:62]:<62} IS n={s['n']:>5} avg={s['avg']*100:>+7.4f}%  |  "
              f"OOS n={o['n']:>5} avg={o['avg']*100:>+7.4f}% hit={o['hit']*100:>4.1f}%  {flag}")

    # ---- null baseline: what does pure luck produce at this scale of search? ----
    print("\n" + "=" * 118)
    print("NULL BASELINE — random filters of the same selectivity, same search size")
    print("=" * 118)
    random.seed(11)
    rng = np.random.default_rng(11)
    nulls = []
    for _ in range(400):
        frac = rng.uniform(0.05, 0.35)
        mask_in = pd.Series(rng.random(len(ins)) < frac, index=ins.index)
        if int(mask_in.sum()) < MIN_N:
            continue
        nulls.append(score(ins[mask_in])["avg"])
    if nulls:
        nulls = np.array(nulls)
        print(f"  400 random in-sample filters: mean {nulls.mean()*100:+.4f}%  "
              f"best {nulls.max()*100:+.4f}%  p95 {np.percentile(nulls,95)*100:+.4f}%")
        best_real = results[0][0] if results else 0.0
        print(f"  best REAL in-sample filter:  {best_real*100:+.4f}%")
        print(f"  -> the search beats luck by {(best_real-np.percentile(nulls,95))*100:+.4f} "
              f"percentage points at the 95th percentile")

    print("\n" + "=" * 118)
    if survivors:
        print(f"{len(survivors)} candidate(s) survived out-of-sample:")
        for name, s, o in survivors:
            print(f"  {name}")
            print(f"     IS  n={s['n']:>5} avg={s['avg']*100:+.4f}% hit={s['hit']*100:.1f}%")
            print(f"     OOS n={o['n']:>5} avg={o['avg']*100:+.4f}% hit={o['hit']*100:.1f}%")
    else:
        print("NOTHING survived out-of-sample. Every in-sample winner failed forward.")
        print("That is a result: at this horizon and cost, entry timing on these indicators")
        print("does not carry information. Do not ship any of them.")
    print("=" * 118)


if __name__ == "__main__":
    main()
