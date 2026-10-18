"""Deep empirical analysis of ALL historical trades to engineer a profitable strategy.

Queries the raw signals + outcomes database, segments by every available dimension
(market, interval, direction, regime, factor scores, conviction, time-of-day, etc.),
and identifies the exact conditions under which the system makes money.

Output: A comprehensive JSON and text report with specific, actionable strategy rules.
"""
import json
import sys
import os
import math
from collections import defaultdict
from datetime import datetime, timezone

# Add parent so we can import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import db


def query_all_trades():
    """Pull every signal+outcome pair with all available metadata."""
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT
                s.id,
                s.symbol,
                coalesce(s.market, 'crypto') as market,
                s.interval,
                s.label,
                s.composite,
                s.confidence,
                s.conviction,
                s.agreement,
                s.entry,
                s.stop,
                s.target,
                s.regime,
                s.shadow,
                s.created_at,
                s.strategy,
                s.win_prob,
                s.ev_r,
                s.meta_p,
                s.reward_risk,
                o.result,
                o.pnl,
                o.mfe,
                o.mae,
                o.bars_held,
                o.resolved_at,
                s.features
            FROM signals s
            JOIN outcomes o ON o.signal_id = s.id
            WHERE o.pnl IS NOT NULL
            ORDER BY s.created_at
        """)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]


def safe_float(v, default=0.0):
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def compute_r(trade):
    """Compute realized R-multiple for a trade."""
    entry = safe_float(trade.get("entry"))
    stop = safe_float(trade.get("stop"))
    pnl = safe_float(trade.get("pnl"))
    if entry == 0 or stop == entry:
        return None
    stop_frac = abs(entry - stop) / abs(entry)
    if stop_frac < 1e-9:
        return None
    # pnl is in percentage points (e.g. 1.5 means +1.5%)
    # Convert to fraction for R calculation
    pnl_frac = pnl / 100.0
    return pnl_frac / stop_frac


def direction_of(trade):
    label = (trade.get("label") or "").lower()
    composite = safe_float(trade.get("composite"))
    if "buy" in label or "long" in label or composite > 0:
        return "long"
    elif "sell" in label or "short" in label or composite < 0:
        return "short"
    return "unknown"


def segment_stats(trades, key_fn, label="segment"):
    """Group trades by key_fn and compute stats for each segment."""
    groups = defaultdict(list)
    for t in trades:
        k = key_fn(t)
        if k is not None:
            groups[k].append(t)
    
    results = []
    for k, group in sorted(groups.items(), key=lambda x: str(x[0])):
        wins = [t for t in group if safe_float(t.get("pnl")) > 0]
        losses = [t for t in group if safe_float(t.get("pnl")) <= 0]
        pnls = [safe_float(t.get("pnl")) for t in group]
        r_vals = [compute_r(t) for t in group]
        r_vals = [r for r in r_vals if r is not None]
        
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p <= 0))
        
        results.append({
            "key": str(k),
            "n": len(group),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(group) * 100, 2) if group else 0,
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(sum(pnls) / len(group), 2) if group else 0,
            "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else float("inf"),
            "avg_win": round(gross_profit / len(wins), 2) if wins else 0,
            "avg_loss": round(-gross_loss / len(losses), 2) if losses else 0,
            "total_r": round(sum(r_vals), 2) if r_vals else 0,
            "avg_r": round(sum(r_vals) / len(r_vals), 4) if r_vals else 0,
            "median_r": round(sorted(r_vals)[len(r_vals)//2], 4) if r_vals else 0,
            "max_win_r": round(max(r_vals), 4) if r_vals else 0,
            "max_loss_r": round(min(r_vals), 4) if r_vals else 0,
        })
    return results


def factor_edge_analysis(trades):
    """For each factor category, find the optimal threshold that maximizes edge."""
    results = {}
    for t in trades:
        factors = t.get("features")
        if not factors or not isinstance(factors, dict):
            continue
        for cat, score in factors.items():
            if cat not in results:
                results[cat] = []
            results[cat].append((safe_float(score), safe_float(t.get("pnl")), compute_r(t)))
    
    analysis = {}
    for cat, data in results.items():
        # Sort by factor score and find optimal threshold
        data.sort(key=lambda x: x[0])
        scores = [d[0] for d in data]
        pnls = [d[1] for d in data]
        r_vals = [d[2] for d in data if d[2] is not None]
        
        # Try different thresholds
        best_threshold = None
        best_edge = -999
        for pct in range(10, 91, 5):
            idx = int(len(scores) * pct / 100)
            if idx == 0 or idx >= len(scores):
                continue
            threshold = scores[idx]
            above = [d for d in data if d[0] >= threshold]
            below = [d for d in data if d[0] < threshold]
            
            above_r = [d[2] for d in above if d[2] is not None]
            below_r = [d[2] for d in below if d[2] is not None]
            
            if above_r and below_r:
                edge_above = sum(above_r) / len(above_r)
                edge_below = sum(below_r) / len(below_r)
                if edge_above > best_edge and len(above_r) >= 15:
                    best_edge = edge_above
                    best_threshold = threshold
        
        # Compute correlation
        if r_vals and len(r_vals) > 10:
            s_scores = [d[0] for d in data if d[2] is not None]
            s_r = [d[2] for d in data if d[2] is not None]
            n = len(s_scores)
            mean_s = sum(s_scores) / n
            mean_r = sum(s_r) / n
            cov = sum((s_scores[i] - mean_s) * (s_r[i] - mean_r) for i in range(n)) / n
            std_s = (sum((x - mean_s)**2 for x in s_scores) / n) ** 0.5
            std_r = (sum((x - mean_r)**2 for x in s_r) / n) ** 0.5
            corr = cov / (std_s * std_r) if std_s > 0 and std_r > 0 else 0
        else:
            corr = 0
        
        analysis[cat] = {
            "n_trades": len(data),
            "mean_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "correlation_with_R": round(corr, 4),
            "best_threshold": round(best_threshold, 2) if best_threshold is not None else None,
            "best_edge_R": round(best_edge, 4) if best_edge > -999 else None,
        }
    
    return analysis


def time_analysis(trades):
    """Analyze performance by hour-of-day and day-of-week."""
    hour_groups = defaultdict(list)
    day_groups = defaultdict(list)
    
    for t in trades:
        created = t.get("created_at")
        if created:
            if hasattr(created, 'hour'):
                hour_groups[created.hour].append(t)
                day_groups[created.strftime("%A")].append(t)
    
    hour_stats = {}
    for h in sorted(hour_groups.keys()):
        group = hour_groups[h]
        pnls = [safe_float(t.get("pnl")) for t in group]
        wins = sum(1 for p in pnls if p > 0)
        hour_stats[f"{h:02d}:00"] = {
            "n": len(group),
            "win_rate": round(wins / len(group) * 100, 1) if group else 0,
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(sum(pnls) / len(group), 2) if group else 0,
        }
    
    day_stats = {}
    for d, group in day_groups.items():
        pnls = [safe_float(t.get("pnl")) for t in group]
        wins = sum(1 for p in pnls if p > 0)
        day_stats[d] = {
            "n": len(group),
            "win_rate": round(wins / len(group) * 100, 1) if group else 0,
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(sum(pnls) / len(group), 2) if group else 0,
        }
    
    return {"by_hour": hour_stats, "by_day": day_stats}


def conviction_band_analysis(trades):
    """Detailed conviction band analysis with optimal conviction ranges."""
    bands = [(0, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 100)]
    results = []
    
    for lo, hi in bands:
        group = [t for t in trades if lo <= abs(safe_float(t.get("conviction", t.get("confidence", 0)))) < hi]
        if not group:
            continue
        pnls = [safe_float(t.get("pnl")) for t in group]
        r_vals = [compute_r(t) for t in group]
        r_vals = [r for r in r_vals if r is not None]
        wins = sum(1 for p in pnls if p > 0)
        
        results.append({
            "band": f"{lo}-{hi}",
            "n": len(group),
            "win_rate": round(wins / len(group) * 100, 1),
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(sum(pnls) / len(group), 2),
            "avg_r": round(sum(r_vals) / len(r_vals), 4) if r_vals else 0,
            "total_r": round(sum(r_vals), 2) if r_vals else 0,
        })
    return results


def bars_held_analysis(trades):
    """Analyze P&L by how long trades are held."""
    bands = [(0, 2), (2, 4), (4, 8), (8, 12), (12, 20), (20, 50)]
    results = []
    
    for lo, hi in bands:
        group = [t for t in trades if t.get("bars_held") is not None and lo <= int(t["bars_held"]) < hi]
        if not group:
            continue
        pnls = [safe_float(t.get("pnl")) for t in group]
        r_vals = [compute_r(t) for t in group]
        r_vals = [r for r in r_vals if r is not None]
        wins = sum(1 for p in pnls if p > 0)
        
        results.append({
            "bars_held": f"{lo}-{hi}",
            "n": len(group),
            "win_rate": round(wins / len(group) * 100, 1),
            "avg_pnl": round(sum(pnls) / len(group), 2) if group else 0,
            "avg_r": round(sum(r_vals) / len(r_vals), 4) if r_vals else 0,
        })
    return results


def mfe_mae_analysis(trades):
    """Analyze Maximum Favorable/Adverse Excursion patterns."""
    mfe_vals = []
    mae_vals = []
    for t in trades:
        mfe = safe_float(t.get("mfe"))
        mae = safe_float(t.get("mae"))
        pnl = safe_float(t.get("pnl"))
        r = compute_r(t)
        if mfe != 0 or mae != 0:
            mfe_vals.append({"mfe": mfe, "mae": mae, "pnl": pnl, "r": r,
                             "result": t.get("result"), "direction": direction_of(t)})
    
    # What fraction of MFE was captured?
    captured = []
    for v in mfe_vals:
        if v["mfe"] > 0 and v["r"] is not None:
            captured.append(v["pnl"] / (v["mfe"] * 100) if v["mfe"] > 0 else 0)
    
    # Winning trades: how far did MAE go before recovering?
    winners = [v for v in mfe_vals if v["pnl"] > 0]
    losers = [v for v in mfe_vals if v["pnl"] <= 0]
    
    return {
        "n_with_excursion": len(mfe_vals),
        "avg_mfe_pct": round(sum(v["mfe"] for v in mfe_vals) / len(mfe_vals) * 100, 3) if mfe_vals else 0,
        "avg_mae_pct": round(sum(v["mae"] for v in mfe_vals) / len(mfe_vals) * 100, 3) if mfe_vals else 0,
        "winners_avg_mae_pct": round(sum(v["mae"] for v in winners) / len(winners) * 100, 3) if winners else 0,
        "losers_avg_mae_pct": round(sum(v["mae"] for v in losers) / len(losers) * 100, 3) if losers else 0,
        "avg_capture_ratio": round(sum(captured) / len(captured), 3) if captured else 0,
    }


def strategy_cross_analysis(trades):
    """Cross-tabulate market x direction x interval x regime."""
    combos = defaultdict(list)
    for t in trades:
        market = (t.get("market") or "crypto").lower()
        direction = direction_of(t)
        interval = t.get("interval", "4h")
        regime = (t.get("regime") or "unknown").lower()
        strategy = (t.get("strategy") or "core").lower()
        
        key = f"{strategy}|{market}|{direction}|{interval}|{regime}"
        combos[key].append(t)
    
    results = []
    for key, group in sorted(combos.items()):
        parts = key.split("|")
        pnls = [safe_float(t.get("pnl")) for t in group]
        r_vals = [compute_r(t) for t in group]
        r_vals = [r for r in r_vals if r is not None]
        wins = sum(1 for p in pnls if p > 0)
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p <= 0))
        
        results.append({
            "strategy": parts[0],
            "market": parts[1],
            "direction": parts[2],
            "interval": parts[3],
            "regime": parts[4],
            "n": len(group),
            "win_rate": round(wins / len(group) * 100, 1) if group else 0,
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(sum(pnls) / len(group), 2) if group else 0,
            "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else float("inf"),
            "total_r": round(sum(r_vals), 2) if r_vals else 0,
            "avg_r": round(sum(r_vals) / len(r_vals), 4) if r_vals else 0,
        })
    
    # Sort by total_r descending
    results.sort(key=lambda x: x["total_r"], reverse=True)
    return results


def symbol_analysis(trades):
    """Performance by individual trading symbol."""
    results = segment_stats(trades, lambda t: t.get("symbol", "?"), "symbol")
    results.sort(key=lambda x: x["total_r"], reverse=True)
    return results


def result_type_analysis(trades):
    """Performance by outcome result type (target, stop, max_hold, partial, etc.)."""
    return segment_stats(trades, lambda t: t.get("result", "?"), "result")


def main():
    print("=" * 80)
    print("STARKX QUANTEDGE: DEEP EMPIRICAL TRADE ANALYSIS")
    print(f"Analysis Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)
    
    trades = query_all_trades()
    print(f"\nTotal trades loaded: {len(trades)}")
    
    # Filter out shadow trades for core analysis
    live_trades = [t for t in trades if not t.get("shadow")]
    shadow_trades = [t for t in trades if t.get("shadow")]
    print(f"Live (non-shadow) trades: {len(live_trades)}")
    print(f"Shadow trades: {len(shadow_trades)}")
    
    report = {
        "total_trades": len(trades),
        "live_trades": len(live_trades),
        "shadow_trades": len(shadow_trades),
    }
    
    # ========== CORE SEGMENTATION ==========
    print("\n" + "=" * 60)
    print("1. BY STRATEGY")
    print("=" * 60)
    strat_stats = segment_stats(trades, lambda t: (t.get("strategy") or "core").lower())
    for s in strat_stats:
        print(f"  {s['key']:12s} | n={s['n']:4d} | WR={s['win_rate']:5.1f}% | PF={s['profit_factor']:6.3f} | "
              f"PnL=${s['total_pnl']:+9.2f} | R={s['total_r']:+8.2f} | AvgR={s['avg_r']:+.4f}")
    report["by_strategy"] = strat_stats
    
    print("\n" + "=" * 60)
    print("2. BY MARKET")
    print("=" * 60)
    mkt_stats = segment_stats(trades, lambda t: (t.get("market") or "crypto").lower())
    for s in mkt_stats:
        print(f"  {s['key']:12s} | n={s['n']:4d} | WR={s['win_rate']:5.1f}% | PF={s['profit_factor']:6.3f} | "
              f"PnL=${s['total_pnl']:+9.2f} | R={s['total_r']:+8.2f} | AvgR={s['avg_r']:+.4f}")
    report["by_market"] = mkt_stats
    
    print("\n" + "=" * 60)
    print("3. BY MARKET x DIRECTION")
    print("=" * 60)
    md_stats = segment_stats(trades, lambda t: f"{(t.get('market') or 'crypto').lower()}_{direction_of(t)}")
    for s in md_stats:
        print(f"  {s['key']:20s} | n={s['n']:4d} | WR={s['win_rate']:5.1f}% | PF={s['profit_factor']:6.3f} | "
              f"PnL=${s['total_pnl']:+9.2f} | R={s['total_r']:+8.2f} | AvgR={s['avg_r']:+.4f}")
    report["by_market_direction"] = md_stats
    
    print("\n" + "=" * 60)
    print("4. BY INTERVAL")
    print("=" * 60)
    int_stats = segment_stats(trades, lambda t: t.get("interval", "?"))
    for s in int_stats:
        print(f"  {s['key']:8s} | n={s['n']:4d} | WR={s['win_rate']:5.1f}% | PF={s['profit_factor']:6.3f} | "
              f"PnL=${s['total_pnl']:+9.2f} | R={s['total_r']:+8.2f}")
    report["by_interval"] = int_stats
    
    print("\n" + "=" * 60)
    print("5. BY REGIME")
    print("=" * 60)
    reg_stats = segment_stats(trades, lambda t: (t.get("regime") or "unknown").lower())
    for s in reg_stats:
        print(f"  {s['key']:18s} | n={s['n']:4d} | WR={s['win_rate']:5.1f}% | PF={s['profit_factor']:6.3f} | "
              f"PnL=${s['total_pnl']:+9.2f} | R={s['total_r']:+8.2f}")
    report["by_regime"] = reg_stats
    
    print("\n" + "=" * 60)
    print("6. BY RESULT TYPE")
    print("=" * 60)
    result_stats = result_type_analysis(trades)
    for s in result_stats:
        print(f"  {s['key']:12s} | n={s['n']:4d} | WR={s['win_rate']:5.1f}% | PnL=${s['total_pnl']:+9.2f}")
    report["by_result"] = result_stats
    
    print("\n" + "=" * 60)
    print("7. CONVICTION BAND ANALYSIS")
    print("=" * 60)
    conv_stats = conviction_band_analysis(trades)
    for s in conv_stats:
        print(f"  {s['band']:8s} | n={s['n']:4d} | WR={s['win_rate']:5.1f}% | "
              f"PnL=${s['total_pnl']:+9.2f} | AvgR={s['avg_r']:+.4f} | TotalR={s['total_r']:+.2f}")
    report["conviction_bands"] = conv_stats
    
    print("\n" + "=" * 60)
    print("8. BARS HELD ANALYSIS")
    print("=" * 60)
    bars_stats = bars_held_analysis(trades)
    for s in bars_stats:
        print(f"  {s['bars_held']:8s} bars | n={s['n']:4d} | WR={s['win_rate']:5.1f}% | "
              f"AvgPnL=${s['avg_pnl']:+.2f} | AvgR={s['avg_r']:+.4f}")
    report["bars_held"] = bars_stats
    
    print("\n" + "=" * 60)
    print("9. FACTOR EDGE ANALYSIS")
    print("=" * 60)
    factor_stats = factor_edge_analysis(trades)
    for cat, info in sorted(factor_stats.items()):
        print(f"  {cat:14s} | n={info['n_trades']:4d} | Corr(R)={info['correlation_with_R']:+.4f} | "
              f"BestThresh={info['best_threshold']} | BestEdge={info['best_edge_R']}")
    report["factor_analysis"] = factor_stats
    
    print("\n" + "=" * 60)
    print("10. CROSS-TABULATION: STRATEGY x MARKET x DIRECTION x INTERVAL x REGIME")
    print("=" * 60)
    cross_stats = strategy_cross_analysis(trades)
    # Show top 15 and bottom 10
    print("  --- TOP 15 by Total R ---")
    for s in cross_stats[:15]:
        print(f"  {s['strategy']:6s} {s['market']:8s} {s['direction']:5s} {s['interval']:4s} {s['regime']:14s} | "
              f"n={s['n']:3d} | WR={s['win_rate']:5.1f}% | PF={s['profit_factor']:6.3f} | "
              f"R={s['total_r']:+7.2f} | AvgR={s['avg_r']:+.4f}")
    print("  --- BOTTOM 10 by Total R ---")
    for s in cross_stats[-10:]:
        print(f"  {s['strategy']:6s} {s['market']:8s} {s['direction']:5s} {s['interval']:4s} {s['regime']:14s} | "
              f"n={s['n']:3d} | WR={s['win_rate']:5.1f}% | PF={s['profit_factor']:6.3f} | "
              f"R={s['total_r']:+7.2f} | AvgR={s['avg_r']:+.4f}")
    report["cross_tabulation"] = cross_stats
    
    print("\n" + "=" * 60)
    print("11. SYMBOL PERFORMANCE (Top 10 / Bottom 10)")
    print("=" * 60)
    sym_stats = symbol_analysis(trades)
    print("  --- TOP 10 ---")
    for s in sym_stats[:10]:
        print(f"  {s['key']:12s} | n={s['n']:3d} | WR={s['win_rate']:5.1f}% | PnL=${s['total_pnl']:+8.2f} | R={s['total_r']:+7.2f}")
    print("  --- BOTTOM 10 ---")
    for s in sym_stats[-10:]:
        print(f"  {s['key']:12s} | n={s['n']:3d} | WR={s['win_rate']:5.1f}% | PnL=${s['total_pnl']:+8.2f} | R={s['total_r']:+7.2f}")
    report["by_symbol"] = sym_stats
    
    print("\n" + "=" * 60)
    print("12. MFE/MAE EXCURSION ANALYSIS")
    print("=" * 60)
    mfe_stats = mfe_mae_analysis(trades)
    for k, v in mfe_stats.items():
        print(f"  {k}: {v}")
    report["mfe_mae"] = mfe_stats
    
    print("\n" + "=" * 60)
    print("13. TIME OF DAY / DAY OF WEEK")
    print("=" * 60)
    time_stats = time_analysis(trades)
    print("  By Hour (UTC):")
    for h, info in sorted(time_stats["by_hour"].items()):
        sign = "+" if info["avg_pnl"] > 0 else "-" if info["avg_pnl"] < 0 else " "
        print(f"    {h} | n={info['n']:3d} | WR={info['win_rate']:5.1f}% | AvgPnL=${info['avg_pnl']:+6.2f} {sign}")
    print("  By Day:")
    for d, info in time_stats["by_day"].items():
        print(f"    {d:10s} | n={info['n']:3d} | WR={info['win_rate']:5.1f}% | AvgPnL=${info['avg_pnl']:+6.2f}")
    report["time_analysis"] = time_stats
    
    # ========== FLASH-SPECIFIC ANALYSIS ==========
    print("\n" + "=" * 60)
    print("14. FLASH BOT DEEP DIVE")
    print("=" * 60)
    flash_trades = [t for t in trades if (t.get("strategy") or "").lower() == "flash"]
    if flash_trades:
        flash_by_symbol = segment_stats(flash_trades, lambda t: t.get("symbol", "?"))
        print("  Flash by symbol:")
        for s in sorted(flash_by_symbol, key=lambda x: x["total_r"], reverse=True)[:10]:
            print(f"    {s['key']:12s} | n={s['n']:3d} | WR={s['win_rate']:5.1f}% | "
                  f"PnL=${s['total_pnl']:+8.2f} | AvgR={s['avg_r']:+.4f}")
        
        flash_by_interval = segment_stats(flash_trades, lambda t: t.get("interval", "?"))
        print("  Flash by interval:")
        for s in flash_by_interval:
            print(f"    {s['key']:8s} | n={s['n']:3d} | WR={s['win_rate']:5.1f}% | "
                  f"PnL=${s['total_pnl']:+8.2f} | PF={s['profit_factor']:6.3f}")
        report["flash_detail"] = {"by_symbol": flash_by_symbol, "by_interval": flash_by_interval}
    else:
        print("  No flash trades found.")
        report["flash_detail"] = None
    
    # Save full report
    output_path = os.path.join(os.path.dirname(__file__), "..", "docs", "TRADE_ANALYSIS_RAW.json")
    
    # Convert non-serializable types
    def _default(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj)):
            return str(obj)
        return str(obj)
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=_default)
    print(f"\nFull report saved to: {output_path}")
    
    # ========== STRATEGY SYNTHESIS ==========
    print("\n" + "=" * 80)
    print("STRATEGY SYNTHESIS: DATA-DRIVEN RULES")
    print("=" * 80)
    
    # Identify profitable segments
    profitable = [s for s in cross_stats if s["n"] >= 8 and s["avg_r"] > 0.1]
    unprofitable = [s for s in cross_stats if s["n"] >= 8 and s["avg_r"] < -0.1]
    
    print("\n  PROFITABLE SEGMENTS (n>=8, avgR > +0.10):")
    for s in profitable:
        print(f"    ✅ {s['strategy']} {s['market']} {s['direction']} {s['interval']} {s['regime']} "
              f"| n={s['n']} WR={s['win_rate']}% PF={s['profit_factor']} AvgR={s['avg_r']:+.4f}")
    
    print("\n  UNPROFITABLE SEGMENTS (n>=8, avgR < -0.10):")
    for s in unprofitable:
        print(f"    ❌ {s['strategy']} {s['market']} {s['direction']} {s['interval']} {s['regime']} "
              f"| n={s['n']} WR={s['win_rate']}% PF={s['profit_factor']} AvgR={s['avg_r']:+.4f}")


if __name__ == "__main__":
    main()
