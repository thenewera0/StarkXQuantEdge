"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchLiveTrades, type LiveTrades, type LiveTrade } from "@/lib/api";
import { Card } from "./ui";
import { Radio, RefreshCw, ArrowUpRight, ArrowDownRight, Zap, Target, ShieldAlert } from "lucide-react";

function usd(n: number): string {
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toFixed(2)}`;
}
function tone(n: number): string {
  return n > 0 ? "text-[var(--profit)]" : n < 0 ? "text-[var(--loss)]" : "text-slate-400";
}
function ago(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h` : `${Math.floor(h / 24)}d`;
}

export function LiveTradesPanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const [d, setD] = useState<LiveTrades | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setD(await fetchLiveTrades(1000)); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);
  // Live refresh every 20s so P&L actually moves.
  useEffect(() => {
    const id = window.setInterval(load, 20000);
    return () => window.clearInterval(id);
  }, [load]);

  const trades = d?.trades ?? [];
  const live = trades.filter((t) => !t.paper);
  const paper = trades.filter((t) => t.paper);

  return (
    <Card className="card-pad" >
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio size={16} className="text-[var(--accent-bright)]" />
          <span className="text-sm font-semibold tracking-tight text-white">Running Trades</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--profit-dim)]0/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--profit)] border border-emerald-500/20">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> LIVE
          </span>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {/* Floating P&L summary */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        <div className="rounded-xl border surface-raised p-3">
          <div className="text-[10px] uppercase tracking-wide text-[var(--ink-muted)]">Open positions</div>
          <div className="mt-1 text-xl font-bold tabular-nums text-white">{d?.count ?? live.length}</div>
          <div className="text-[10px] text-[var(--ink-muted)]">real capital</div>
        </div>
        <div className="rounded-xl border surface-raised p-3">
          <div className="text-[10px] uppercase tracking-wide text-[var(--ink-muted)]">Floating P&L</div>
          <div className={`mt-1 text-xl font-bold tabular-nums ${tone(d?.open_pnl_usd ?? 0)}`}>{usd(d?.open_pnl_usd ?? 0)}</div>
          <div className="text-[10px] text-[var(--ink-muted)]">those same positions</div>
        </div>
        <div className="rounded-xl border surface-raised p-3">
          <div className="text-[10px] uppercase tracking-wide text-[var(--ink-muted)]">Flash (paper)</div>
          <div className="mt-1 text-xl font-bold tabular-nums text-[var(--accent-bright)]">{d?.paper_count ?? paper.length}</div>
          <div className={`text-[10px] tabular-nums ${tone(d?.paper_pnl_usd ?? 0)}`}>{usd(d?.paper_pnl_usd ?? 0)} not real</div>
        </div>
      </div>

      {(d?.unpriced ?? 0) > 0 && (
        <div className="mb-3 rounded-xl border border-[var(--warn)]/25 bg-[var(--warn-dim)] p-2.5 text-[11px] text-[var(--ink-secondary)]">
          {d?.unpriced} open position{(d?.unpriced ?? 0) > 1 ? "s have" : " has"} no live quote right now.
          They are listed below without a mark rather than hidden &mdash; an open risk is never dropped
          from this view just because a price feed is unavailable.
        </div>
      )}

      {trades.length === 0 && (
        <div className="rounded-xl border surface-raised p-4 text-sm text-slate-400">
          No positions open right now. The engine opens a trade when a setup clears its expected-value bar.
        </div>
      )}

      <div className="space-y-2">
        {trades.map((t) => <TradeRow key={t.id} t={t} />)}
      </div>
    </Card>
  );
}

function TradeRow({ t }: { t: LiveTrade }) {
  const up = t.direction === "long";
  const prog = Math.max(-100, Math.min(100, t.progress_pct ?? 0));
  return (
    <div className="rounded-xl border surface-raised p-3 transition-colors hover:bg-[var(--surface-hover)]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold text-white">{t.symbol}</span>
        <span className="text-[11px] text-[var(--ink-muted)]">{t.interval}</span>
        <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold ${up ? "bg-[var(--profit-dim)]0/10 text-[var(--profit)]" : "bg-[var(--loss-dim)]0/10 text-[var(--loss)]"}`}>
          {up ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}{t.direction}
        </span>
        {t.strategy === "flash" && (
          <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold bg-[var(--accent-bright)]/10 text-[var(--accent-bright)] border border-[var(--accent-bright)]/20">
            <Zap size={10} /> flash
          </span>
        )}
        {t.paper && <span className="rounded bg-[var(--warn-dim)]0/10 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--warn)] border border-amber-500/20">PAPER</span>}
        <span className="ml-auto text-right">
          <span className={`text-base font-bold tabular-nums ${tone(t.pnl_usd ?? 0)}`}>
            {t.priced ? usd(t.pnl_usd ?? 0) : "—"}
          </span>
          {t.priced && t.pnl_pct != null && (
            <span className={`ml-2 text-xs tabular-nums ${tone(t.pnl_pct)}`}>
              {t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct}%
            </span>
          )}
        </span>
      </div>

      {/* progress toward target */}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={`h-full rounded-full transition-all ${prog >= 0 ? "bg-emerald-400" : "bg-rose-400"}`}
          style={{ width: `${Math.abs(prog)}%`, marginLeft: prog >= 0 ? 0 : "auto" }}
        />
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[var(--ink-muted)] tabular-nums">
        <span>entry <span className="text-slate-300">{t.entry}</span></span>
        <span>now <span className="text-white font-medium">{t.priced ? t.price : "no quote"}</span></span>
        {t.stop != null && <span className="flex items-center gap-0.5"><ShieldAlert size={10} className="text-[var(--loss)]" />{t.stop}</span>}
        {t.target != null && <span className="flex items-center gap-0.5"><Target size={10} className="text-[var(--profit)]" />{t.target}</span>}
        {t.r_multiple != null && <span>{t.r_multiple > 0 ? "+" : ""}{t.r_multiple}R</span>}
        <span className="ml-auto">{ago(t.opened_at)} ago</span>
      </div>
    </div>
  );
}
