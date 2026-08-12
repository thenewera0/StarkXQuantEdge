"""Flash: the decisive test. Is there ANY edge before cost, and what would it take to keep it?

Every previous search asked "can a better signal beat the cost?" and the answer was no across
88,964 candidates and 11,024 indicator combinations. This asks the prior question, which should
have been asked first:

    Is the GROSS edge (before any cost) positive at all?

That single number decides everything:
  * If gross <= 0, no execution improvement can help, and no signal search will ever work. The
    horizon simply does not contain a directional edge.
  * If gross > 0 but smaller than the round trip, the problem is EXECUTION, not prediction — and
    the fix is maker orders, not more indicators.

The cost model charges taker economics: 0.05% fee + book-crossing slip + ATR-scaled slippage,
per side. On an alt at 1% ATR that is 0.14% per side, 0.28% round trip — almost exactly the
measured baseline loss of 0.26%. That coincidence is the thing to test.

Also measured here, because they are the remaining honest levers:
  1 GROSS vs NET by symbol tier — where is any real edge hiding?
  2 BREAK-EVEN COST — what would execution have to cost for the signal to survive?
  3 MAKER economics — resting limit orders pay ~0.02% and cross no spread, but they only fill
    when price comes to you, which is adverse selection. Modelled honestly, not assumed away.
  4 HOLDING PERIOD — cost is paid once, so edge must grow with hold. Where does it cross?

    python -m scripts.research_flash_final
"""

from __future__ import annotations

import concurrent.futures as cf
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from app.costs import round_trip_cost, _crypto_tier
from app.data import fetch_klines_history
from app.indicators import compute_indicators
from app import universe

BARS = 3000
ATR_STOP = 1.5
RR = 2.0


def simulate(sym: str, interval: str, hold: int) -> pd.DataFrame:
    """Every bar, both directions. Records GROSS (no cost) and the cost separately."""
    try:
        ind = compute_indicators(fetch_klines_history(sym, interval, BARS))
    except Exception:
        return pd.DataFrame()
    if len(ind) < 400:
        return pd.DataFrame()
    h, l, c, a = (ind[k].to_numpy(float) for k in ("high", "low", "close", "atr"))
    n = len(ind)
    rows = []
    for i in range(250, n - hold - 1, 3):
        if not np.isfinite(a[i]) or a[i] <= 0:
            continue
        e = c[i]
        atr_pct = a[i] / e
        cost = round_trip_cost("crypto", sym, atr_pct)
        for d in (1, -1):
            st, tg = e - d * ATR_STOP * a[i], e + d * ATR_STOP * a[i] * RR
            xp = None
            for j in range(i + 1, min(i + 1 + hold, n)):
                if d > 0:
                    if l[j] <= st: xp = st; break
                    if h[j] >= tg: xp = tg; break
                else:
                    if h[j] >= st: xp = st; break
                    if l[j] <= tg: xp = tg; break
            if xp is None:
                xp = c[min(i + hold, n - 1)]
            rows.append({"symbol": sym, "interval": interval, "hold": hold, "dir": d,
                         "gross": d * (xp - e) / e, "cost": cost,
                         "tier": _crypto_tier(sym), "atr_pct": atr_pct})
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame, label: str) -> dict:
    if df.empty:
        return {}
    g = df["gross"].to_numpy()
    cst = df["cost"].to_numpy()
    net = g - cst
    # t-stat on the GROSS mean: is there any directional edge at all, ignoring execution?
    t = g.mean() / (g.std() / np.sqrt(len(g))) if g.std() > 0 else 0.0
    return {"label": label, "n": len(g), "gross": g.mean(), "cost": cst.mean(),
            "net": net.mean(), "t_gross": t, "hit": (net > 0).mean()}


def line(s: dict) -> str:
    if not s:
        return "  (no data)"
    verdict = "EDGE" if s["t_gross"] > 2 else ("hint" if s["t_gross"] > 1 else "none")
    return (f"  {s['label']:<26} n={s['n']:>7,}  gross={s['gross']*100:>+8.4f}%  "
            f"cost={s['cost']*100:>6.4f}%  net={s['net']*100:>+8.4f}%  "
            f"t(gross)={s['t_gross']:>6.2f} [{verdict}]")


