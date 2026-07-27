"""Portfolio allocation across strategy sleeves — the "fund" layer.

A hedge fund does not put all capital in one strategy; it splits it across sleeves whose returns
are imperfectly correlated, sizes each by RISK rather than by hope, and holds a cash buffer. This
module does the same for the sleeves this system actually runs.

Method — inverse-volatility (risk parity) weighting, tilted by proven edge:

  1. RISK PARITY BASE     w_i proportional to 1/sigma_i, so each sleeve contributes a similar share
                          of portfolio risk. A sleeve twice as volatile gets half the capital. This
                          is the standard, defensible default when you cannot forecast returns well.
  2. EDGE TILT            multiply by a factor derived from each sleeve's REALIZED expectancy. A
                          sleeve with no proven edge (or a paper-only one) cannot take real capital
                          regardless of how calm its volatility looks.
  3. CASH FLOOR           always reserve a cash buffer — it is what lets you survive a drawdown and
                          buy when everything is on sale.
  4. CAPS                 no sleeve may exceed max_weight, so a single strategy failure can never
                          be fatal.

Everything is computed from the sleeve's own realized trade record, so the allocation moves as the
evidence moves rather than as anyone's opinion moves.
"""

from __future__ import annotations

import math

from . import db
from .config import settings


def _sleeve_stats(days: int = 90) -> dict[str, dict]:
    """Realized per-sleeve stats from the trade record: expectancy in R and volatility of R."""
    out: dict[str, dict] = {}
    if not db.enabled():
        return out
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select case when coalesce(s.strategy,'core') = 'flash' then 'flash' else 'core' end sleeve,
                       s.shadow,
                       o.pnl / nullif(abs(s.entry - s.stop) / nullif(abs(s.entry),0), 0) as r,
                       o.pnl as ret
                from outcomes o join signals s on s.id = o.signal_id
                where o.pnl is not null and s.entry is not null and s.stop is not null
                  and s.entry <> 0 and s.stop <> s.entry
                  and o.resolved_at > now() - interval '{int(days)} days'
                """
            )
            rows = cur.fetchall()
    except Exception:
        return out

    buckets: dict[str, list[tuple[float, float]]] = {}
    paper: dict[str, bool] = {}
    for sleeve, shadow, r, ret in rows:
        if r is None or ret is None:
            continue
        key = f"{sleeve} (paper)" if shadow else sleeve
        buckets.setdefault(key, []).append((float(r), float(ret)))
        paper[key] = bool(shadow)

    for key, pairs in buckets.items():
        n = len(pairs)
        rs = [p[0] for p in pairs]
        rets = [p[1] for p in pairs]
        mean_r = sum(rs) / n
        var_r = sum((x - mean_r) ** 2 for x in rs) / n if n > 1 else 0.0
        # Expectancy per trade as a RETURN fraction — this is what actually compounds into dollars.
        # (R-multiples distort here: many small-stop losses can drag mean-R negative while the
        #  dollar P&L is positive, because R divides by each trade's own stop distance.)
        mean_ret = sum(rets) / n
        out[key] = {
            "trades": n,
            "expectancy_r": round(mean_r, 4),
            "expectancy_ret": round(mean_ret, 6),
            "total_return": round(sum(rets), 6),
            "vol_r": round(math.sqrt(var_r), 4),
            "paper": paper[key],
        }
    return out


def allocate(equity: float | None = None, days: int = 90) -> dict:
    """Target capital split across sleeves. Returns weights, $ amounts and the reasoning."""
    equity = equity or settings.account_equity_usd
    stats = _sleeve_stats(days)

    sleeves: list[dict] = []
    for name, s in stats.items():
        vol = max(s["vol_r"], 0.25)                       # floor so a tiny sample can't dominate
        risk_parity = 1.0 / vol                            # inverse-vol base weight

        # Edge tilt: only PROVEN, REAL, POSITIVE-RETURN expectancy earns capital.
        exp_ret = s["expectancy_ret"]
        if s["paper"]:
            tilt, why = 0.0, "paper only — no real capital until it proves an edge"
        elif s["trades"] < settings.portfolio_min_trades:
            tilt, why = 0.35, f"thin record ({s['trades']} trades) — starter allocation"
        elif exp_ret <= 0:
            tilt, why = 0.0, f"negative expectancy ({exp_ret*100:+.2f}%/trade) — stood down"
        else:
            tilt = min(1.5, 0.5 + exp_ret * 100.0)
            why = (f"proven +{exp_ret*100:.2f}%/trade over {s['trades']} trades "
                   f"({s['total_return']*100:+.1f}% total)")

        sleeves.append({
            "name": name, "raw": risk_parity * tilt, "trades": s["trades"],
            "expectancy_r": s["expectancy_r"], "expectancy_pct": round(exp_ret * 100, 3),
            "total_return_pct": round(s["total_return"] * 100, 2),
            "vol_r": s["vol_r"], "paper": s["paper"], "reason": why,
        })

    investable = 1.0 - settings.portfolio_cash_floor
    total_raw = sum(s["raw"] for s in sleeves)

    for s in sleeves:
        w = (s["raw"] / total_raw * investable) if total_raw > 1e-9 else 0.0
        w = min(w, settings.portfolio_max_weight)          # cap: no single point of failure
        s["weight"] = round(w, 4)
        s["allocation_usd"] = round(w * equity, 2)
        s.pop("raw", None)

    allocated = sum(s["weight"] for s in sleeves)
    cash_w = max(settings.portfolio_cash_floor, 1.0 - allocated)

    sleeves.sort(key=lambda x: x["weight"], reverse=True)
    return {
        "equity_usd": equity,
        "window_days": days,
        "method": "inverse-volatility risk parity, tilted by realized expectancy, cash-floored",
        "sleeves": sleeves,
        "cash": {
            "weight": round(cash_w, 4),
            "allocation_usd": round(cash_w * equity, 2),
            "reason": "dry powder — survives drawdowns and buys dislocations",
        },
        "deployed_pct": round(allocated * 100, 2),
    }
