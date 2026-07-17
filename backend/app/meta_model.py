"""Meta-labeling model (Blueprint v2 §5) — a secondary take/skip model, run in SHADOW first.

Primary model = the confluence engine (direction). This secondary model predicts P(win) from a
richer feature set (meta_features) and is the blueprint's highest-impact accuracy upgrade. It is
CALIBRATED (isotonic) and validated with time-series CV + embargo, then promoted from shadow to
gating ONLY when it beats the primary calibrated probability out-of-sample AND has enough data.

Model: heavily-regularized weighted logistic regression (robust at a few-hundred samples; a GBT is
a drop-in upgrade once N grows). Sample weights = |pnl| x recency, matching the learning loop.
Dependency-free (numpy only); params persist as JSON in the settings table.
"""

from __future__ import annotations

import json
import time

import numpy as np

from . import db
from .calibration import _pava
from .meta_features import FEATURE_KEYS, build

_MIN_PROMOTE = 300     # blueprint: stay in shadow until ~300 resolved outcomes
_MIN_FIT = 80          # below this, don't even fit
_DECAY_HALFLIFE_DAYS = 90.0
_PROMOTE_AUC_MARGIN = 0.02
_TTL = 300.0
_cache: tuple[float, dict | None] | None = None


# --- math helpers -----------------------------------------------------------

def _rankdata(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    order = a.argsort(kind="mergesort")
    sa = a[order]
    ranks_sorted = np.empty(len(a))
    i, n = 0, len(a)
    while i < n:
        j = i
        while j + 1 < n and sa[j + 1] == sa[i]:
            j += 1
        ranks_sorted[i:j + 1] = (i + 1 + j + 1) / 2.0
        i = j + 1
    ranks = np.empty(len(a))
    ranks[order] = ranks_sorted
    return ranks


def _auc(score: np.ndarray, y: np.ndarray) -> float:
    y = np.asarray(y)
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return 0.5
    r = _rankdata(score)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def _fit_logreg(X: np.ndarray, y: np.ndarray, sw: np.ndarray,
                l2: float = 3.0, iters: int = 600, lr: float = 0.2) -> np.ndarray:
    """Weighted L2 logistic regression with a bias term. X already standardized."""
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    swn = sw / (sw.mean() + 1e-12)
    w = np.zeros(d + 1)
    reg = np.ones(d + 1); reg[-1] = 0.0    # don't regularize the bias
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(Xb @ w)))
        grad = Xb.T @ (swn * (p - y)) / n + l2 * (reg * w) / n
        w -= lr * grad
    return w


def _predict_raw(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, w: np.ndarray) -> np.ndarray:
    Xs = (X - mu) / sd
    Xb = np.hstack([Xs, np.ones((len(Xs), 1))])
    return 1.0 / (1.0 + np.exp(-(Xb @ w)))


# --- training data ----------------------------------------------------------

def _training() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y, sample_weights, baseline_win_prob) ordered by signal time (oldest first)."""
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select s.composite, s.agreement, s.reward_risk, s.atr, s.price, s.regime, s.label,
                   s.win_prob, s.as_of, s.features,
                   f.trend, f.momentum, f.volatility, f.structure, f.flow, f.sentiment, f.macro, f.consensus,
                   o.pnl, extract(epoch from (now() - o.resolved_at)) / 86400.0 as age_days,
                   extract(dow from s.as_of) * 24 + extract(hour from s.as_of) as how
            from outcomes o
            join signals s on s.id = o.signal_id
            join factor_logs f on f.signal_id = s.id
            where o.pnl is not null and s.composite is not null
            order by s.as_of asc
            """
        )
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    X, y, sw, base = [], [], [], []
    lam = np.log(2.0) / _DECAY_HALFLIFE_DAYS
    n_feat = len(FEATURE_KEYS)
    for r in rows:
        # §11 replay: use the persisted feature vector verbatim when it matches the current layout
        # (so richer features like the §3 stats train once they've been logged); else reconstruct
        # from base columns (new features fall back to their neutral defaults via build()).
        feats = r.get("features")
        if isinstance(feats, list) and len(feats) == n_feat:
            X.append([float(v) for v in feats])
        else:
            price = float(r["price"]) if r["price"] else 0.0
            atr_pct = (abs(float(r["atr"])) / price) if (r["atr"] and price) else 0.0
            raw = {
                "composite": r["composite"], "agreement": r["agreement"], "reward_risk": r["reward_risk"],
                "atr_pct": atr_pct, "win_prob": r["win_prob"], "hour_of_week": r["how"],
                "htf_trend": 0, "is_long": r["label"] in ("Buy", "Strong Buy"), "regime": r["regime"],
                "factors": {k: r[k] for k in ("trend", "momentum", "volatility", "structure",
                                              "flow", "sentiment", "macro", "consensus")},
            }
            X.append(build(raw))
        pnl = float(r["pnl"])
        y.append(1.0 if pnl > 0 else 0.0)
        sw.append(max(abs(pnl), 1e-4) * float(np.exp(-lam * max(0.0, float(r["age_days"] or 0.0)))))
        base.append(float(r["win_prob"]) if r["win_prob"] is not None else 0.5)
    sw = np.array(sw, dtype=float)
    if len(sw) >= 20:                       # winsorize so one outlier trade can't dominate the fit
        sw = np.clip(sw, None, float(np.percentile(sw, 95)))
    return (np.array(X, dtype=float), np.array(y, dtype=float),
            sw, np.array(base, dtype=float))


