"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchRebalanceModel, type RebalanceModel, type RebalHolding } from "@/lib/api";
import { Card } from "./ui";
import { Scale, RefreshCw, ArrowDown, ArrowUp, Minus, ShieldCheck } from "lucide-react";

const pct = (n: number, d = 1) => `${(n * 100).toFixed(d)}%`;

const CLASS_LABEL: Record<string, string> = {
  crypto: "Crypto", forex: "Forex", commodities: "Commodities",
  indices: "Indices", rates: "Rates",
};

export function RebalancePanel() {
  const [m, setM] = useState<RebalanceModel | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setM(await fetchRebalanceModel()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const bt = m?.backtest;
  const todo = [...(m?.rebalance.trim ?? []), ...(m?.rebalance.add ?? [])];

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--profit)] to-[var(--accent)]">
            <Scale size={16} className="text-white" />
          </span>
          <div>
            <h3 className="text-[13.5px] font-semibold text-[var(--ink)]">Rebalancing Engine</h3>
            <p className="text-[11px] text-[var(--ink-muted)]">{m?.model ?? "—"}</p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {bt && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-[var(--profit)]/25 bg-[var(--profit-dim)] p-3">
          <ShieldCheck size={15} className="mt-0.5 shrink-0 text-[var(--profit)]" />
          <div className="text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
            <span className="font-semibold text-[var(--profit)]">This forecasts nothing.</span>{" "}
            Tested on {bt.baskets_tested} <b>randomly drawn</b> baskets over {bt.window_days} days:
            median return <b className="text-[var(--ink)]">{pct(bt.median_total)}</b> with a median
            drawdown of <b className="text-[var(--ink)]">{pct(bt.median_maxdd)}</b>, Sharpe{" "}
            <b className="text-[var(--ink)]">{bt.median_sharpe.toFixed(2)}</b>. {bt.beat_benchmark} beat
            buy-and-hold ({pct(bt.benchmark_total)} / {pct(bt.benchmark_maxdd)}) on <i>both</i> return and
            drawdown. Surviving random name selection is what makes it an edge and not a backtest.
          </div>
        </div>
      )}

      {bt && (
        <div className="mb-4 rounded-xl border border-[var(--accent)]/25 bg-[var(--accent-dim)] p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-bright)]">
            The rebalancing IS the edge
          </div>
          <p className="mt-1 text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
            Same basket, same window: rebalanced it returned{" "}
            <b className="text-[var(--profit)]">{pct(bt.median_total)}</b>; left alone it returned{" "}
            <b className="text-[var(--loss)]">{pct(bt.no_rebalance_total)}</b>. Two thirds of the return
            comes from periodically selling what rose to buy what fell — not from choosing well.
          </p>
        </div>
      )}

      {/* What to do right now */}
      <div className="mb-4">
        <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
          Action now · drift band {m?.rebalance.band_pct ?? 5}%
        </div>
        {todo.length === 0 ? (
          <div className="flex items-center gap-2 rounded-xl surface-raised px-3 py-2.5 text-[12px] text-[var(--ink-secondary)]">
            <Minus size={14} className="text-[var(--ink-muted)]" />
            {m?.rebalance.note ?? "—"}
          </div>
        ) : (
          <div className="space-y-1.5">
            {(m?.rebalance.trim ?? []).map((s) => (
              <Action key={`t-${s}`} symbol={s} kind="trim" />
            ))}
            {(m?.rebalance.add ?? []).map((s) => (
              <Action key={`a-${s}`} symbol={s} kind="add" />
            ))}
          </div>
        )}
      </div>

      {/* Class balance */}
      {m?.by_category && (
        <div className="mb-4">
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
            Equal risk per asset class
          </div>
          <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-[var(--surface-raised)]">
            {Object.entries(m.by_category).map(([c, w], i) => (
              <div key={c} title={`${c} ${pct(w)}`} style={{ width: `${w * 100}%`, opacity: 1 - i * 0.13 }}
                   className="bg-[var(--accent-bright)]" />
            ))}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-[var(--ink-muted)]">
            {Object.entries(m.by_category).map(([c, w]) => (
              <span key={c}>{CLASS_LABEL[c] ?? c} {pct(w, 0)}</span>
            ))}
          </div>
        </div>
      )}

      {/* Holdings, grouped */}
      <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
        Target book · {m?.screened ?? 0} names
      </div>
      <div className="max-h-[340px] space-y-1 overflow-y-auto pr-1">
        {(m?.holdings ?? []).map((h) => <Row key={`${h.category}-${h.symbol}`} h={h} />)}
      </div>

      {m?.rules && (
        <ol className="mt-4 space-y-0.5 border-t border-[var(--line)] pt-3 text-[10.5px] text-[var(--ink-muted)]">
          {m.rules.map((r, i) => <li key={i}>{i + 1}. {r}</li>)}
        </ol>
      )}
    </Card>
  );
}

function Action({ symbol, kind }: { symbol: string; kind: "trim" | "add" }) {
  const trim = kind === "trim";
  return (
    <div className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-[12px] ${
      trim ? "border-[var(--warn)]/25 bg-[var(--warn-dim)]" : "border-[var(--profit)]/25 bg-[var(--profit-dim)]"}`}>
      {trim ? <ArrowDown size={13} className="text-[var(--warn)]" />
            : <ArrowUp size={13} className="text-[var(--profit)]" />}
      <span className="font-semibold text-[var(--ink)]">{symbol}</span>
      <span className="text-[var(--ink-secondary)]">
        {trim ? "has run ahead — trim back to target" : "has lagged — top up to target"}
      </span>
    </div>
  );
}

function Row({ h }: { h: RebalHolding }) {
  const up = h.drift_pct >= 0;
  const act = h.action;
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-3 py-2 ${
      act === "hold" ? "surface-raised"
        : act === "trim" ? "border border-[var(--warn)]/25 bg-[var(--warn-dim)]"
        : "border border-[var(--profit)]/25 bg-[var(--profit-dim)]"}`}>
      <span className="min-w-[86px] font-semibold text-[var(--ink)]">{h.symbol.replace("USDT", "")}</span>
      <span className="rounded bg-[var(--surface-hover)] px-1.5 py-0.5 text-[9.5px] capitalize text-[var(--ink-muted)]">
        {h.category}
      </span>
      <span className="text-[11px] tabular-nums text-[var(--ink-secondary)]">
        target {pct(h.target_weight, 2)}
      </span>
      <span className="text-[11px] tabular-nums text-[var(--ink-muted)]">
        now {pct(h.current_weight, 2)}
      </span>
      <span className={`ml-auto text-[11px] tabular-nums ${up ? "text-[var(--profit)]" : "text-[var(--loss)]"}`}>
        {up ? "+" : ""}{h.drift_pct.toFixed(2)}%
      </span>
    </div>
  );
}
