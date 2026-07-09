"""Adaptive per-regime factor weighting with a walk-forward champion/challenger gate.

How it works (PLAN.md §5):
  1. Join factor_logs + outcomes + signals.regime -> training rows (features = the 4 BACKTESTABLE
     category scores; label = win/loss).
  2. Per regime with ENOUGH resolved outcomes, fit a small L2 logistic regression. The positive
     coefficients become a CHALLENGER weight profile (live-only categories keep their fixed weight,
     so the profile still sums to 1 and only the backtestable mix is adapted).
  3. GATE: the challenger must beat the current CHAMPION on a walk-forward (holdout) backtest across
     a basket. Only then is it promoted into regime_weights. This is what stops "self-improvement"
     from drifting into noise.

Discipline first: below `min_samples` resolved outcomes per regime, we DO NOT touch the weights and
say so. With almost no data (the current state), that is the correct, honest behaviour.
"""

from __future__ import annotations

import json
import time

import numpy as np

from . import db
from .backtest import backtest
from .data import fetch_klines_history
from .factors.weights import CATEGORIES, regime_base_weights, timeframe_bucket, weights_for_interval
from .indicators import compute_indicators
from .regime import REGIMES

BACKTESTABLE = ("trend", "momentum", "volatility", "structure")
_BASKET = ("BTCUSDT", "ETHUSDT")
_BUCKET_INTERVAL = {"intraday": "15m", "short": "4h", "swing": "1d", "long": "1w"}
# Blueprint v2 §2.3.3: 40 is too few for d=4 with overlapping trades. Raised, and paired with
# shrinkage toward the global profile (below) so low-N regimes can't overfit to noise.
MIN_SAMPLES = 60
_SHRINKAGE_K = 100.0          # §2.3.3 shrink weight: w = (n*w_local + k*w_global)/(n+k)
_DECAY_HALFLIFE_DAYS = 90.0   # §4.1 time-decay: recent outcomes weigh more
_PROMOTE_MARGIN = 0.002       # §2.4 challenger must beat champion OOS by a margin, not just tie

_champions: dict[tuple[str, str], dict] | None = None


# --- Active-weight provider (used by the live scorer) -----------------------


def _load_champions() -> dict[tuple[str, str], dict]:
    champ: dict[tuple[str, str], dict] = {}
    if not db.enabled():
        return champ
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute("select regime, interval, weights from regime_weights where is_champion = true")
            for regime, bucket, weights in cur.fetchall():
                champ[(regime, bucket)] = weights if isinstance(weights, dict) else json.loads(weights)
    except Exception:
        pass
    return champ


def refresh() -> None:
    global _champions
    _champions = _load_champions()


def active_weights(interval: str, regime: str | None) -> dict:
    """Champion weights for (regime, timeframe) if one was promoted, else the fixed profile."""
    global _champions
    if _champions is None:
        _champions = _load_champions()
    if regime:
        champ = _champions.get((regime, timeframe_bucket(interval)))
        if champ:
            return champ
        base = regime_base_weights(regime)  # regime-conditional defaults (Confluence L3)
        if base:
            return base
    return weights_for_interval(interval)


# --- Training data ----------------------------------------------------------


def _training_rows() -> list[dict]:
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select s.regime, s.interval,
                   f.trend, f.momentum, f.volatility, f.structure,
                   o.result, o.pnl,
                   extract(epoch from (now() - o.resolved_at)) / 86400.0 as age_days
            from outcomes o
            join signals s on s.id = o.signal_id
            join factor_logs f on f.signal_id = s.id
            where o.result is not null and o.pnl is not null and s.regime is not null
            """
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def resolved_counts() -> dict[str, int]:
    counts = {r: 0 for r in REGIMES}
    if not db.enabled():
        return counts
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select s.regime, count(*)
                from outcomes o join signals s on s.id = o.signal_id
                where o.result is not null and s.regime is not null
                group by s.regime
                """
            )
            for regime, c in cur.fetchall():
                counts[regime] = int(c)
    except Exception:
        pass
    return counts


# --- Challenger training ----------------------------------------------------


