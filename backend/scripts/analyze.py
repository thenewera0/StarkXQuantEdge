"""Deep P&L / trade analysis to find accuracy improvements. Read-only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app import db

FACTORS = ["trend", "momentum", "volatility", "structure", "flow", "sentiment", "macro", "consensus"]


def load() -> pd.DataFrame:
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            select s.symbol, s.market, s.interval, s.label, coalesce(s.regime,'?') regime,
                   s.tier, s.confidence, s.conviction, s.reward_risk,
                   o.result, o.pnl, o.mfe, o.mae, o.bars_held,
                   {', '.join('f.'+c for c in FACTORS)}
            from outcomes o
            join signals s on s.id = o.signal_id
            left join factor_logs f on f.signal_id = o.signal_id
            where o.pnl is not null
            """
        )
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    df = pd.DataFrame(rows)
    for c in ["confidence", "conviction", "reward_risk", "pnl", "mfe", "mae"] + FACTORS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["dir"] = np.where(df["label"].isin(["Buy", "Strong Buy"]), "long", "short")
    df["win"] = df["pnl"] > 0
    df["pnl_pct"] = df["pnl"] * 100
    return df


def stats(g: pd.DataFrame) -> str:
    n = len(g)
    if n == 0:
        return "n=0"
    w = g["win"].sum()
    wins = g.loc[g["win"], "pnl"]
    losses = g.loc[~g["win"], "pnl"]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
    exp = g["pnl"].mean() * 100
    return (f"n={n:>3} hit={w/n:5.1%} exp={exp:+.3f}% pf={pf:4.2f} "
            f"avgW={wins.mean()*100:+.2f}% avgL={losses.mean()*100:+.2f}% pnl${g['pnl'].sum()*1000:+.0f}")


def main() -> None:
    df = load()
    print(f"\n===== OVERALL ({len(df)} closed trades) =====")
    print(" ", stats(df))
    print("  results:", df["result"].value_counts().to_dict())

    print("\n===== BY DIRECTION =====")
    for d, g in df.groupby("dir"):
        print(f"  {d:6}", stats(g))

    print("\n===== BY REGIME =====")
    for r, g in sorted(df.groupby("regime"), key=lambda x: -x[1]["pnl"].sum()):
        print(f"  {r:<13}", stats(g))

    print("\n===== BY TIER =====")
    for t, g in df.groupby(df["tier"].fillna("(none)")):
        print(f"  {t:<9}", stats(g))

    print("\n===== BY INTERVAL =====")
    for iv, g in df.groupby("interval"):
        print(f"  {iv:<4}", stats(g))

    print("\n===== BY SYMBOL (worst first) =====")
    for s, g in sorted(df.groupby("symbol"), key=lambda x: x[1]["pnl"].sum()):
        print(f"  {s:<9}", stats(g))

    print("\n===== CONFIDENCE / CONVICTION buckets =====")
    df["conf_b"] = pd.cut(df["confidence"], [0, 55, 65, 75, 100])
    for b, g in df.groupby("conf_b", observed=True):
        print(f"  conf {str(b):<10}", stats(g))

    print("\n===== FACTOR DISCRIMINATION (directional: + = aligned with trade) =====")
    print("  factor        win_avg  loss_avg  spread   (higher spread = more predictive)")
    for f in FACTORS:
        dirf = np.where(df["dir"] == "long", df[f], -df[f])
        s = pd.Series(dirf, index=df.index)
        wa = s[df["win"]].mean()
        la = s[~df["win"]].mean()
        if pd.notna(wa) and pd.notna(la):
            print(f"  {f:<12} {wa:8.1f} {la:8.1f}  {wa-la:+7.1f}")

    print("\n===== MFE / MAE (stop/target sizing) =====")
    for lbl, g in [("winners", df[df["win"]]), ("losers", df[~df["win"]])]:
        print(f"  {lbl:8} avg MFE {g['mfe'].mean()*100:+.2f}%  avg MAE {g['mae'].mean()*100:+.2f}%  avg bars {g['bars_held'].mean():.1f}")
    stopped = df[df["result"] == "stop"]
    print(f"  of STOPPED trades: avg MFE (ran in favor before stop) = {stopped['mfe'].mean()*100:+.2f}% "
          f"| {100*(stopped['mfe']>0.015).mean():.0f}% ran >1.5% in favor first")


if __name__ == "__main__":
    main()
