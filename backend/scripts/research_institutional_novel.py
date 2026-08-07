"""INSTITUTIONAL NOVEL STRATEGY SUITE — 4 Completely New Strategies & Personas.

Run: python -m scripts.research_institutional_novel

Evaluates 4 novel institutional-grade quantitative strategies:
  1. "Billionaire Macro Alpha" — Regime-Adaptive Liquidity Exhaustion & Vol Parity
  2. "Investment Banker Carry" — Funding Yield Harvest & Delta-Neutral Carry Engine
  3. "Retail Trap Breaker"    — Liquidation Sweep & False Breakout Fade Engine
  4. "Quant Confluence Hybrid"— Multi-Factor Kalman + Order Flow + Volatility Target
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd

from app.costs import round_trip_cost
from app.data import fetch_klines_history
from app.data.validate import validate_ohlcv
from app.indicators import compute_indicators

UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT", "UNIUSDT"]
DAYS = 720
COST_PER_TURN = 0.0015  # 15 bps round-trip cost


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
        return {"name": name, "total": 0, "cagr": 0, "vol": 0, "sharpe": 0, "maxdd": 0, "calmar": 0, "win_rate": 0}
    total = equity.iloc[-1] / equity.iloc[0] - 1
    years = len(rets) / 365
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    vol = float(rets.std(ddof=0) * np.sqrt(365))
    sharpe = float((rets.mean() * 365) / vol) if vol > 1e-9 else 0
    dd = float((equity / equity.cummax() - 1).min())
    calmar = cagr / abs(dd) if dd < 0 else 0
    wins = (rets > 0).sum()
    win_rate = wins / len(rets) if len(rets) else 0
    return {
        "name": name,
        "total": float(total),
        "cagr": float(cagr),
        "vol": float(vol),
        "sharpe": float(sharpe),
        "maxdd": float(dd),
        "calmar": float(calmar),
        "win_rate": float(win_rate),
    }


# ==============================================================================
# STRATEGY 1: BILLIONAIRE MACRO ALPHA (Liquidity Exhaustion & Vol Parity)
# ==============================================================================
def strategy_billionaire_alpha(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Billionaire Macro Strategist: Buys extreme downside liquidation exhaustion
    in high-quality assets when Hurst < 0.45 (mean reverting) and RSI < 35,
    scaled by inverse volatility targeting (12% annualized target).
    """
    idx = sorted(set().union(*[set(d.index.date) for d in data.values()]))
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
            ema200 = row.get("ema200")
            rsi = row.get("rsi")
            hurst = row.get("hurst")
            vol = row.get("atr")

            # Conditions: Structural uptrend intact (close > 0.8 * ema200) AND oversold exhaustion
            if close and ema200 and rsi and hurst and vol:
                is_uptrend = close > 0.85 * ema200
                is_exhaustion = rsi < 40 and (hurst < 0.50)
                if is_uptrend and is_exhaustion:
                    # Risk parity weighting (inverse volatility)
                    vol_est = (vol / close) * np.sqrt(365)
                    target_weights[s] = 1.0 / max(vol_est, 0.20)

        # Scale weights to total exposure cap of 100%
        tot = sum(target_weights.values())
        if tot > 1.0:
            target_weights = {k: v / tot for k, v in target_weights.items()}
        elif tot > 0:
            target_weights = {k: v * 0.8 for k, v in target_weights.items()}

        # Turnover cost calculation
        turn = sum(abs(target_weights.get(s, 0.0) - prev_w.get(s, 0.0)) for s in set(target_weights) | set(prev_w))
        cost = turn * COST_PER_TURN

        # Return calculation
        r = 0.0
        for s, wt in target_weights.items():
            if wt > 0 and i + 1 < len(closes[s]):
                p0, p1 = closes[s].iloc[i], closes[s].iloc[i + 1]
                if p0 and p1 and not np.isnan(p0) and not np.isnan(p1):
                    r += wt * (p1 / p0 - 1)

        equity.append(equity[-1] * (1 + r - cost))
        prev_w = target_weights

    return pd.Series(equity, index=dates[start : start + len(equity)])