def _fit_logreg(X: np.ndarray, y: np.ndarray, sw: np.ndarray,
                l2: float = 2.0, iters: int = 400, lr: float = 0.2) -> np.ndarray:
    """Sample-weighted L2 logistic regression (weighted by payoff x recency x uniqueness)."""
    Xs = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    n, d = Xs.shape
    swn = sw / (sw.mean() + 1e-12)          # normalize weights to mean 1
    w = np.zeros(d)
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(Xs @ w)))
        grad = Xs.T @ (swn * (p - y)) / n + l2 * w / n
        w -= lr * grad
    return w


def _sample_weights(rows: list[dict]) -> np.ndarray:
    """§2.3.1/§4.1: weight each sample by |pnl| (payoff-aware) x exp(-age/halflife) (recency).

    Payoff weighting stops the model preferring high-hit-rate/low-payoff setups over the reverse;
    time-decay lets recent market behaviour dominate so old regimes fade instead of polluting.
    """
    pnl = np.array([abs(float(r["pnl"] or 0.0)) for r in rows], dtype=float)
    payoff = np.clip(pnl, 1e-4, None)       # floor so a ~breakeven trade still counts a little
    age = np.array([max(0.0, float(r.get("age_days") or 0.0)) for r in rows], dtype=float)
    lam = np.log(2.0) / _DECAY_HALFLIFE_DAYS
    recency = np.exp(-lam * age)
    return payoff * recency


def _challenger_weights(rows: list[dict], bucket_interval: str) -> dict | None:
    X = np.array([[float(r[c] or 0.0) for c in BACKTESTABLE] for r in rows], dtype=float)
    # §2.3.2: label on realized P&L (includes timeouts), NOT result=='target' (which drops the
    # non-random chop timeouts and biases the model).
    y = np.array([1.0 if float(r["pnl"] or 0.0) > 0 else 0.0 for r in rows], dtype=float)
    if len(set(y.tolist())) < 2:
        return None  # all wins or all losses — nothing to learn

    sw = _sample_weights(rows)
    coef = _fit_logreg(X, y, sw)
    # §2.3.4: DO NOT clip to positives — a reliably negative factor is a working contrarian
    # signal. Keep the sign, renormalize by sum(|coef|) so the backtestable block keeps its mass.
    denom = np.abs(coef).sum()
    if denom <= 1e-9:
        return None  # no factor carries information — keep the champion

    fixed = weights_for_interval(bucket_interval)
    indicator_total = sum(fixed[c] for c in BACKTESTABLE)
    learned = coef / denom * indicator_total   # signed weights, |sum| == indicator_total

    # §2.3.3: shrink learned weights toward the global profile by k (guards low-N overfitting).
    n = len(rows)
    challenger = dict(fixed)
    for cat, w_local in zip(BACKTESTABLE, learned):
        w_global = fixed[cat]
        w = (n * float(w_local) + _SHRINKAGE_K * w_global) / (n + _SHRINKAGE_K)
        challenger[cat] = round(w, 4)
    return challenger


# --- Walk-forward gate ------------------------------------------------------


def _basket_holdout_return(interval: str, weights: dict) -> float:
    """Sum of OOS (last 40%) backtest returns across the basket with these weights."""
    total = 0.0
    for symbol in _BASKET:
        try:
            ind = compute_indicators(fetch_klines_history(symbol, interval, 2000))
        except Exception:
            continue
        n = len(ind)
        start = int(n * 0.6)
        res = backtest(ind, symbol, interval, start_idx=start, end_idx=n, weights_override=weights)
        total += res.total_return
    return total


def _promote(regime: str, bucket: str, weights: dict) -> None:
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "update regime_weights set is_champion = false where regime = %s and interval = %s",
            (regime, bucket),
        )
        cur.execute(
            "insert into regime_weights (regime, interval, weights, is_champion) values (%s,%s,%s,true)",
            (regime, bucket, json.dumps(weights)),
        )
        conn.commit()


# --- Public entry points ----------------------------------------------------


