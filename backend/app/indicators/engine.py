"""Pure pandas/numpy indicators — transparent, deterministic, and causal.

Causal = every value at bar *t* depends only on bars <= t. This is what lets the
backtest harness iterate bar-by-bar without lookahead. We deliberately avoid pandas-ta
(numpy 2.x incompatibility) and TA-Lib (Windows C toolchain pain). Every formula here is
auditable.

The public entry point is `compute_indicators(df)`, which takes an OHLCV DataFrame
(columns: open, high, low, close, volume; DatetimeIndex) and returns a copy with all
indicator columns appended.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# --- Individual indicators -------------------------------------------------


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder smoothing == EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.fillna(100.0).where(avg_loss != 0, 100.0)


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14, d: int = 3
) -> tuple[pd.Series, pd.Series]:
    lowest = low.rolling(k, min_periods=k).min()
    highest = high.rolling(k, min_periods=k).max()
    rng = (highest - lowest).replace(0.0, np.nan)
    percent_k = 100.0 * (close - lowest) / rng
    percent_d = percent_k.rolling(d, min_periods=d).mean()
    return percent_k, percent_d


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Average True Range."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def bollinger(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    mid = sma(close, period)
    std = close.rolling(period, min_periods=period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / mid.replace(0.0, np.nan)
    return mid, upper, lower, width


def rolling_vwap(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int = 20
) -> pd.Series:
    """Rolling VWAP over `window` bars (causal; no session anchoring needed for backtests)."""
    typical = (high + low + close) / 3.0
    pv = (typical * volume).rolling(window, min_periods=window).sum()
    vol = volume.rolling(window, min_periods=window).sum().replace(0.0, np.nan)
    return pv / vol


def classic_pivots(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Classic floor-trader pivots from the *previous* bar (causal by construction)."""
    prev_h, prev_l, prev_c = high.shift(1), low.shift(1), close.shift(1)
    pivot = (prev_h + prev_l + prev_c) / 3.0
    r1 = 2 * pivot - prev_l
    s1 = 2 * pivot - prev_h
    return pivot, r1, s1


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's ADX — trend strength (regime gate). >25 strong trend, <18 range."""
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)
    atr_ = _true_range(high, low, close).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    atr_ = atr_.replace(0.0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_
    denom = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denom
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def choppiness(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Choppiness Index — range vs trend. >61 choppy/range, <38 trending."""
    tr = _true_range(high, low, close)
    sum_tr = tr.rolling(period, min_periods=period).sum()
    rng = (high.rolling(period, min_periods=period).max() - low.rolling(period, min_periods=period).min()).replace(0.0, np.nan)
    return 100 * np.log10(sum_tr / rng) / np.log10(period)


def tema(series: pd.Series, length: int) -> pd.Series:
    """Triple EMA — the default MA in LuxAlgo's MA Sabres."""
    e1 = ema(series, length)
    e2 = ema(e1, length)
    e3 = ema(e2, length)
    return 3 * e1 - 3 * e2 + e3


def ut_bot(close: pd.Series, atr_series: pd.Series, key: float = 1.0) -> tuple[pd.Series, pd.Series]:
    """UT Bot Alerts (Pine v4 port) — ATR trailing stop + position state.

    Returns (trailing_stop, position) where position is +1 (long), -1 (short), 0 (none).
    The recurrence matches the original: nz(stop[1], 0) seeds at 0. This is necessarily a
    sequential loop because each bar's stop depends on the previous bar's stop.
    """
    src = close.to_numpy(dtype=float)
    nloss = (key * atr_series).to_numpy(dtype=float)
    n = len(src)
    stop = np.full(n, np.nan)
    pos = np.zeros(n)
    prev_stop = 0.0
    prev_pos = 0.0

    for i in range(n):
        if np.isnan(nloss[i]):
            stop[i] = prev_stop
            pos[i] = prev_pos
            continue
        s = src[i]
        sp = src[i - 1] if i > 0 else s
        if s > prev_stop and sp > prev_stop:
            cur = max(prev_stop, s - nloss[i])
        elif s < prev_stop and sp < prev_stop:
            cur = min(prev_stop, s + nloss[i])
        elif s > prev_stop:
            cur = s - nloss[i]
        else:
            cur = s + nloss[i]

        if i > 0 and sp < prev_stop and s > prev_stop:
            cur_pos = 1.0
        elif i > 0 and sp > prev_stop and s < prev_stop:
            cur_pos = -1.0
        else:
            cur_pos = prev_pos

        stop[i] = cur
        pos[i] = cur_pos
        prev_stop, prev_pos = cur, cur_pos

    idx = close.index
    return pd.Series(stop, index=idx), pd.Series(pos, index=idx)


def ma_sabres(close: pd.Series, length: int = 50, count: int = 20) -> pd.Series:
    """LuxAlgo MA Sabres reversal signal (TEMA default): +1 bullish flip, -1 bearish flip, 0 none.

    up = MA was strictly falling for `count` bars (as of the prior bar) and now ticks up.
    dn = MA was strictly rising for `count` bars (as of the prior bar) and now ticks down.
    """
    ma = tema(close, length)
    diff = ma.diff()
    falling = (diff < 0).rolling(count, min_periods=count).sum().eq(count)
    rising = (diff > 0).rolling(count, min_periods=count).sum().eq(count)
    up = falling.shift(1, fill_value=False) & (ma > ma.shift(1))
    dn = rising.shift(1, fill_value=False) & (ma < ma.shift(1))
    return up.astype(int) - dn.astype(int)


def variance_ratio(close: pd.Series, q: int = 4, window: int = 100) -> pd.Series:
    """Lo-MacKinlay Variance Ratio VR(q) = Var(q-bar returns) / (q * Var(1-bar returns)) (§3.5).

    VR > 1 => momentum/persistence present; VR < 1 => mean reversion; ~1 => random walk. Causal,
    rolling. Centered at 1.0 (a natural 'no info' point) so the meta-model reads deviations."""
    logp = np.log(close.replace(0.0, np.nan))
    r1 = logp.diff()
    rq = logp.diff(q)
    var1 = r1.rolling(window, min_periods=window // 2).var()
    varq = rq.rolling(window, min_periods=window // 2).var()
    vr = varq / (q * var1.replace(0.0, np.nan))
    return vr.replace([np.inf, -np.inf], np.nan)


def return_entropy(close: pd.Series, window: int = 32) -> pd.Series:
    """Shannon entropy (bits) of the up/down return-sign sequence over `window` (§3.6).

    ~1.0 = coin-flip (nothing to predict); ~0.0 = strongly one-directional. Causal, rolling."""
    up = (close.diff() > 0).astype(float)
    p = up.rolling(window, min_periods=window).mean().clip(1e-6, 1 - 1e-6)
    return -(p * np.log2(p) + (1 - p) * np.log2(1 - p))


def _hurst_rs(r: np.ndarray) -> float:
    """Rescaled-range (R/S) Hurst estimate for one window of returns. NaN if undersized."""
    n = len(r)
    scales = [s for s in (n // 4, n // 2, n) if s >= 8]
    if len(scales) < 2:
        return np.nan
    logs, logrs = [], []
    for s in scales:
        chunks = n // s
        vals = []
        for c in range(chunks):
            seg = r[c * s:(c + 1) * s]
            sd = seg.std()
            if sd <= 0:
                continue
            dev = np.cumsum(seg - seg.mean())
            vals.append((dev.max() - dev.min()) / sd)
        if vals:
            logs.append(np.log(s)); logrs.append(np.log(np.mean(vals)))
    if len(logs) < 2:
        return np.nan
    return float(np.polyfit(logs, logrs, 1)[0])


def hurst_exponent(close: pd.Series, window: int = 100) -> pd.Series:
    """Rolling Hurst exponent (§3.2). H>0.55 trending/persistent, H<0.45 mean-reverting, ~0.5 random."""
    r = np.log(close.replace(0.0, np.nan)).diff()
    return r.rolling(window, min_periods=window).apply(_hurst_rs, raw=True)


def kalman_slope(close: pd.Series, atr_series: pd.Series,
                 q_level: float = 1e-3, q_slope: float = 1e-4, r_obs: float = 1.0) -> pd.Series:
    """Local-linear-trend Kalman filter slope, in ATR units (§3.1) — adaptive, near lag-free.

    State = [level, slope]; observation = close. The filtered slope divided by ATR is a scale-free,
    self-tuning trend-strength/direction estimate. Sequential (each bar depends on the previous)."""
    x = close.to_numpy(dtype=float)
    n = len(x)
    out = np.full(n, np.nan)
    level, slope = x[0], 0.0
    P = np.array([[1.0, 0.0], [0.0, 1.0]])
    Q = np.array([[q_level, 0.0], [0.0, q_slope]])
    for t in range(n):
        # Predict
        level = level + slope
        P = np.array([[P[0, 0] + P[0, 1] + P[1, 0] + P[1, 1] + Q[0, 0], P[0, 1] + P[1, 1]],
                      [P[1, 0] + P[1, 1], P[1, 1] + Q[1, 1]]])
        # Update with observation of level
        S = P[0, 0] + r_obs
        k0, k1 = P[0, 0] / S, P[1, 0] / S
        innov = x[t] - level
        level += k0 * innov
        slope += k1 * innov
        P = np.array([[(1 - k0) * P[0, 0], (1 - k0) * P[0, 1]],
                      [P[1, 0] - k1 * P[0, 0], P[1, 1] - k1 * P[0, 1]]])
        out[t] = slope
    atr = atr_series.to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(atr > 0, out / atr, np.nan)
    return pd.Series(ratio, index=close.index)


def ou_halflife(close: pd.Series, window: int = 50) -> pd.Series:
    """Rolling Ornstein-Uhlenbeck / AR(1) half-life of mean reversion (Blueprint v2 §3.3).

    Fit x_t = phi*x_{t-1} on deviations x = close - rolling_mean over `window` bars; the half-life
    of reversion is HL = -ln(2)/ln(phi) for 0<phi<1. Small HL = price snaps back fast (fade-able);
    large/NaN = slow or non-mean-reverting (don't fade). Causal: uses only past bars. Returned in
    BARS. NaN where phi is outside (0,1) (i.e. trending / random walk — not mean reverting).
    """
    dev = close - close.rolling(window, min_periods=window).mean()
    dev1 = dev.shift(1)
    cov = dev.rolling(window, min_periods=window).cov(dev1)
    var = dev1.rolling(window, min_periods=window).var()
    phi = cov / var.replace(0.0, np.nan)
    phi = phi.where((phi > 0.0) & (phi < 1.0))          # only genuine mean reversion
    hl = -np.log(2.0) / np.log(phi)
    return hl.where(np.isfinite(hl))


def fib_position(close: pd.Series, lookback: int = 50) -> pd.Series:
    """Where price sits within the rolling [low, high] range, 0..1.

    0 = at the lookback low, 1 = at the lookback high. A causal proxy for "distance from
    the nearest Fibonacci retracement" without hard-coding which swing is active.
    """
    hh = close.rolling(lookback, min_periods=lookback).max()
    ll = close.rolling(lookback, min_periods=lookback).min()
    rng = (hh - ll).replace(0.0, np.nan)
    return ((close - ll) / rng).clip(0.0, 1.0)


# Higher-timeframe resample rule per base interval (for HTF confluence, §5). No extra network:
# we aggregate the already-fetched OHLCV to a coarser timeframe.
_HTF_RULE = {
    "1m": "15min", "3m": "30min", "5m": "1h", "15m": "4h", "30m": "4h",
    "1h": "4h", "2h": "12h", "4h": "1D", "6h": "1D", "8h": "1D", "12h": "1D",
    "1d": "1W", "3d": "1W", "1w": "1M",
}


def htf_trend(df: pd.DataFrame, interval: str) -> int:
    """Higher-timeframe trend state (+1 up / -1 down / 0 flat) by resampling the base OHLCV.

    Aligns a lower-timeframe signal with the bigger picture: price above a rising HTF EMA = +1.
    Returns 0 when there isn't enough resampled history to judge (safe/neutral)."""
    rule = _HTF_RULE.get(interval)
    if rule is None or "close" not in df.columns or len(df) < 20:
        return 0
    try:
        htf = df["close"].resample(rule).last().dropna()
        if len(htf) < 12:
            return 0
        span = min(20, max(5, len(htf) // 3))
        e = htf.ewm(span=span, adjust=False).mean()
        price = float(htf.iloc[-1])
        ema_now, ema_prev = float(e.iloc[-1]), float(e.iloc[-min(3, len(e))])
        if price > ema_now and ema_now >= ema_prev:
            return 1
        if price < ema_now and ema_now <= ema_prev:
            return -1
    except Exception:
        return 0
    return 0


# --- Aggregator ------------------------------------------------------------


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Append all indicator columns to an OHLCV frame. Returns a copy."""
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV frame missing columns: {sorted(missing)}")

    out = df.copy()
    c, h, l, v = out["close"], out["high"], out["low"], out["volume"]

    # Trend
    out["ema9"] = ema(c, 9)
    out["ema21"] = ema(c, 21)
    out["ema50"] = ema(c, 50)
    out["ema200"] = ema(c, 200)
    macd_line, macd_signal, macd_hist = macd(c)
    out["macd"] = macd_line
    out["macd_signal"] = macd_signal
    out["macd_hist"] = macd_hist

    # Momentum
    out["rsi"] = rsi(c, 14)
    k, d = stochastic(h, l, c, 14, 3)
    out["stoch_k"] = k
    out["stoch_d"] = d

    # Volatility / risk
    out["atr"] = atr(h, l, c, 14)
    bb_mid, bb_up, bb_low, bb_width = bollinger(c, 20, 2.0)
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_up
    out["bb_lower"] = bb_low
    out["bb_width"] = bb_width
    # Bollinger %B: where close sits within the band, 0..1
    band = (bb_up - bb_low).replace(0.0, np.nan)
    out["bb_pctb"] = ((c - bb_low) / band).clip(-0.5, 1.5)

    # Volume / flow
    out["vol_sma20"] = sma(v, 20)
    out["vwap"] = rolling_vwap(h, l, c, v, 20)
    out["vwap_dist"] = (c - out["vwap"]) / out["vwap"].replace(0.0, np.nan)

    # Structure / levels
    pivot, r1, s1 = classic_pivots(h, l, c)
    out["pivot"] = pivot
    out["pivot_r1"] = r1
    out["pivot_s1"] = s1
    out["fib_pos"] = fib_position(c, 50)
    out["ou_halflife"] = ou_halflife(c, 50)  # mean-reversion speed (range-fade gate, §3.3)

    # Advanced statistical machinery (Blueprint v2 §3) — fed to the meta-model as features.
    out["hurst"] = hurst_exponent(c, 100)
    out["variance_ratio"] = variance_ratio(c, 4, 100)
    out["entropy"] = return_entropy(c, 32)
    out["kalman_slope"] = kalman_slope(c, out["atr"])

    # External algos ported from Pine (deterministic, causal)
    atr10 = atr(h, l, c, 10)  # UT Bot uses ATR(10)
    ut_stop, ut_pos = ut_bot(c, atr10, key=1.0)
    out["ut_stop"] = ut_stop
    out["ut_pos"] = ut_pos
    out["sabre"] = ma_sabres(c, length=50, count=20)

    # Regime inputs (Confluence Engine L1)
    out["adx"] = adx(h, l, c, 14)
    out["chop"] = choppiness(h, l, c, 14)
    out["ema200_slope"] = out["ema200"].pct_change(10)
    out["bb_width_min60"] = out["bb_width"].rolling(120, min_periods=30).min()  # squeeze reference

    # Swing levels for risk geometry (Confluence Engine L5)
    out["swing_high"] = h.rolling(20, min_periods=10).max()
    out["swing_low"] = l.rolling(20, min_periods=10).min()

    return out
