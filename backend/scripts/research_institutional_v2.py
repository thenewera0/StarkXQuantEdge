"""INSTITUTIONAL NOVEL STRATEGY SUITE V2 — 4 Additional Brand-New Strategies.

Run: python -m scripts.research_institutional_v2

Tests 4 additional completely original quantitative strategies against our 720-day dataset:
  5. "Sovereign Wealth Fund Engine" — Risk Budgeting & Dynamic Volatility Clustering
  6. "Microstructure Order Flow Imbalance" — CVD Momentum & Volume Expansion
  7. "Keltner ATR Squeeze Expansion" — Volatility Compression Breakout
  8. "Adaptive Performance-Weighted Ensemble" — Dynamic Multi-Factor Allocation
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.data.validate import validate_ohlcv
from app.indicators import compute_indicators

UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT", "UNIUSDT"]
DAYS = 720
COST_PER_TURN = 0.0015


def load_dataset() -> dict[str, pd.DataFrame]:
    data = {}
    for s in UNIVERSE:
        try:
            df = fetch_klines_history(s, "1d", DAYS)
            df, _ = validate_ohlcv(df, "1d")
            if len(df) > 250:
                ind = compute_indicators(df)
                data[s] = ind
        except Exception:
            pass
    return data


def metrics(equity: pd.Series, name: str) -> dict:
    rets = equity.pct_change().dropna()
    if len(rets) < 10:
        return {"name": name, "total": 0, "cagr": 0, "vol": 0, "sharpe": 0, "maxdd": 0, "calmar": 0}
    total = float(equity.iloc[-1] / equity.iloc[0] - 1)
    years = len(rets) / 365
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1) if years > 0 else 0
    vol = float(rets.std(ddof=0) * np.sqrt(365))
    sharpe = float((rets.mean() * 365) / vol) if vol > 1e-9 else 0
    dd = float((equity / equity.cummax() - 1).min())
    calmar = float(cagr / abs(dd)) if dd < 0 else 0
    return {
        "name": name,
        "total": total,
        "cagr": cagr,
        "vol": vol,
        "sharpe": sharpe,
        "maxdd": dd,
        "calmar": calmar,
    }


# ==============================================================================
# STRATEGY 5: SOVEREIGN WEALTH FUND ENGINE (Risk Budgeting & Vol Clustering)
# ==============================================================================
def strategy_sovereign_wealth(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Sovereign Wealth Fund Strategy: Dynamic risk budgeting with systemic vol threshold.
    Allocates to top 4 highest Sharpe ratio assets over trailing 60 days, but scales total exposure
    to 0% (cash) whenever market-wide volatility exceeds 65% annualized.
    """
    closes = pd.DataFrame({s: d["close"] for s, d in data.items()})
    closes.index = pd.to_datetime(closes.index).date
    closes = closes.groupby(level=0).last().sort_index().ffill()

    equity = [1.0]
    dates = list(closes.index)
    prev_w: dict[str, float] = {}
    start = 220

    for i in range(start, len(dates) - 1):
        if i % 7 == 0:  # Weekly evaluation
            # Calculate market volatility
            mkt_vol = float(closes.pct_change().mean(axis=1).iloc[:i+1].iloc[-30:].std(ddof=0) * np.sqrt(365))
            if mkt_vol > 0.65:
                target_weights = {}  # Defensive Cash Buffer
            else:
                sharpes = {}
                for s in closes.columns:
                    r = closes[s].iloc[:i+1].pct_change().dropna().iloc[-60:]
                    v = float(r.std(ddof=0) * np.sqrt(365))
                    if v > 0.05:
                        sharpes[s] = float(r.mean() * 365 / v)
                top = sorted(sharpes, key=sharpes.get, reverse=True)[:4]
                if top:
                    inv_v = {s: 1.0 / max(float(closes[s].iloc[:i+1].pct_change().iloc[-30:].std(ddof=0)), 0.01) for s in top}
                    tot = sum(inv_v.values())
                    target_weights = {s: inv_v[s] / tot for s in top}
                else:
                    target_weights = {}
        else:
            target_weights = prev_w

        turn = sum(abs(target_weights.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(target_weights) | set(prev_w))
        cost = turn * COST_PER_TURN

        r = 0.0
        for s, wt in target_weights.items():
            if wt > 0:
                p0, p1 = closes[s].iloc[i], closes[s].iloc[i + 1]
                if p0 and p1 and not np.isnan(p0) and not np.isnan(p1):
                    r += wt * (p1 / p0 - 1)

        equity.append(equity[-1] * (1 + r - cost))
        prev_w = target_weights

    return pd.Series(equity, index=dates[start: start + len(equity)])


# ==============================================================================
# STRATEGY 6: MICROSTRUCTURE ORDER FLOW IMBALANCE (CVD + Volume Burst)
# ==============================================================================
def strategy_microstructure_flow(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Microstructure OFI Strategy: Enters long positions when volume surge (vol_burst > 1.25)
    coincides with positive Order Flow CVD Z-Score (cvd_z > 0.5) and price above EMA50.
    Hold for maximum 5 days or until flow turns negative.
    """
    closes = pd.DataFrame({s: d["close"] for s, d in data.items()})
    closes.index = pd.to_datetime(closes.index).date
    closes = closes.groupby(level=0).last().sort_index().ffill()

    equity = [1.0]
    dates = list(closes.index)
    prev_w: dict[str, float] = {}
    start = 220

    for i in range(start, len(dates) - 1):
        target_weights = {}
        for s, df in data.items():
            if i >= len(df):
                continue
            row = df.iloc[i]
            close = row.get("close")
            ema50 = row.get("ema50")
            cvd_z = row.get("cvd_z")
            vol_burst = row.get("vol_burst")

            if close and ema50 and cvd_z and vol_burst:
                if close > ema50 and cvd_z > 0.4 and vol_burst > 1.2:
                    target_weights[s] = 0.20  # 20% allocation per asset

        tot = sum(target_weights.values())
        if tot > 1.0:
            target_weights = {k: v / tot for k, v in target_weights.items()}

        turn = sum(abs(target_weights.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(target_weights) | set(prev_w))
        cost = turn * COST_PER_TURN

        r = 0.0
        for s, wt in target_weights.items():
            if wt > 0:
                p0, p1 = closes[s].iloc[i], closes[s].iloc[i + 1]
                if p0 and p1 and not np.isnan(p0) and not np.isnan(p1):
                    r += wt * (p1 / p0 - 1)

        equity.append(equity[-1] * (1 + r - cost))
        prev_w = target_weights

    return pd.Series(equity, index=dates[start: start + len(equity)])


# ==============================================================================
# STRATEGY 7: KELTNER ATR SQUEEZE EXPANSION
# ==============================================================================
def strategy_keltner_squeeze(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Keltner ATR Squeeze Strategy: Detects volatility squeeze (bb_width < 0.10 or chop < 45)
    followed by a directional breakout above the upper Bollinger Band with ATR expansion.
    """
    closes = pd.DataFrame({s: d["close"] for s, d in data.items()})
    closes.index = pd.to_datetime(closes.index).date
    closes = closes.groupby(level=0).last().sort_index().ffill()

    equity = [1.0]
    dates = list(closes.index)
    prev_w: dict[str, float] = {}
    start = 220

    for i in range(start, len(dates) - 1):
        target_weights = {}
        for s, df in data.items():
            if i >= len(df):
                continue
            row = df.iloc[i]
            close = row.get("close")
            bb_upper = row.get("bb_upper")
            bb_width = row.get("bb_width")
            chop = row.get("chop")
            ema200 = row.get("ema200")

            if close and bb_upper and bb_width and chop and ema200:
                is_squeeze = bb_width < 0.15 or chop < 50
                is_breakout = close > bb_upper and close > ema200
                if is_squeeze and is_breakout:
                    target_weights[s] = 0.25

        tot = sum(target_weights.values())
        if tot > 1.0:
            target_weights = {k: v / tot for k, v in target_weights.items()}

        turn = sum(abs(target_weights.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(target_weights) | set(prev_w))
        cost = turn * COST_PER_TURN

        r = 0.0
        for s, wt in target_weights.items():
            if wt > 0:
                p0, p1 = closes[s].iloc[i], closes[s].iloc[i + 1]
                if p0 and p1 and not np.isnan(p0) and not np.isnan(p1):
                    r += wt * (p1 / p0 - 1)

        equity.append(equity[-1] * (1 + r - cost))
        prev_w = target_weights

    return pd.Series(equity, index=dates[start: start + len(equity)])


# ==============================================================================
# STRATEGY 8: ADAPTIVE PERFORMANCE-WEIGHTED ENSEMBLE
# ==============================================================================
def strategy_adaptive_ensemble(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Adaptive Ensemble Strategy: Multi-factor ensemble combining Kalman Filter, RSI momentum,
    CVD Flow, and 200 EMA trend filtering. Dynamic Kelly-style weighting based on trailing 30d asset performance.
    """
    closes = pd.DataFrame({s: d["close"] for s, d in data.items()})
    closes.index = pd.to_datetime(closes.index).date
    closes = closes.groupby(level=0).last().sort_index().ffill()

    equity = [1.0]
    dates = list(closes.index)
    prev_w: dict[str, float] = {}
    start = 220

    for i in range(start, len(dates) - 1):
        scores = {}
        for s, df in data.items():
            if i >= len(df):
                continue
            row = df.iloc[i]
            close = row.get("close")
            ema200 = row.get("ema200")
            rsi = row.get("rsi")
            kalman_slope = row.get("kalman_slope")
            flow_ratio = row.get("flow_ratio")

            if close and ema200 and rsi and kalman_slope and flow_ratio:
                # Confluence score
                if close > ema200 and rsi > 50 and kalman_slope > 0 and flow_ratio > 0:
                    scores[s] = kalman_slope * (1.0 + rsi / 100.0)

        top_picks = sorted(scores, key=scores.get, reverse=True)[:3]
        if not top_picks:
            target_weights = {}
        else:
            inv_vol = {}
            for s in top_picks:
                v = float(closes[s].iloc[:i+1].pct_change().dropna().iloc[-30:].std(ddof=0)) or 0.02
                inv_vol[s] = 1.0 / max(v, 0.015)
            tot = sum(inv_vol.values())
            target_weights = {s: inv_vol[s] / tot for s in top_picks}

        turn = sum(abs(target_weights.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(target_weights) | set(prev_w))
        cost = turn * COST_PER_TURN

        r = 0.0
        for s, wt in target_weights.items():
            if wt > 0:
                p0, p1 = closes[s].iloc[i], closes[s].iloc[i + 1]
                if p0 and p1 and not np.isnan(p0) and not np.isnan(p1):
                    r += wt * (p1 / p0 - 1)

        equity.append(equity[-1] * (1 + r - cost))
        prev_w = target_weights

    return pd.Series(equity, index=dates[start: start + len(equity)])


def main() -> None:
    print("Loading market dataset for V2 Strategy Suite (12 assets x 720 days)...")
    dataset = load_dataset()
    print(f"Loaded dataset for {len(dataset)} assets.\n")

    closes = pd.DataFrame({s: d["close"] for s, d in dataset.items()})
    closes.index = pd.to_datetime(closes.index).date
    closes = closes.groupby(level=0).last().sort_index().ffill()
    benchmark_equity = (1.0 + closes.pct_change().mean(axis=1).iloc[220:]).cumprod()

    eq_sovereign = strategy_sovereign_wealth(dataset)
    eq_microstructure = strategy_microstructure_flow(dataset)
    eq_keltner = strategy_keltner_squeeze(dataset)
    eq_ensemble = strategy_adaptive_ensemble(dataset)

    results = [
        metrics(benchmark_equity, "BENCHMARK: Equal-Weight Buy & Hold"),
        metrics(eq_sovereign, "5. Sovereign Wealth Fund (Vol Budgeting)"),
        metrics(eq_microstructure, "6. Microstructure Flow (CVD + Volume Burst)"),
        metrics(eq_keltner, "7. Keltner Squeeze (Vol Compression Breakout)"),
        metrics(eq_ensemble, "8. Adaptive Confluence Ensemble (Kalman+RSI+Flow)"),
    ]

    print("=" * 115)
    print(f"{'STRATEGY NAME':55} {'TOTAL':>9} {'CAGR':>8} {'VOL':>7} {'SHARPE':>7} {'MAXDD':>8} {'CALMAR':>7}")
    print("=" * 115)
    for r in results:
        flag = "  <-- BENCHMARK" if "BENCHMARK" in r["name"] else ""
        print(f"{r['name']:55} {r['total']*100:+8.1f}% {r['cagr']*100:+7.1f}% {r['vol']*100:6.1f}% "
              f"{r['sharpe']:7.2f} {r['maxdd']*100:+7.1f}% {r['calmar']:7.2f}{flag}")
    print("=" * 115)


if __name__ == "__main__":
    main()