def train_and_gate(min_samples: int = MIN_SAMPLES) -> dict:
    """Try to learn + promote challenger weights per regime. Returns a per-regime report."""
    if not db.enabled():
        return {"enabled": False, "regimes": {}}

    try:
        rows = _training_rows()
    except Exception:
        return {"enabled": True, "error": "training query failed", "regimes": {}}

    by_regime: dict[str, list[dict]] = {r: [] for r in REGIMES}
    for row in rows:
        by_regime.setdefault(row["regime"], []).append(row)

    report: dict[str, dict] = {}
    for regime, grp in by_regime.items():
        n = len(grp)
        if n < min_samples:
            report[regime] = {"samples": n, "status": "insufficient_data",
                              "needed": min_samples, "promoted": False}
            continue

        bucket = timeframe_bucket(grp[0]["interval"])
        bucket_interval = _BUCKET_INTERVAL.get(bucket, "4h")
        challenger = _challenger_weights(grp, bucket_interval)
        if challenger is None:
            report[regime] = {"samples": n, "status": "no_predictive_signal", "promoted": False}
            continue

        champion = active_weights(bucket_interval, regime)
        champ_ret = float(_basket_holdout_return(bucket_interval, champion))
        chal_ret = float(_basket_holdout_return(bucket_interval, challenger))
        # §2.4: require the challenger to CLEAR the champion by a margin (not merely tie/edge past
        # it), a pragmatic multiple-testing haircut against promoting noise.
        promoted = bool(chal_ret > champ_ret + _PROMOTE_MARGIN)
        if promoted:
            _promote(regime, bucket, challenger)

        report[regime] = {
            "samples": n, "status": "gated",
            "champion_oos": round(champ_ret, 4), "challenger_oos": round(chal_ret, 4),
            "promoted": promoted,
            "challenger_weights": challenger if promoted else None,
        }

    refresh()
    return {"enabled": True, "min_samples": min_samples, "regimes": report}


_TREND_REGIMES = {"strong_trend", "weak_trend"}
_ALL_REGIMES = ("strong_trend", "weak_trend", "range", "high_vol", "squeeze")
_regime_perf_cache: tuple[float, int, dict] | None = None
_REGIME_TTL = 120  # short cache so the gates react quickly to new outcomes


def regime_performance(window_days: int = 4) -> dict[str, dict]:
    """Per-regime realized stats over a rolling window: {regime: {trades, wins, pnl_frac}}. Cached."""
    global _regime_perf_cache
    now = time.time()
    if _regime_perf_cache and _regime_perf_cache[1] == window_days and now - _regime_perf_cache[0] < _REGIME_TTL:
        return _regime_perf_cache[2]
    result: dict[str, dict] = {}
    if db.enabled():
        try:
            with db.get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""
                    select coalesce(s.regime,'unknown') r, count(*),
                           count(*) filter (where o.pnl > 0), coalesce(sum(o.pnl), 0)
                    from outcomes o join signals s on s.id = o.signal_id
                    where o.pnl is not null and o.resolved_at > now() - interval '{int(window_days)} days'
                    group by r
                    """
                )
                for r, n, w, pnl in cur.fetchall():
                    result[r] = {"trades": int(n), "wins": int(w), "pnl_frac": float(pnl)}
        except Exception:
            pass
    _regime_perf_cache = (now, window_days, result)
    return result


def tradeable_regimes(min_sample: int = 12, window_days: int = 4) -> set[str]:
    """Regimes we're allowed to trade: proven-positive, or thin (benefit-of-doubt re-exploration).

    Data-driven loss-cutting: a regime with >= min_sample resolved trades and NEGATIVE net P&L is
    dropped until its losing trades age out of the window. A regime with too little data gets the
    benefit of the doubt so it can re-prove itself (this is what lets the range-fade family re-open
    once the old continuation-era range losses age out — otherwise range would deadlock, unable to
    take the new trades it needs to re-qualify). The EV gate is the per-trade backstop that still
    blocks negative-EV setups even in a re-opened regime.
    """
    perf = regime_performance(window_days)
    out: set[str] = set()
    for r in _ALL_REGIMES:
        p = perf.get(r)
        if p is None or p["trades"] < min_sample:
            out.add(r)  # thin -> benefit of the doubt / auto re-exploration
        elif p["pnl_frac"] > 0:
            out.add(r)
    # NO fallback: if every regime (trend ones included) has proven negative expectancy, stand
    # down entirely rather than forcing trades into a losing market. Thin regimes still get
    # benefit-of-doubt above, so this only empties when trend regimes are *proven* losers -> the
    # losing trades then age out of the window and the regime auto-re-tests later.
    return out


_LONG_LABELS = ("Buy", "Strong Buy")
_dir_perf_cache: tuple[float, dict] | None = None
_sym_perf_cache: tuple[float, dict] | None = None


def symbol_performance(window_days: int = 5) -> dict[str, dict]:
    """Per-symbol realized stats over a rolling window: {symbol: {trades, wins, pnl_frac}}. Cached."""
    global _sym_perf_cache
    now = time.time()
    if _sym_perf_cache and now - _sym_perf_cache[0] < _REGIME_TTL:
        return _sym_perf_cache[1]
    result: dict[str, dict] = {}
    if db.enabled():
        try:
            with db.get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""
                    select s.symbol, count(*), count(*) filter (where o.pnl > 0), coalesce(sum(o.pnl), 0)
                    from outcomes o join signals s on s.id = o.signal_id
                    where o.pnl is not null and o.resolved_at > now() - interval '{int(window_days)} days'
                    group by s.symbol
                    """
                )
                for sym, n, w, pnl in cur.fetchall():
                    result[sym] = {"trades": int(n), "wins": int(w), "pnl_frac": float(pnl)}
        except Exception:
            pass
    _sym_perf_cache = (now, result)
    return result


