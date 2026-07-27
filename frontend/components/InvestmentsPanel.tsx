"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchInvestments, type InvestScreen, type InvestAsset } from "@/lib/api";
import { Card } from "./ui";
import { Landmark, RefreshCw, TrendingUp, TrendingDown, Info } from "lucide-react";

const TIER: Record<string, { label: string; cls: string }> = {
  core: { label: "CORE", cls: "bg-[var(--profit-dim)] text-[var(--profit)] border-[var(--profit)]/30" },
  satellite: { label: "SATELLITE", cls: "bg-[var(--accent-dim)] text-[var(--accent-bright)] border-[var(--accent)]/30" },
  watch: { label: "WATCH", cls: "bg-[var(--warn-dim)] text-[var(--warn)] border-[var(--warn)]/30" },
  avoid: { label: "AVOID", cls: "bg-[var(--loss-dim)] text-[var(--loss)] border-[var(--loss)]/30" },
};

export function InvestmentsPanel() {
  const [d, setD] = useState<InvestScreen | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setD(await fetchInvestments()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const assets = d?.assets ?? [];
  const investable = assets.filter((a) => a.tier === "core" || a.tier === "satellite");

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-dim)]">
            <Landmark size={16} className="text-[var(--accent-bright)]" />
          </span>
          <div>
            <h3 className="text-[13.5px] font-semibold text-[var(--ink)]">Long-term Investments</h3>
            <p className="text-[11px] text-[var(--ink-muted)]">Momentum 12-1 · trend quality · Sharpe · drawdown</p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Rescreen
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      <div className="mb-4 grid grid-cols-4 gap-2.5">
        {(["core", "satellite", "watch", "avoid"] as const).map((t) => (
          <div key={t} className="surface-raised px-3 py-2.5">
            <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">{t}</div>
            <div className="mt-0.5 text-xl font-bold tabular-nums text-[var(--ink)]">{d?.tiers?.[t] ?? 0}</div>
          </div>
        ))}
      </div>

      {investable.length === 0 && assets.length > 0 && (
        <div className="mb-3 flex items-start gap-2 rounded-xl border border-[var(--warn)]/25 bg-[var(--warn-dim)] p-3">
          <Info size={15} className="mt-0.5 shrink-0 text-[var(--warn)]" />
          <p className="text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
            Nothing currently qualifies for a long-term allocation — every asset screened is below its
            200-day average with negative 12-month momentum. That is a bear market reading, and the
            honest answer is to wait rather than average into falling trends.
          </p>
        </div>
      )}

      <div className="space-y-2">
        {assets.slice(0, 12).map((a) => <AssetRow key={a.symbol} a={a} />)}
      </div>

      <p className="mt-3 text-[10.5px] leading-relaxed text-[var(--ink-muted)]">
        {d?.horizon ?? "Hold-and-review shortlist, not a trade signal."} No stops or targets — this is
        an allocation view, deliberately separate from the trading engine.
      </p>
    </Card>
  );
}

function AssetRow({ a }: { a: InvestAsset }) {
  const t = TIER[a.tier] ?? TIER.watch;
  const up = a.momentum_12_1 >= 0;
  return (
    <div className="surface-raised px-3 py-2.5 transition-colors hover:bg-[var(--surface-hover)]">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="font-semibold text-[var(--ink)]">{a.symbol.replace("USDT", "")}</span>
        <span className={`rounded border px-1.5 py-0.5 text-[9.5px] font-bold tracking-wide ${t.cls}`}>{t.label}</span>
        <span className={`inline-flex items-center gap-0.5 text-[11px] tabular-nums ${up ? "text-[var(--profit)]" : "text-[var(--loss)]"}`}>
          {up ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {(a.momentum_12_1 * 100).toFixed(0)}%
        </span>
        <span className="ml-auto flex items-center gap-2">
          <span className="text-[10px] text-[var(--ink-muted)]">score</span>
          <span className="text-base font-bold tabular-nums text-[var(--ink)]">{a.score}</span>
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-0.5 text-[10.5px] tabular-nums text-[var(--ink-muted)]">
        <span>Sharpe <span className={a.sharpe > 0 ? "text-[var(--profit)]" : "text-[var(--loss)]"}>{a.sharpe.toFixed(2)}</span></span>
        <span>vol {(a.ann_vol * 100).toFixed(0)}%</span>
        <span>from high <span className="text-[var(--ink-secondary)]">{(a.drawdown_from_high * 100).toFixed(0)}%</span></span>
        <span>{a.above_ma200 ? <span className="text-[var(--profit)]">above 200d</span> : <span className="text-[var(--loss)]">below 200d</span>}</span>
      </div>
      {a.notes.length > 0 && (
        <p className="mt-1 text-[10.5px] leading-snug text-[var(--ink-muted)]">{a.notes.slice(0, 2).join(" · ")}</p>
      )}
    </div>
  );
}
