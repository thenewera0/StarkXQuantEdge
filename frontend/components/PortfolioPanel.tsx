"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchAllocation, type Allocation, type Sleeve } from "@/lib/api";
import { Card } from "./ui";
import { PieChart, RefreshCw, Wallet, Layers } from "lucide-react";

function usd(n: number): string {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function PortfolioPanel({ equity = 1000 }: { equity?: number }) {
  const [d, setD] = useState<Allocation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setD(await fetchAllocation(equity)); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, [equity]);
  useEffect(() => { load(); }, [load]);

  const sleeves = d?.sleeves ?? [];
  const cashW = d?.cash?.weight ?? 1;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-dim)]">
            <PieChart size={16} className="text-[var(--accent-bright)]" />
          </span>
          <div>
            <h3 className="text-[13.5px] font-semibold text-[var(--ink)]">Portfolio Allocation</h3>
            <p className="text-[11px] text-[var(--ink-muted)]">Risk parity, tilted by proven expectancy</p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Rebalance
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {/* Allocation bar */}
      <div className="mb-1 flex h-3 w-full overflow-hidden rounded-full bg-[var(--surface-raised)]">
        {sleeves.filter((s) => s.weight > 0).map((s) => (
          <div key={s.name} className="h-full bg-[var(--accent)]" style={{ width: `${s.weight * 100}%` }} title={s.name} />
        ))}
        <div className="h-full bg-[var(--surface-hover)]" style={{ width: `${cashW * 100}%` }} title="cash" />
      </div>
      <div className="mb-4 flex justify-between text-[10.5px] tabular-nums text-[var(--ink-muted)]">
        <span>{d?.deployed_pct ?? 0}% deployed</span>
        <span>{Math.round(cashW * 100)}% cash</span>
      </div>

      <div className="space-y-2">
        {sleeves.map((s) => <SleeveRow key={s.name} s={s} />)}

        <div className="surface-raised flex items-center gap-3 px-3 py-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--surface-hover)]">
            <Wallet size={13} className="text-[var(--ink-secondary)]" />
          </span>
          <div className="min-w-0">
            <div className="text-[13px] font-medium text-[var(--ink)]">Cash reserve</div>
            <div className="text-[10.5px] text-[var(--ink-muted)]">{d?.cash?.reason}</div>
          </div>
          <div className="ml-auto text-right">
            <div className="text-base font-bold tabular-nums text-[var(--ink)]">{Math.round(cashW * 100)}%</div>
            <div className="text-[10.5px] tabular-nums text-[var(--ink-muted)]">{usd(d?.cash?.allocation_usd ?? 0)}</div>
          </div>
        </div>
      </div>

      <p className="mt-3 flex items-start gap-1.5 text-[10.5px] leading-relaxed text-[var(--ink-muted)]">
        <Layers size={12} className="mt-0.5 shrink-0" />
        {d?.method ?? "—"}. Each sleeve is sized by its volatility, then scaled by realized expectancy;
        paper sleeves and negative-expectancy sleeves get nothing.
      </p>
    </Card>
  );
}

function SleeveRow({ s }: { s: Sleeve }) {
  const good = s.expectancy_pct > 0 && !s.paper;
  return (
    <div className="surface-raised px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="text-[13px] font-medium capitalize text-[var(--ink)]">{s.name.replace(" (paper)", "")}</span>
        {s.paper && (
          <span className="rounded border border-[var(--warn)]/30 bg-[var(--warn-dim)] px-1.5 py-0.5 text-[9.5px] font-bold text-[var(--warn)]">PAPER</span>
        )}
        <span className={`text-[11px] tabular-nums ${good ? "text-[var(--profit)]" : "text-[var(--loss)]"}`}>
          {s.expectancy_pct > 0 ? "+" : ""}{s.expectancy_pct}%/trade
        </span>
        <span className="text-[10.5px] tabular-nums text-[var(--ink-muted)]">{s.trades} trades</span>
        <span className="ml-auto text-right">
          <span className="text-base font-bold tabular-nums text-[var(--ink)]">{Math.round(s.weight * 100)}%</span>
          <span className="ml-2 text-[10.5px] tabular-nums text-[var(--ink-muted)]">{usd(s.allocation_usd)}</span>
        </span>
      </div>
      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-hover)]">
        <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${Math.max(s.weight * 100, 0)}%` }} />
      </div>
      <p className="mt-1 text-[10.5px] leading-snug text-[var(--ink-muted)]">{s.reason}</p>
    </div>
  );
}
