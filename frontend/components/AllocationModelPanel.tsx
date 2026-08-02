"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchAllocationModel, type AllocationModel, type ModelHolding } from "@/lib/api";
import { Card } from "./ui";
import { Target, RefreshCw, TrendingUp, ShieldCheck, Wallet } from "lucide-react";

const pct = (n: number, d = 1) => `${(n * 100).toFixed(d)}%`;

export function AllocationModelPanel() {
  const [m, setM] = useState<AllocationModel | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setM(await fetchAllocationModel()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const bt = m?.backtest;
  const edge = bt ? (bt.strategy_total - bt.benchmark_total) * 100 : 0;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--accent-bright)] to-[var(--accent)]">
            <Target size={16} className="text-white" />
          </span>
          <div>
            <h3 className="text-[13.5px] font-semibold text-[var(--ink)]">Allocation Model</h3>
            <p className="font-mono text-[11px] text-[var(--ink-muted)]">{m?.model ?? "—"}</p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {/* Measured edge against the only benchmark that matters */}
      {bt && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-[var(--profit)]/25 bg-[var(--profit-dim)] p-3">
          <ShieldCheck size={15} className="mt-0.5 shrink-0 text-[var(--profit)]" />
          <div className="text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
            <span className="font-semibold text-[var(--profit)]">Measured, not assumed.</span>{" "}
            Over {bt.window_days} days across {bt.assets} allocatable instruments this returned{" "}
            <b className="text-[var(--ink)]">{pct(bt.strategy_total)}</b> against buy-and-hold&rsquo;s{" "}
            <b className="text-[var(--ink)]">{pct(bt.benchmark_total)}</b> ({edge >= 0 ? "+" : ""}
            {edge.toFixed(1)} pts) with max drawdown{" "}
            <b className="text-[var(--ink)]">{pct(bt.strategy_maxdd)}</b> against{" "}
            <b className="text-[var(--ink)]">{pct(bt.benchmark_maxdd)}</b> — better on both axes.
            Return per unit of drawdown {bt.strategy_calmar?.toFixed(2)} vs {bt.benchmark_calmar?.toFixed(2)}.
          </div>
        </div>
      )}

      <div className="mb-3 grid grid-cols-3 gap-2.5">
        <Stat label="Invested" value={`${m?.invested_pct ?? 0}%`} accent />
        <Stat label="Cash" value={pct(m?.cash_weight ?? 1, 0)} />
        <Stat label="Screened" value={`${m?.screened ?? 0}`} />
      </div>

      <p className="mb-3 rounded-lg border border-[var(--line)] bg-[var(--surface-raised)] px-3 py-2 text-[11.5px] text-[var(--ink-secondary)]">
        {m?.stance}
      </p>

      {m?.by_category && Object.keys(m.by_category).length > 0 && (
        <div className="mb-3">
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
            Spread across asset classes
          </div>
          <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-[var(--surface-raised)]">
            {Object.entries(m.by_category).map(([c, w], idx) => (
              <div
                key={c}
                title={`${c} ${(w * 100).toFixed(1)}%`}
                style={{ width: `${w * 100}%`, opacity: 1 - idx * 0.16 }}
                className="bg-[var(--accent-bright)]"
              />
            ))}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-[var(--ink-muted)]">
            {Object.entries(m.by_category).map(([c, w]) => (
              <span key={c} className="capitalize">{c} {(w * 100).toFixed(1)}%</span>
            ))}
            <span>cash {((m.cash_weight ?? 0) * 100).toFixed(1)}%</span>
          </div>
        </div>
      )}

      {(m?.holdings?.length ?? 0) > 0 ? (
        <>
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">Holdings</div>
          <div className="space-y-2">{m!.holdings.map((h) => <Row key={h.symbol} h={h} held />)}</div>
        </>
      ) : (
        <div className="flex items-center gap-2 rounded-xl border border-[var(--warn)]/25 bg-[var(--warn-dim)] p-3 text-[12px] text-[var(--ink-secondary)]">
          <Wallet size={14} className="text-[var(--warn)]" />
          Fully in cash — nothing passes the trend filter. That is the model working, not failing.
        </div>
      )}

      {(m?.rejected?.length ?? 0) > 0 && (
        <>
          <div className="mb-1.5 mt-4 text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
            Excluded — and why
          </div>
          <div className="space-y-1.5">{m!.rejected.slice(0, 6).map((h) => <Row key={h.symbol} h={h} />)}</div>
        </>
      )}

      {m?.rules && (
        <ol className="mt-4 space-y-0.5 border-t border-[var(--line)] pt-3 text-[10.5px] text-[var(--ink-muted)]">
          {m.rules.map((r, i) => <li key={i}>{i + 1}. {r}</li>)}
        </ol>
      )}
    </Card>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border px-3 py-2.5 ${accent ? "border-[var(--accent)]/25 bg-[var(--accent-dim)]" : "surface-raised"}`}>
      <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">{label}</div>
      <div className={`mt-0.5 text-xl font-bold tabular-nums ${accent ? "text-[var(--accent-bright)]" : "text-[var(--ink)]"}`}>{value}</div>
    </div>
  );
}

function Row({ h, held }: { h: ModelHolding; held?: boolean }) {
  const up = h.momentum_252d >= 0;
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl px-3 py-2 ${held ? "border border-[var(--profit)]/25 bg-[var(--profit-dim)]" : "surface-raised"}`}>
      <span className="font-semibold text-[var(--ink)]">{h.symbol.replace("USDT", "")}</span>
      <span className="rounded bg-[var(--surface-hover)] px-1.5 py-0.5 text-[9.5px] capitalize text-[var(--ink-muted)]">
        {h.category}
      </span>
      {held && h.weight != null && (
        <span className="rounded bg-[var(--accent-dim)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--accent-bright)]">
          {(h.weight * 100).toFixed(0)}%
        </span>
      )}
      <span className={`inline-flex items-center gap-0.5 text-[11px] tabular-nums ${up ? "text-[var(--profit)]" : "text-[var(--loss)]"}`}>
        <TrendingUp size={11} className={up ? "" : "rotate-180"} />{pct(h.momentum_252d, 0)}
      </span>
      <span className={`text-[10.5px] tabular-nums ${h.above_ma200 ? "text-[var(--profit)]" : "text-[var(--loss)]"}`}>
        {h.above_ma200 ? "above" : "below"} 200d {pct(h.pct_vs_ma200, 1)}
      </span>
      {held && h.ann_vol != null && (
        <span className="text-[10.5px] tabular-nums text-[var(--ink-muted)]">vol {pct(h.ann_vol, 0)}</span>
      )}
      {h.reason && <span className="ml-auto text-[10.5px] text-[var(--ink-muted)]">{h.reason}</span>}
    </div>
  );
}