# --- train + gate -----------------------------------------------------------

def _ts_cv_auc(X: np.ndarray, y: np.ndarray, sw: np.ndarray, k: int = 5, embargo: int = 5) -> float | None:
    """Out-of-sample AUC via expanding-window time-series CV with an embargo gap (no leakage)."""
    n = len(X)
    if n < _MIN_FIT:
        return None
    folds = np.linspace(int(n * 0.4), n, k + 1).astype(int)
    oos_p, oos_y = [], []
    for i in range(k):
        tr_end, te_end = folds[i], folds[i + 1]
        tr_end_emb = max(10, tr_end - embargo)
        if te_end <= tr_end or tr_end_emb < _MIN_FIT // 2:
            continue
        Xtr, ytr, swtr = X[:tr_end_emb], y[:tr_end_emb], sw[:tr_end_emb]
        if len(set(ytr.tolist())) < 2:
            continue
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        w = _fit_logreg((Xtr - mu) / sd, ytr, swtr)
        p = _predict_raw(X[tr_end:te_end], mu, sd, w)
        oos_p.extend(p.tolist()); oos_y.extend(y[tr_end:te_end].tolist())
    if len(oos_y) < 20 or len(set(oos_y)) < 2:
        return None
    return _auc(np.array(oos_p), np.array(oos_y))


def train_and_gate() -> dict:
    if not db.enabled():
        return {"enabled": False}
    try:
        X, y, sw, base = _training()
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "error": f"training query failed: {exc}"}

    n = len(X)
    if n < _MIN_FIT or len(set(y.tolist())) < 2:
        return {"enabled": True, "status": "insufficient_data", "samples": n, "min_fit": _MIN_FIT,
                "is_active": False}

    auc_meta = _ts_cv_auc(X, y, sw)
    auc_base = _auc(base, y)  # the primary calibrated prob on the same rows

    # Fit the final model on all data + isotonic-calibrate its in-sample scores.
    mu, sd = X.mean(0), X.std(0) + 1e-9
    w = _fit_logreg((X - mu) / sd, y, sw)
    p_in = _predict_raw(X, mu, sd, w)
    knots_x, knots_y = _pava(p_in, y)

    is_active = bool(
        n >= _MIN_PROMOTE and auc_meta is not None
        and auc_meta > max(0.55, auc_base + _PROMOTE_AUC_MARGIN)
    )
    model = {
        "features": FEATURE_KEYS, "mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(),
        "knots_x": knots_x.tolist(), "knots_y": knots_y.tolist(),
        "is_active": is_active,
        "metrics": {"n": n, "auc_oos": round(auc_meta, 4) if auc_meta is not None else None,
                    "auc_baseline": round(auc_base, 4), "min_promote": _MIN_PROMOTE},
        "trained_at": time.time(),
    }
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """insert into settings (key, value) values ('meta_model', %s::jsonb)
                   on conflict (key) do update set value = excluded.value, updated_at = now()""",
                (json.dumps(model),),
            )
            conn.commit()
    except Exception:
        pass
    refresh()
    return {"enabled": True, "status": "trained", **model["metrics"], "is_active": is_active,
            "mode": "gating" if is_active else "shadow"}


# --- live prediction --------------------------------------------------------

def _model() -> dict | None:
    global _cache
    now = time.time()
    if _cache and now - _cache[0] < _TTL:
        return _cache[1]
    m = None
    if db.enabled():
        try:
            with db.get_conn() as conn, conn.cursor() as cur:
                cur.execute("select value from settings where key = 'meta_model'")
                row = cur.fetchone()
                if row:
                    m = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except Exception:
            m = None
    _cache = (now, m)
    return m


def refresh() -> None:
    global _cache
    _cache = None


def predict(raw: dict) -> float | None:
    """Calibrated meta P(win) for a live signal, or None if no model is trained yet.

    Returned for SHADOW logging regardless of promotion; callers gate on it only when is_active().
    """
    m = _model()
    if not m or m.get("features") != FEATURE_KEYS:
        return None
    try:
        x = np.array([build(raw)], dtype=float)
        p = _predict_raw(x, np.array(m["mu"]), np.array(m["sd"]), np.array(m["w"]))[0]
        cal = float(np.interp(p, np.array(m["knots_x"]), np.array(m["knots_y"])))
        return float(min(0.98, max(0.02, cal)))
    except Exception:
        return None


def is_active() -> bool:
    m = _model()
    return bool(m and m.get("is_active"))


def status() -> dict:
    m = _model()
    if not m:
        return {"trained": False, "mode": "none"}
    return {"trained": True, "is_active": bool(m.get("is_active")),
            "mode": "gating" if m.get("is_active") else "shadow", "metrics": m.get("metrics", {})}