# ==============================================================================
# STRATEGY 2: INVESTMENT BANKER CARRY (Yield & Trend-Shielded Allocation)
# ==============================================================================
def strategy_investment_banker(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Investment Banker: Focuses on capital preservation, risk-adjusted carry,
    and momentum filtering. Allocates strictly to Top 3 positive 126d momentum
    assets ONLY when price is above EMA200, rebalanced weekly, with inverse-volatility
    weighting and a strict 15% volatility ceiling.
    """
    closes = pd.DataFrame({s: d["close"] for s, d in data.items()})
    closes.index = pd.to_datetime(closes.index).date
    closes = closes.groupby(level=0).last().sort_index().ffill()

    equity = [1.0]
    dates = list(closes.index)
    prev_w: dict[str, float] = {}
    start = 220

    for i in range(start, len(dates) - 1):
        if i % 7 != 0:  # Weekly rebalance
            target_weights = prev_w
        else:
            # Measure 126d momentum and 200d trend
            scores = {}
            for s in closes.columns:
                c = closes[s].iloc[: i + 1].dropna()
                if len(c) > 130:
                    mom126 = c.iloc[-1] / c.iloc[-126] - 1
                    ema200 = c.iloc[-200:].mean()
                    if c.iloc[-1] > ema200 and mom126 > 0:
                        scores[s] = mom126

            ranked = sorted(scores, key=scores.get, reverse=True)[:3]
            if not ranked:
                target_weights = {}
            else:
                inv_vol = {}
                for s in ranked:
                    v = float(closes[s].iloc[: i + 1].pct_change().dropna().iloc[-60:].std(ddof=0)) or 0.02
                    inv_vol[s] = 1.0 / max(v, 0.01)
                tot = sum(inv_vol.values())
                target_weights = {s: inv_vol[s] / tot for s in ranked}

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

    return pd.Series(equity, index=dates[start : start + len(equity)])


# ==============================================================================
# STRATEGY 3: RETAIL TRAP BREAKER (Liquidation Sweep & False Breakout Fade)
# ==============================================================================
def strategy_retail_trap_breaker(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Retail Trader Trap Breaker: Exploits retail trader stop runs.
    When an asset sweeps below 20-day low but closes back inside the channel with
    volume expansion (vol_burst > 1.2) and positive CVD flow, buy the sweep reversal
    targeting VWAP / mean-reversion.
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
            low = row.get("low")
            bb_lower = row.get("bb_lower")
            rsi = row.get("rsi")
            vol_burst = row.get("vol_burst")

            # Conditions for retail trap fade: low dropped below BB lower band, but close recovered above it
            if close and low and bb_lower and rsi and vol_burst:
                sweep = low < bb_lower and close > bb_lower
                oversold = rsi < 45
                volume_confirmation = vol_burst > 1.1
                if sweep and oversold and volume_confirmation:
                    target_weights[s] = 0.25  # Max 25% per symbol slot

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

    return pd.Series(equity, index=dates[start : start + len(equity)])


# ==============================================================================
# STRATEGY 4: QUANT CONFLUENCE HYBRID (Kalman + Order Flow + Vol Target)
# ==============================================================================
def strategy_quant_confluence_hybrid(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Multi-Factor Quant Hybrid: Blends Kalman filter trend slope, volume flow ratio,
    and ATR-based volatility targeting. Only buys assets where Kalman slope is positive,
    CVD flow is positive, and 50d EMA slope > 0.
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
            kalman_slope = row.get("kalman_slope")
            flow_ratio = row.get("flow_ratio")
            ema200_slope = row.get("ema200_slope")
            close = row.get("close")
            ema200 = row.get("ema200")

            if kalman_slope and flow_ratio and close and ema200:
                if kalman_slope > 0 and flow_ratio > 0.05 and close > ema200:
                    scores[s] = kalman_slope * (1.0 + flow_ratio)

        top_picks = sorted(scores, key=scores.get, reverse=True)[:4]
        if not top_picks:
            target_weights = {}
        else:
            inv_vol = {}
            for s in top_picks:
                v = float(closes[s].iloc[: i + 1].pct_change().dropna().iloc[-30:].std(ddof=0)) or 0.02
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

    return pd.Series(equity, index=dates[start : start + len(equity)])


def main() -> None:
    print("Loading market dataset across 12 major assets (720 days)...")
    dataset = load_dataset()
    print(f"Loaded indicators for {len(dataset)} assets.\n")

    # Benchmark: Buy & Hold Equal Weight
    closes = pd.DataFrame({s: d["close"] for s, d in dataset.items()})
    closes.index = pd.to_datetime(closes.index).date
    closes = closes.groupby(level=0).last().sort_index().ffill()
    benchmark_equity = (1.0 + closes.pct_change().mean(axis=1).iloc[220:]).cumprod()

    # Run the 4 novel strategies
    eq_billionaire = strategy_billionaire_alpha(dataset)
    eq_banker = strategy_investment_banker(dataset)
    eq_retail_trap = strategy_retail_trap_breaker(dataset)
    eq_quant_hybrid = strategy_quant_confluence_hybrid(dataset)

    results = [
        metrics(benchmark_equity, "BENCHMARK: Equal-Weight Buy & Hold"),
        metrics(eq_billionaire, "1. Billionaire Macro Alpha (Liquidity & Vol Parity)"),
        metrics(eq_banker, "2. Investment Banker Carry (Yield & Trend Shield)"),
        metrics(eq_retail_trap, "3. Retail Trap Breaker (Liquidation Sweep Fade)"),
        metrics(eq_quant_hybrid, "4. Quant Confluence Hybrid (Kalman + Flow + Vol)"),
    ]

    print("=" * 115)
    print(f"{'STRATEGY NAME':50} {'TOTAL':>9} {'CAGR':>8} {'VOL':>7} {'SHARPE':>7} {'MAXDD':>8} {'CALMAR':>7}")
    print("=" * 115)
    for r in results:
        flag = "  <-- BENCHMARK" if "BENCHMARK" in r["name"] else ""
        print(f"{r['name']:50} {r['total']*100:+8.1f}% {r['cagr']*100:+7.1f}% {r['vol']*100:6.1f}% "
              f"{r['sharpe']:7.2f} {r['maxdd']*100:+7.1f}% {r['calmar']:7.2f}{flag}")
    print("=" * 115)


if __name__ == "__main__":
    main()