def is_symbol_tradeable(symbol: str, min_sample: int = 12, window_days: int = 5) -> bool:
    """A symbol is paused only if it has >= min_sample recent trades AND negative net P&L."""
    p = symbol_performance(window_days).get(symbol)
    if p is None or p["trades"] < min_sample:
        return True  # thin -> benefit of the doubt (also lets a paused symbol re-explore)
    return p["pnl_frac"] > 0


def direction_performance(window_days: int = 21) -> dict[str, dict]:
    """Rolling per-direction stats {long/short: {trades, wins, pnl_frac}} over the last window."""
    global _dir_perf_cache
    now = time.time()
    if _dir_perf_cache and now - _dir_perf_cache[0] < _REGIME_TTL:
        return _dir_perf_cache[1]
    result: dict[str, dict] = {}
    if db.enabled():
        try:
            with db.get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""
                    select case when s.label in ('Buy','Strong Buy') then 'long' else 'short' end d,
                           count(*), count(*) filter (where o.pnl > 0), coalesce(sum(o.pnl), 0)
                    from outcomes o join signals s on s.id = o.signal_id
                    where o.pnl is not null and s.label <> 'Neutral'
                      and o.resolved_at > now() - interval '{int(window_days)} days'
                    group by d
                    """
                )
                for d, n, w, pnl in cur.fetchall():
                    result[d] = {"trades": int(n), "wins": int(w), "pnl_frac": float(pnl)}
        except Exception:
            pass
    _dir_perf_cache = (now, result)
    return result


def tradeable_directions(min_sample: int = 12, window_days: int = 21) -> set[str]:
    """Directions allowed to trade: proven-positive, or thin (benefit of the doubt).

    A direction with >= min_sample resolved trades and NEGATIVE rolling P&L is dropped until it
    turns positive again. This cuts the persistent short (or long) bleed automatically.
    """
    perf = direction_performance(window_days)
    out: set[str] = set()
    for d in ("long", "short"):
        p = perf.get(d)
        if p is None or p["trades"] < min_sample:
            out.add(d)
        elif p["pnl_frac"] > 0:
            out.add(d)
    # NO fallback: if BOTH directions have proven negative expectancy, stand down entirely
    # ("silence is a position"). Losing trades age out of the window -> auto re-test later.
    return out


def learning_status() -> dict:
    if not db.enabled():
        return {"enabled": False}
    champ = _load_champions()
    return {
        "enabled": True,
        "min_samples": MIN_SAMPLES,
        "resolved_per_regime": resolved_counts(),
        "champions": {f"{r}/{b}": w for (r, b), w in champ.items()},
    }
