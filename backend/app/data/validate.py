"""Candle validation at ingest (Blueprint v2 §11).

Bad candles silently corrupt every downstream number — a duplicated timestamp double-counts a
bar, a zero/NaN price NaNs an indicator, an out-of-order index breaks the causal backtest. This
cleans an OHLCV frame defensively (never raises on the live path) and reports what it fixed.

Rules:
  * index must be a unique, sorted DatetimeIndex (drop duplicate timestamps, keep last)
  * OHLC must be finite and strictly positive; drop rows that aren't
  * high >= max(open, close, low) and low <= min(open, close, high) — drop violated bars
  * volume may be zero (some forex feeds report 0); negative volume -> 0
Large time gaps are reported (not dropped) so a scheduler/alerting layer can react.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_OHLC = ("open", "high", "low", "close")


def validate_ohlcv(df: pd.DataFrame, interval: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Return (clean_df, report). Best-effort: on any structural problem, returns what it can."""
    report = {"rows_in": int(len(df)), "dropped": 0, "dedup": 0, "reordered": False, "gaps": 0}
    if df is None or df.empty:
        return df, report

    out = df.copy()

    # 1. Unique, sorted index.
    if not out.index.is_monotonic_increasing:
        out = out.sort_index()
        report["reordered"] = True
    dup = out.index.duplicated(keep="last")
    if dup.any():
        report["dedup"] = int(dup.sum())
        out = out[~dup]

    # 2. Finite, positive OHLC.
    present = [c for c in _OHLC if c in out.columns]
    before = len(out)
    if present:
        finite = np.isfinite(out[present].to_numpy()).all(axis=1)
        positive = (out[present].to_numpy() > 0).all(axis=1)
        out = out[finite & positive]

    # 3. OHLC internal consistency (high is the max, low is the min).
    if set(_OHLC).issubset(out.columns) and not out.empty:
        hi_ok = out["high"] >= out[["open", "close", "low"]].max(axis=1)
        lo_ok = out["low"] <= out[["open", "close", "high"]].min(axis=1)
        out = out[hi_ok & lo_ok]

    report["dropped"] = int(before - len(out))

    # 4. Non-negative volume.
    if "volume" in out.columns:
        out["volume"] = out["volume"].clip(lower=0.0)

    # 5. Report (don't drop) abnormal time gaps — a missing candle run.
    if interval and len(out) > 2 and isinstance(out.index, pd.DatetimeIndex):
        from .binance import INTERVAL_SECONDS
        step = INTERVAL_SECONDS.get(interval)
        if step:
            deltas = out.index.to_series().diff().dt.total_seconds().dropna()
            report["gaps"] = int((deltas > step * 1.5).sum())

    report["rows_out"] = int(len(out))
    return out, report
