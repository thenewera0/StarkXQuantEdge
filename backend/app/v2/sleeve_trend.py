"""StarkX QuantEdge v2: Sleeve T — Diversified Trend, Vol-Targeted, Long/Flat.

Rules:
1. 7 signals: sign(close_t/close_{t-L}-1) for L in {20, 60, 120, 250}; sign(EMA_fast - EMA_slow) for (16,64), (32,128), (64,256).
2. Composite signal s = mean(7 signals); Exposure e = max(s, 0). (Shorts disabled: V2_ALLOW_SHORT=false).
3. Volatility: EWMA of daily log returns, halflife 30 days, annualized x sqrt(365), floor 20%.
4. Weights: w_i = e_i * (SIGMA_TARGET / sigma_i) / N_active; per-asset cap 0.25.
5. Portfolio vol estimate from 90-day covariance: k = min(1, SIGMA_TARGET / sigma_p); gross exposure cap 1.0.
6. No-trade band: trade only if |w_target - w_current| > max(0.20 * w_target, 0.02).
7. Neighbourhood variants: lookbacks scaled by 0.75x and 1.25x; EMA pairs scaled by 0.75x and 1.25x.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .config import settings_v2

# Default parameters
DEFAULT_LOOKBACKS = (20, 60, 120, 250)
DEFAULT_EMA_PAIRS = ((16, 64), (32, 128), (64, 256))

# Robustness neighbourhood specifications
NEIGHBOURHOOD_VARIANTS = {
    "base": {
        "lookbacks": (20, 60, 120, 250),
        "ema_pairs": ((16, 64), (32, 128), (64, 256))
    },
    "v_lookbacks_0_75x": {
        "lookbacks": (15, 45, 90, 188),
        "ema_pairs": ((16, 64), (32, 128), (64, 256))
    },
    "v_lookbacks_1_25x": {
        "lookbacks": (25, 75, 150, 312),
        "ema_pairs": ((16, 64), (32, 128), (64, 256))
    },
    "v_ema_0_75x": {
        "lookbacks": (20, 60, 120, 250),
        "ema_pairs": ((12, 48), (24, 96), (48, 192))
    },
    "v_ema_1_25x": {
        "lookbacks": (20, 60, 120, 250),
        "ema_pairs": ((20, 80), (40, 160), (80, 320))
    }
}


def compute_asset_signals(
    df: pd.DataFrame,
    lookbacks: Tuple[int, ...] = DEFAULT_LOOKBACKS,
    ema_pairs: Tuple[Tuple[int, int], ...] = DEFAULT_EMA_PAIRS
) -> pd.DataFrame:
    """Computes the 7 constituent trend signals, composite score, and long-only exposure.
    
    Returns DataFrame with columns:
      - mom_L for each L in lookbacks
      - ema_fast_slow for each pair in ema_pairs
      - composite_signal: mean of the 7 signals [-1.0, +1.0]
      - exposure: max(composite_signal, 0.0) [0.0, +1.0]
    """
    res = pd.DataFrame(index=df.index)
    close = df["close"]
    
    signal_cols = []
    
    # 1. Price Momentum Signals: sign(close_t / close_{t-L} - 1)
    for L in lookbacks:
        col = f"mom_{L}"
        mom = (close / close.shift(L) - 1.0)
        # Sign: +1 if > 0, -1 if < 0, 0 if == 0
        res[col] = np.sign(mom).fillna(0.0)
        signal_cols.append(col)
        
    # 2. Moving Average Crossover Signals: sign(EMA_fast - EMA_slow)
    for fast_span, slow_span in ema_pairs:
        col = f"ema_{fast_span}_{slow_span}"
        fast_ema = close.ewm(span=fast_span, adjust=False).mean()
        slow_ema = close.ewm(span=slow_span, adjust=False).mean()
        res[col] = np.sign(fast_ema - slow_ema).fillna(0.0)
        signal_cols.append(col)
        
    # 3. Composite Signal: mean of the 7 signals
    res["composite_signal"] = res[signal_cols].mean(axis=1)
    
    # 4. Exposure: max(composite_signal, 0.0) — long/flat only (shorts disabled)
    res["exposure"] = res["composite_signal"].clip(lower=0.0)
    
    return res


def compute_ewma_volatility(
    df: pd.DataFrame,
    halflife_days: float = 30.0,
    floor: float = 0.20
) -> pd.Series:
    """Computes EWMA of daily log returns with specified halflife, annualized, and floored.
    
    Formula:
      r_t = ln(close_t / close_{t-1})
      sigma_t^2 = EWMA(r_t^2, halflife=30)
      sigma_ann = sqrt(sigma_t^2 * 365)
      result = max(sigma_ann, floor)
    """
    log_ret = np.log(df["close"] / df["close"].shift(1)).fillna(0.0)
    # Variance via ewm on squared returns
    var_series = (log_ret ** 2).ewm(halflife=halflife_days, min_periods=10).mean()
    vol_ann = np.sqrt(var_series * 365.0)
    # Apply floor
    vol_floored = vol_ann.clip(lower=floor).fillna(floor)
    return vol_floored


def compute_portfolio_target_weights(
    asset_data: Dict[str, pd.DataFrame],
    current_weights: Optional[Dict[str, float]] = None,
    sigma_target: float = 0.15,
    covariance_window: int = 90,
    per_asset_cap: float = 0.25,
    lookbacks: Tuple[int, ...] = DEFAULT_LOOKBACKS,
    ema_pairs: Tuple[Tuple[int, int], ...] = DEFAULT_EMA_PAIRS
) -> Dict[str, Any]:
    """Calculates multi-asset volatility-targeted portfolio weights with covariance scaling.
    
    Steps:
    1. For each asset, extract latest exposure e_i and EWMA vol sigma_i.
    2. Compute raw target weight: w_i = e_i * (sigma_target / sigma_i) / N_active.
    3. Apply per-asset cap (0.25).
    4. Compute portfolio vol estimate using trailing 90-day covariance matrix.
    5. Portfolio scale factor k = min(1.0, sigma_target / sigma_p).
    6. Scale weights by k and cap gross exposure <= 1.0.
    7. Apply no-trade band hysteresis against current_weights.
    """
    if current_weights is None:
        current_weights = {sym: 0.0 for sym in asset_data}
        
    assets = sorted(asset_data.keys())
    N_active = len(assets)
    if N_active == 0:
        return {"target_weights": {}, "trades": {}, "portfolio_vol": 0.0, "scale_factor": 1.0}
        
    exposures = {}
    vols = {}
    returns_dict = {}
    
    for sym in assets:
        df = asset_data[sym]
        sig_df = compute_asset_signals(df, lookbacks=lookbacks, ema_pairs=ema_pairs)
        vol_s = compute_ewma_volatility(df, halflife_days=30.0, floor=0.20)
        
        exposures[sym] = float(sig_df["exposure"].iloc[-1])
        vols[sym] = float(vol_s.iloc[-1])
        
        # Daily returns for covariance
        returns_dict[sym] = df["close"].pct_change().fillna(0.0)
        
    # Unscaled weights
    raw_weights = {}
    for sym in assets:
        e_i = exposures[sym]
        sig_i = vols[sym]
        raw_w = e_i * (sigma_target / sig_i) / N_active
        # Apply per-asset cap
        raw_weights[sym] = min(raw_w, per_asset_cap)
        
    # Portfolio volatility from 90-day covariance
    ret_df = pd.DataFrame(returns_dict).iloc[-covariance_window:]
    if len(ret_df) >= 20 and len(assets) > 1:
        cov_matrix = ret_df.cov().values * 365.0
        w_vec = np.array([raw_weights[s] for s in assets])
        port_var = float(w_vec.T @ cov_matrix @ w_vec)
        sigma_p = math.sqrt(max(port_var, 1e-6))
    else:
        # Fallback to sum of weighted volatilities
        sigma_p = sum(raw_weights[s] * vols[s] for s in assets)
        
    # Scale factor k = min(1.0, sigma_target / sigma_p)
    k = min(1.0, sigma_target / sigma_p) if sigma_p > 1e-4 else 1.0
    
    # Scaled weights
    scaled_weights = {}
    for sym in assets:
        scaled_weights[sym] = raw_weights[sym] * k
        
    # Gross exposure cap <= 1.0
    total_gross = sum(scaled_weights.values())
    if total_gross > 1.0:
        for sym in assets:
            scaled_weights[sym] /= total_gross
            
    # Apply No-Trade Band against current_weights:
    # trade only if |w_target - w_current| > max(0.20 * w_target, 0.02)
    final_targets = {}
    trades = {}
    
    for sym in assets:
        w_t = scaled_weights[sym]
        w_c = current_weights.get(sym, 0.0)
        threshold = max(0.20 * w_t, 0.02)
        delta = abs(w_t - w_c)
        
        if delta > threshold:
            final_targets[sym] = round(w_t, 6)
            trades[sym] = {
                "action": "BUY" if w_t > w_c else "SELL",
                "target_weight": round(w_t, 6),
                "current_weight": round(w_c, 6),
                "delta_weight": round(w_t - w_c, 6)
            }
        else:
            final_targets[sym] = round(w_c, 6)
            trades[sym] = {
                "action": "HOLD",
                "target_weight": round(w_c, 6),
                "current_weight": round(w_c, 6),
                "delta_weight": 0.0
            }
            
    return {
        "unscaled_weights": raw_weights,
        "scaled_weights": scaled_weights,
        "final_targets": final_targets,
        "trades": trades,
        "portfolio_vol_est": sigma_p,
        "scale_factor_k": k,
        "exposures": exposures,
        "vols": vols
    }


# Convenience alias for sleeve rebalancing
rebalance_sleeve_t = compute_portfolio_target_weights


from dataclasses import dataclass

@dataclass
class TrendSleeveResult:
    symbol: str
    annualized_return: float
    annualized_vol: float
    sharpe_ratio: float
    max_drawdown: float
    bh_annualized_return: float
    bh_max_drawdown: float
    switches_per_year: float
    strategy_net_returns: pd.Series
    bh_returns: pd.Series
    equity_curve: pd.Series
    bh_equity_curve: pd.Series


def evaluate_sleeve_trend(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    sigma_target: float = 0.15,
    per_asset_cap: float = 0.25,
    lookbacks: Tuple[int, ...] = DEFAULT_LOOKBACKS,
    ema_pairs: Tuple[Tuple[int, int], ...] = DEFAULT_EMA_PAIRS,
) -> TrendSleeveResult:
    """Simulates daily execution of Sleeve T on an asset DataFrame."""
    if len(df) < 250:
        empty = pd.Series(dtype=float)
        return TrendSleeveResult(
            symbol=symbol,
            annualized_return=0.0,
            annualized_vol=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            bh_annualized_return=0.0,
            bh_max_drawdown=0.0,
            switches_per_year=0.0,
            strategy_net_returns=empty,
            bh_returns=empty,
            equity_curve=empty,
            bh_equity_curve=empty,
        )

    signals_df = compute_asset_signals(df, lookbacks=lookbacks, ema_pairs=ema_pairs)
    vol_series = compute_ewma_volatility(df, halflife_days=30.0, floor=0.20)

    closes = df["close"].values
    n = len(closes)
    bh_rets = np.zeros(n)
    bh_rets[1:] = (closes[1:] / closes[:-1]) - 1.0

    exposures = signals_df["exposure"].values
    vols = vol_series.values

    # Compute unscaled weights & capped weights
    target_weights = np.zeros(n)
    for i in range(n):
        if vols[i] > 1e-4:
            raw_w = exposures[i] * (sigma_target / vols[i])
            target_weights[i] = min(raw_w, per_asset_cap)

    # Shift by 1 bar to prevent lookahead: trade at bar open based on bar close at t-1
    weights = np.zeros(n)
    current_w = 0.0
    switches = 0
    strat_net_rets = np.zeros(n)

    cost_rate = (settings_v2.fee_maker_bps * (1.0 + settings_v2.gst_rate) + settings_v2.slippage_bps_tier1) / 10000.0

    for i in range(1, n):
        t_w = target_weights[i - 1]
        delta = abs(t_w - current_w)
        threshold = max(0.20 * t_w, 0.02)
        trade_cost = 0.0

        if delta > threshold:
            trade_cost = delta * cost_rate
            if (current_w == 0.0 and t_w > 0.0) or (current_w > 0.0 and t_w == 0.0):
                switches += 1
            current_w = t_w

        weights[i] = current_w
        strat_net_rets[i] = (current_w * bh_rets[i]) - trade_cost

    strat_s = pd.Series(strat_net_rets, index=df.index)
    bh_s = pd.Series(bh_rets, index=df.index)

    cum_strat = (1.0 + strat_s).cumprod()
    cum_bh = (1.0 + bh_s).cumprod()

    # Drawdowns
    running_peak_strat = cum_strat.cummax()
    dd_strat = (running_peak_strat - cum_strat) / running_peak_strat
    max_dd_strat = float(dd_strat.max())

    running_peak_bh = cum_bh.cummax()
    dd_bh = (running_peak_bh - cum_bh) / running_peak_bh
    max_dd_bh = float(dd_bh.max())

    # Annualized metrics
    years = max(1.0, len(df) / 365.25)
    ann_ret_strat = float(cum_strat.iloc[-1] ** (1.0 / years) - 1.0)
    ann_vol_strat = float(strat_s.std(ddof=1) * math.sqrt(365.0))
    sharpe = ann_ret_strat / (ann_vol_strat + 1e-6)

    ann_ret_bh = float(cum_bh.iloc[-1] ** (1.0 / years) - 1.0)
    switches_yr = switches / years

    return TrendSleeveResult(
        symbol=symbol,
        annualized_return=ann_ret_strat,
        annualized_vol=ann_vol_strat,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd_strat,
        bh_annualized_return=ann_ret_bh,
        bh_max_drawdown=max_dd_bh,
        switches_per_year=switches_yr,
        strategy_net_returns=strat_s,
        bh_returns=bh_s,
        equity_curve=cum_strat,
        bh_equity_curve=cum_bh,
    )


def evaluate_neighbourhood_variants(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
) -> Dict[str, TrendSleeveResult]:
    """Evaluates all 4 parameter neighbourhood variants plus base for robustness audit."""
    results = {}
    for name, params in NEIGHBOURHOOD_VARIANTS.items():
        res = evaluate_sleeve_trend(
            df=df,
            symbol=symbol,
            lookbacks=params["lookbacks"],
            ema_pairs=params["ema_pairs"],
        )
        results[name] = res
    return results
