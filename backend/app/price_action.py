"""Price Action & Chart Intelligence Engine.

Provides real-time candlestick anatomy reading, dynamic support & resistance
clustering, liquidity sweep detection, market structure trend analysis (BOS / CHoCH),
and entry clearance filters for Flash, Core, and Long-Term strategies.

Guarantees:
  - 100% causal: uses closed bars only to prevent repainting.
  - Zero unhandled exceptions: handles flat candles, zero volume, NaN, and small datasets.
  - Non-destructive & additive: seamlessly integrates with existing pipelines without
    breaking any existing contracts.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np
import pandas as pd


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert value to float, handling None, NaN, and Inf."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return default


def analyze_candle_anatomy(row: pd.Series) -> dict[str, Any]:
    """Examine internal structure of a single candle: body, wicks, and rejection bias."""
    o = _safe_float(row.get("open"))
    h = _safe_float(row.get("high"))
    l = _safe_float(row.get("low"))
    c = _safe_float(row.get("close"))

    candle_range = max(h - l, 1e-9)
    body = abs(c - o)
    upper_wick = max(0.0, h - max(o, c))
    lower_wick = max(0.0, min(o, c) - l)

    body_ratio = body / candle_range
    upper_wick_ratio = upper_wick / candle_range
    lower_wick_ratio = lower_wick / candle_range

    is_bullish = c >= o

    # Rejection diagnosis
    rejection = "none"
    if upper_wick_ratio >= 0.45 and upper_wick_ratio > 1.8 * lower_wick_ratio:
        rejection = "bearish_rejection"  # Sellers absorbed the highs
    elif lower_wick_ratio >= 0.45 and lower_wick_ratio > 1.8 * upper_wick_ratio:
        rejection = "bullish_rejection"  # Buyers absorbed the lows

    return {
        "range": candle_range,
        "body": body,
        "body_ratio": round(body_ratio, 4),
        "upper_wick": upper_wick,
        "upper_wick_ratio": round(upper_wick_ratio, 4),
        "lower_wick": lower_wick,
        "lower_wick_ratio": round(lower_wick_ratio, 4),
        "is_bullish": is_bullish,
        "rejection": rejection,
    }


def detect_candlestick_patterns(df: pd.DataFrame, lookback: int = 5) -> list[dict[str, Any]]:
    """Detect classic and institutional candlestick formations on the most recent closed bars."""
    if len(df) < 2:
        return []

    patterns: list[dict[str, Any]] = []
    end_idx = len(df)
    start_idx = max(1, end_idx - lookback)

    for i in range(start_idx, end_idx):
        curr = df.iloc[i]
        prev = df.iloc[i - 1]
        prev2 = df.iloc[i - 2] if i >= 2 else None

        # Extract bar timestamp if available
        bar_time = None
        if "time" in curr:
            bar_time = int(_safe_float(curr.get("time")))
        elif isinstance(curr.name, (int, float)):
            bar_time = int(curr.name)
        elif hasattr(curr.name, "timestamp"):
            bar_time = int(curr.name.timestamp())

        curr_anat = analyze_candle_anatomy(curr)
        prev_anat = analyze_candle_anatomy(prev)

        c = _safe_float(curr.get("close"))
        o = _safe_float(curr.get("open"))
        h = _safe_float(curr.get("high"))
        l = _safe_float(curr.get("low"))

        pc = _safe_float(prev.get("close"))
        po = _safe_float(prev.get("open"))
        ph = _safe_float(prev.get("high"))
        pl = _safe_float(prev.get("low"))

        bar_offset = i - end_idx  # -1 for last bar, -2 for prior, etc.

        # 1. Pin Bars (Hammer & Shooting Star)
        if curr_anat["body_ratio"] <= 0.35:
            if curr_anat["lower_wick_ratio"] >= 0.55:
                patterns.append({
                    "pattern": "hammer_pin_bar",
                    "name": "Hammer Pin Bar",
                    "time": bar_time,
                    "direction": "bullish",
                    "bar_offset": bar_offset,
                    "strength": round(min(1.0, float(curr_anat["lower_wick_ratio"]) * 1.2), 2),
                    "price": l,
                    "desc": "Long lower wick buyer absorption pin bar",
                })
            elif curr_anat["upper_wick_ratio"] >= 0.55:
                patterns.append({
                    "pattern": "shooting_star_pin_bar",
                    "name": "Shooting Star",
                    "time": bar_time,
                    "direction": "bearish",
                    "bar_offset": bar_offset,
                    "strength": round(min(1.0, float(curr_anat["upper_wick_ratio"]) * 1.2), 2),
                    "price": h,
                    "desc": "Long upper wick seller rejection shooting star",
                })

        # 2. Engulfing Bars
        if not prev_anat["is_bullish"] and curr_anat["is_bullish"]:
            if o <= pc and c >= po and curr_anat["body_ratio"] >= 0.5:
                patterns.append({
                    "pattern": "bullish_engulfing",
                    "name": "Bullish Engulfing",
                    "time": bar_time,
                    "direction": "bullish",
                    "bar_offset": bar_offset,
                    "strength": 0.85,
                    "price": l,
                    "desc": "Bullish expansion body fully engulfing previous red candle",
                })
        elif prev_anat["is_bullish"] and not curr_anat["is_bullish"]:
            if o >= pc and c <= po and curr_anat["body_ratio"] >= 0.5:
                patterns.append({
                    "pattern": "bearish_engulfing",
                    "name": "Bearish Engulfing",
                    "time": bar_time,
                    "direction": "bearish",
                    "bar_offset": bar_offset,
                    "strength": 0.85,
                    "price": h,
                    "desc": "Bearish expansion body fully engulfing previous green candle",
                })

        # 3. Inside Bar (Volatility compression)
        if h <= ph and l >= pl:
            patterns.append({
                "pattern": "inside_bar",
                "name": "Inside Bar",
                "time": bar_time,
                "direction": "neutral",
                "bar_offset": bar_offset,
                "strength": 0.65,
                "price": (h + l) / 2.0,
                "desc": "Volatility contraction inside previous candle range",
            })

        # 4. Morning Star / Evening Star (3-bar reversal cluster)
        if prev2 is not None:
            p2c = _safe_float(prev2.get("close"))
            p2o = _safe_float(prev2.get("open"))
            if p2c < p2o and prev_anat["body_ratio"] < 0.35 and c > o and c > (p2o + p2c) / 2:
                patterns.append({
                    "pattern": "morning_star",
                    "name": "Morning Star",
                    "time": bar_time,
                    "direction": "bullish",
                    "bar_offset": bar_offset,
                    "strength": 0.90,
                    "price": l,
                    "desc": "Three-bar bullish morning star reversal cluster",
                })
            elif p2c > p2o and prev_anat["body_ratio"] < 0.35 and c < o and c < (p2o + p2c) / 2:
                patterns.append({
                    "pattern": "evening_star",
                    "name": "Evening Star",
                    "time": bar_time,
                    "direction": "bearish",
                    "bar_offset": bar_offset,
                    "strength": 0.90,
                    "price": h,
                    "desc": "Three-bar bearish evening star reversal cluster",
                })

    return patterns


def detect_support_resistance_zones(
    df: pd.DataFrame,
    lookback: int = 100,
    fractal_window: int = 3,
    atr_tolerance_mult: float = 0.35,
) -> dict[str, Any]:
    """Identify fractal swing pivots and cluster them into dynamic S/R zones with touch counts."""
    if len(df) < fractal_window * 2 + 1:
        return {
            "support_zones": [],
            "resistance_zones": [],
            "nearest_support": None,
            "nearest_resistance": None,
            "dist_support_pct": None,
            "dist_resistance_pct": None,
            "room_to_run_atr": None,
            "room_to_run_short_atr": None,
            "atr": 0.0,
        }

    sample = df.iloc[-lookback:] if len(df) > lookback else df
    highs = sample["high"].astype(float).values
    lows = sample["low"].astype(float).values
    closes = sample["close"].astype(float).values
    curr_price = float(closes[-1])

    # Dynamic ATR tolerance for clustering
    if "atr" in sample:
        curr_atr = float(_safe_float(sample["atr"].iloc[-1], 0.0))
    else:
        tr = np.maximum(highs[1:] - lows[1:], np.abs(highs[1:] - closes[:-1]))
        curr_atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(curr_price * 0.01)
    if curr_atr <= 0:
        curr_atr = float(curr_price * 0.01)

    tolerance = curr_atr * atr_tolerance_mult
    if tolerance <= 0:
        tolerance = curr_price * 0.002

    # Find swing fractal pivots
    swing_highs: list[float] = []
    swing_lows: list[float] = []
    n = len(sample)
    w = fractal_window

    for i in range(w, n - w):
        val_h = highs[i]
        val_l = lows[i]
        if all(val_h >= highs[i - k] for k in range(1, w + 1)) and all(val_h >= highs[i + k] for k in range(1, w + 1)):
            swing_highs.append(val_h)
        if all(val_l <= lows[i - k] for k in range(1, w + 1)) and all(val_l <= lows[i + k] for k in range(1, w + 1)):
            swing_lows.append(val_l)

    # Helper to cluster raw levels within tolerance
    def _cluster_levels(levels: list[float], is_resistance: bool) -> list[dict[str, Any]]:
        if not levels:
            return []
        sorted_lvls = sorted(levels)
        clusters: list[list[float]] = []
        for lvl in sorted_lvls:
            if not clusters:
                clusters.append([lvl])
            else:
                last_cluster = clusters[-1]
                if abs(lvl - float(np.mean(last_cluster))) <= tolerance:
                    last_cluster.append(lvl)
                else:
                    clusters.append([lvl])

        zones: list[dict[str, Any]] = []
        for cl in clusters:
            mid = float(np.mean(cl))
            touches = len(cl)
            strength = min(5, touches)
            dist_pct = round(abs(mid - curr_price) / max(curr_price, 1e-9) * 100.0, 3)
            zones.append({
                "price": round(mid, 4),
                "high_bound": round(float(np.max(cl)), 4),
                "low_bound": round(float(np.min(cl)), 4),
                "touches": touches,
                "strength": strength,
                "dist_pct": dist_pct,
                "type": "resistance" if is_resistance else "support",
            })
        return zones

    # Cluster resistance levels (above price) and support levels (below price)
    raw_res = [p for p in swing_highs if p > curr_price]
    raw_sup = [p for p in swing_lows if p < curr_price]

    res_zones = _cluster_levels(raw_res, is_resistance=True)
    sup_zones = _cluster_levels(raw_sup, is_resistance=False)

    # Sort resistances: closest to current price first (ascending)
    res_zones.sort(key=lambda z: z["price"])
    # Sort supports: closest to current price first (descending)
    sup_zones.sort(key=lambda z: z["price"], reverse=True)

    nearest_res = res_zones[0]["price"] if res_zones else None
    nearest_sup = sup_zones[0]["price"] if sup_zones else None

    # Significant multi-touch zones (touches >= 2): genuine structural barriers, not 1-candle wicks
    sig_res_zones = [z for z in res_zones if z.get("touches", 1) >= 2]
    sig_sup_zones = [z for z in sup_zones if z.get("touches", 1) >= 2]
    nearest_sig_res = sig_res_zones[0]["price"] if sig_res_zones else nearest_res
    nearest_sig_sup = sig_sup_zones[0]["price"] if sig_sup_zones else nearest_sup

    dist_res_pct = round((nearest_res - curr_price) / curr_price * 100.0, 3) if nearest_res else None
    dist_sup_pct = round((curr_price - nearest_sup) / curr_price * 100.0, 3) if nearest_sup else None

    room_to_run_atr = round((nearest_sig_res - curr_price) / curr_atr, 2) if (nearest_sig_res and curr_atr > 0) else None
    room_to_run_short_atr = round((curr_price - nearest_sig_sup) / curr_atr, 2) if (nearest_sig_sup and curr_atr > 0) else None

    return {
        "support_zones": sup_zones[:5],
        "resistance_zones": res_zones[:5],
        "nearest_support": nearest_sup,
        "nearest_resistance": nearest_res,
        "dist_support_pct": dist_sup_pct,
        "dist_resistance_pct": dist_res_pct,
        "room_to_run_atr": room_to_run_atr,
        "room_to_run_short_atr": room_to_run_short_atr,
        "atr": round(curr_atr, 4),
    }


def detect_liquidity_sweeps(df: pd.DataFrame, lookback: int = 20) -> dict[str, Any] | None:
    """Detect liquidity sweeps (stop hunts) where price briefly pierced recent extremes but failed to hold."""
    if len(df) < lookback + 2:
        return None

    recent = df.iloc[-(lookback + 1):-1]
    last = df.iloc[-1]

    highest_high = _safe_float(recent["high"].max())
    lowest_low = _safe_float(recent["low"].min())

    c = _safe_float(last.get("close"))
    h = _safe_float(last.get("high"))
    l = _safe_float(last.get("low"))

    # Bearish sweep: High pierced above previous highest high, but closed back below it (fakeout)
    if h > highest_high and c < highest_high:
        return {
            "type": "bearish_liquidity_sweep",
            "direction": "bearish",
            "level_swept": round(highest_high, 4),
            "sweep_high": round(h, 4),
            "close": round(c, 4),
            "desc": "Bearish liquidity sweep above recent swing high (fakeout trap)",
            "strength": 0.85,
        }

    # Bullish sweep: Low pierced below previous lowest low, but closed back above it (bear trap absorption)
    if l < lowest_low and c > lowest_low:
        return {
            "type": "bullish_liquidity_sweep",
            "direction": "bullish",
            "level_swept": round(lowest_low, 4),
            "sweep_low": round(l, 4),
            "close": round(c, 4),
            "desc": "Bullish liquidity sweep below recent swing low (bear trap absorption)",
            "strength": 0.85,
        }

    return None


def analyze_market_structure(df: pd.DataFrame, lookback: int = 50) -> dict[str, Any]:
    """Analyze Higher Highs/Higher Lows (BOS) vs Lower Highs/Lower Lows (CHoCH)."""
    if len(df) < 15:
        return {"trend": "neutral", "structure": "ranging", "score": 0.0}

    sample = df.iloc[-lookback:]
    highs = sample["high"].astype(float).values
    lows = sample["low"].astype(float).values

    # Find local 5-bar swing fractal pivots
    swing_highs: list[float] = []
    swing_lows: list[float] = []
    for i in range(2, len(sample) - 2):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
            swing_lows.append(lows[i])

    score = 0.0
    trend = "neutral"

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        hh = swing_highs[-1] > swing_highs[-2]
        hl = swing_lows[-1] > swing_lows[-2]
        lh = swing_highs[-1] < swing_highs[-2]
        ll = swing_lows[-1] < swing_lows[-2]

        if hh and hl:
            trend = "bullish"
            score = 65.0
        elif lh and ll:
            trend = "bearish"
            score = -65.0
        elif hh and ll:
            trend = "expanding_volatility"
            score = 0.0
        elif lh and hl:
            trend = "contracting_triangle"
            score = 0.0

    return {
        "trend": trend,
        "score": score,
        "swing_highs_count": len(swing_highs),
        "swing_lows_count": len(swing_lows),
    }


def evaluate_price_action(df: pd.DataFrame) -> dict[str, Any]:
    """Master evaluator combining candlestick patterns, S/R zones, liquidity sweeps, and structure."""
    if len(df) < 10:
        return {
            "score": 0.0,
            "bias": "neutral",
            "patterns": [],
            "nearest_support": None,
            "nearest_resistance": None,
            "dist_support_pct": None,
            "dist_resistance_pct": None,
            "room_to_run_atr": None,
            "room_to_run_short_atr": None,
            "atr": 0.0,
            "support_zones": [],
            "resistance_zones": [],
            "liquidity_sweep": None,
            "market_structure": {"trend": "neutral", "score": 0.0},
            "last_candle": {},
        }

    last_bar = df.iloc[-1]
    last_candle_anatomy = analyze_candle_anatomy(last_bar)
    patterns = detect_candlestick_patterns(df, lookback=4)
    sr = detect_support_resistance_zones(df)
    sweep = detect_liquidity_sweeps(df)
    structure = analyze_market_structure(df)

    # Base composite from market structure
    composite_score = float(structure.get("score", 0.0)) * 0.4

    # Add candlestick pattern signals
    for pat in patterns:
        dir_mult = 1.0 if pat.get("direction") == "bullish" else (-1.0 if pat.get("direction") == "bearish" else 0.0)
        recency = 1.0 if pat.get("bar_offset") == -1 else 0.7
        composite_score += dir_mult * float(pat.get("strength", 0.0)) * 25.0 * recency

    # Add liquidity sweep impact
    if sweep:
        sweep_mult = 1.0 if sweep.get("direction") == "bullish" else -1.0
        composite_score += sweep_mult * float(sweep.get("strength", 0.0)) * 30.0

    # Add last-candle rejection bias
    if last_candle_anatomy.get("rejection") == "bullish_rejection":
        composite_score += 20.0
    elif last_candle_anatomy.get("rejection") == "bearish_rejection":
        composite_score -= 20.0

    final_score = float(np.clip(composite_score, -100.0, 100.0))
    bias = "bullish" if final_score >= 25.0 else ("bearish" if final_score <= -25.0 else "neutral")

    # Format visual chart markers for Lightweight Charts if timestamps are available
    chart_markers = []
    try:
        times: list[int] = []
        if isinstance(df.index, pd.DatetimeIndex) or hasattr(df.index, "view"):
            times = [int(t) for t in (df.index.view("int64") // 1_000_000_000)]
        elif "time" in df.columns:
            times = [int(t) for t in df["time"]]

        if times:
            for pat in patterns:
                bo = pat.get("bar_offset", -1)
                idx = len(times) + bo if bo < 0 else bo
                if 0 <= idx < len(times):
                    ts = times[idx]
                    d = pat.get("direction", "neutral")
                    chart_markers.append({
                        "time": ts,
                        "position": "belowBar" if d == "bullish" else "aboveBar",
                        "color": "#10b981" if d == "bullish" else ("#f43f5e" if d == "bearish" else "#6366f1"),
                        "shape": "arrowUp" if d == "bullish" else ("arrowDown" if d == "bearish" else "circle"),
                        "text": pat.get("name", "Pattern"),
                    })
            if sweep:
                ts = times[-1]
                sdir = sweep.get("direction", "bullish")
                chart_markers.append({
                    "time": ts,
                    "position": "belowBar" if sdir == "bullish" else "aboveBar",
                    "color": "#eab308",
                    "shape": "circle",
                    "text": f"Sweep ({sdir[:4]})",
                })
    except Exception:
        chart_markers = []

    return {
        "score": round(final_score, 1),
        "bias": bias,
        "patterns": patterns,
        "nearest_support": sr.get("nearest_support"),
        "nearest_resistance": sr.get("nearest_resistance"),
        "dist_support_pct": sr.get("dist_support_pct"),
        "dist_resistance_pct": sr.get("dist_resistance_pct"),
        "room_to_run_atr": sr.get("room_to_run_atr"),
        "room_to_run_short_atr": sr.get("room_to_run_short_atr"),
        "atr": sr.get("atr", 0.0),
        "support_zones": sr.get("support_zones", []),
        "resistance_zones": sr.get("resistance_zones", []),
        "liquidity_sweep": sweep,
        "market_structure": structure,
        "last_candle": last_candle_anatomy,
        "chart_markers": chart_markers,
    }


def validate_trade_price_action(
    df: pd.DataFrame,
    direction: Literal["long", "short"],
    min_clearance_atr: float = 0.50,
    max_opposing_wick_pct: float = 0.45,
) -> tuple[bool, str, dict[str, Any]]:
    """Strict pre-trade gate for Flash, Core, and Long-Term execution.

    Verifies:
      1. Last closed candle did NOT suffer severe opposing wick rejection (absorption trap).
      2. Trade is NOT firing directly into a massive opposing S/R zone (< min_clearance_atr).
      3. Trade is NOT fighting a fresh opposing liquidity sweep.
    """
    if len(df) < 15:
        return True, "insufficient_data_bypassed", {}

    pa = evaluate_price_action(df)
    last_candle = pa.get("last_candle", {})
    sweep = pa.get("liquidity_sweep")
    room_to_run = pa.get("room_to_run_atr")

    if direction == "long":
        # 1. Opposing rejection wick check (upper wick on long = sellers dumping at high)
        if float(last_candle.get("upper_wick_ratio", 0.0)) >= max_opposing_wick_pct:
            return (
                False,
                f"blocked: severe upper wick rejection ({last_candle['upper_wick_ratio']*100:.1f}%)",
                pa,
            )

        # 2. Resistance clearance check (never buy right below major resistance)
        if room_to_run is not None and room_to_run < min_clearance_atr:
            return (
                False,
                f"blocked: nearest resistance too close ({room_to_run:.2f} ATR < {min_clearance_atr} ATR clearance)",
                pa,
            )

        # 3. Liquidity sweep check (never buy right after a bearish sweep fakeout)
        if sweep and sweep.get("direction") == "bearish":
            return False, "blocked: recent bearish liquidity sweep (fakeout trap)", pa

    elif direction == "short":
        # 1. Opposing rejection wick check (lower wick on short = buyers absorbing dip)
        if float(last_candle.get("lower_wick_ratio", 0.0)) >= max_opposing_wick_pct:
            return (
                False,
                f"blocked: severe lower wick rejection ({last_candle['lower_wick_ratio']*100:.1f}%)",
                pa,
            )

        # 2. Support clearance check (never short right above major support)
        nearest_sup = pa.get("nearest_support")
        atr = pa.get("atr") or last_candle.get("range", 1.0)
        curr_price = _safe_float(df["close"].iloc[-1])
        if nearest_sup and curr_price > nearest_sup and atr > 0:
            dist_sup_atr = (curr_price - nearest_sup) / atr
            if dist_sup_atr < min_clearance_atr:
                return (
                    False,
                    f"blocked: nearest support too close ({dist_sup_atr:.2f} ATR < {min_clearance_atr} ATR clearance)",
                    pa,
                )

        # 3. Liquidity sweep check (never short right after a bullish sweep bear trap)
        if sweep and sweep.get("direction") == "bullish":
            return False, "blocked: recent bullish liquidity sweep (bear trap)", pa

    return True, "price_action_confirmed", pa