def main() -> None:
    syms = [c["symbol"] for c in universe.catalog(
        ["crypto"], crypto_limit=20, min_volume=universe.MIN_VOLUME_FLASH)]
    print(f"Simulating every bar on {len(syms)} deep pairs...\n")

    print("=" * 122)
    print("1. IS THERE ANY EDGE BEFORE COST? (gross = the signal; cost = the tax)")
    print("=" * 122)
    frames = []
    jobs = [(s, iv, 24) for s in syms for iv in ("15m", "1h", "4h")]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for d in ex.map(lambda a: simulate(*a), jobs):
            if not d.empty:
                frames.append(d)
    df = pd.concat(frames, ignore_index=True)

    for iv in ("15m", "1h", "4h"):
        sub = df[df["interval"] == iv]
        print(line(summarise(sub, f"{iv} both directions")))
        print(line(summarise(sub[sub["dir"] == 1], f"{iv} long only")))

    print("\n" + "=" * 122)
    print("2. GROSS EDGE BY LIQUIDITY TIER — cost differs 2x between majors and alts")
    print("=" * 122)
    for iv in ("1h", "4h"):
        for tier in ("major", "large", "alt"):
            sub = df[(df["interval"] == iv) & (df["tier"] == tier) & (df["dir"] == 1)]
            if len(sub) > 500:
                print(line(summarise(sub, f"{iv} long {tier}")))

    print("\n" + "=" * 122)
    print("3. BREAK-EVEN COST — what would execution have to cost for this to survive?")
    print("=" * 122)
    for iv in ("15m", "1h", "4h"):
        sub = df[(df["interval"] == iv) & (df["dir"] == 1)]
        if sub.empty:
            continue
        g, c_now = sub["gross"].mean(), sub["cost"].mean()
        print(f"  {iv:<4} long: gross {g*100:+.4f}%  needs cost < {max(g,0)*100:.4f}%  "
              f"currently pays {c_now*100:.4f}%  -> "
              + ("ACHIEVABLE with maker fills" if 0 < g else "IMPOSSIBLE — gross is negative"))

    print("\n" + "=" * 122)
    print("4. MAKER EXECUTION — does paying 0.02% instead of crossing the book rescue it?")
    print("=" * 122)
    # Maker: 0.02%/side fee, no book-crossing slip, no ATR slippage (the order rests).
    # Adverse selection is charged as a haircut on gross: a resting bid fills preferentially when
    # price is falling, so the fills you GET are worse than the average bar. 25% is a
    # deliberately harsh assumption; real studies put it lower for liquid pairs.
    MAKER_RT = 0.0004
    for iv in ("15m", "1h", "4h"):
        sub = df[(df["interval"] == iv) & (df["dir"] == 1)]
        if sub.empty:
            continue
        g = sub["gross"].mean()
        for adverse in (0.0, 0.25, 0.50):
            net = g * (1 - adverse) - MAKER_RT
            print(f"  {iv:<4} long, maker rt {MAKER_RT*100:.2f}%, adverse selection "
                  f"{adverse*100:>3.0f}%  ->  net {net*100:>+8.4f}%"
                  + ("   <-- PROFITABLE" if net > 0 else ""))

    print("\n" + "=" * 122)
    print("5. HOLDING PERIOD — cost is paid ONCE, so does edge grow faster than it?")
    print("=" * 122)
    for hold in (6, 12, 24, 48, 96):
        jobs = [(s, "1h", hold) for s in syms[:12]]
        fr = []
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            for d in ex.map(lambda a: simulate(*a), jobs):
                if not d.empty:
                    fr.append(d)
        if not fr:
            continue
        sub = pd.concat(fr, ignore_index=True)
        sub = sub[sub["dir"] == 1]
        print(line(summarise(sub, f"1h long, hold {hold} bars")))


if __name__ == "__main__":
    main()
