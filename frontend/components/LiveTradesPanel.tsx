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
  return n > 0 ? "text-emerald-400" : n < 0 ? "text-rose-400" : "text-slate-400";
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
          <Radio size={16} className="text-[#00d4ff]" />
          <span className="text-sm font-semibold tracking-tight text-white">Running Trades</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> LIVE
          </span>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-rose-400">{error}</div>}

      {/* Floating P&L summary */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-white/[0.02] p-3">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Open positions</div>
          <div className="mt-1 text-xl font-bold tabular-nums text-white">{live.length}</div>
        </div>
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-white/[0.02] p-3">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Floating P&L</div>
          <div className={`mt-1 text-xl font-bold tabular-nums ${tone(d?.open_pnl_usd ?? 0)}`}>{usd(d?.open_pnl_usd ?? 0)}</div>
        </div>
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-white/[0.02] p-3">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Flash (paper)</div>
          <div className="mt-1 text-xl font-bold tabular-nums text-[#00d4ff]">{paper.length}</div>
        </div>
      </div>

      {trades.length === 0 && (
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-white/[0.02] p-4 text-sm text-slate-400">
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
    <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-white/[0.02] p-3 transition-colors hover:bg-white/[0.04]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold text-white">{t.symbol}</span>
        <span className="text-[11px] text-slate-500">{t.interval}</span>
        <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold ${up ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
          {up ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}{t.direction}
        </span>
        {t.strategy === "flash" && (
          <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20">
            <Zap size={10} /> flash
          </span>
        )}
        {t.paper && <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-400 border border-amber-500/20">PAPER</span>}
        <span className="ml-auto text-right">
          <span className={`text-base font-bold tabular-nums ${tone(t.pnl_usd)}`}>{usd(t.pnl_usd)}</span>
          <span className={`ml-2 text-xs tabular-nums ${tone(t.pnl_pct)}`}>{t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct}%</span>
        </span>
      </div>

      {/* progress toward target */}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={`h-full rounded-full transition-all ${prog >= 0 ? "bg-emerald-400" : "bg-rose-400"}`}
          style={{ width: `${Math.abs(prog)}%`, marginLeft: prog >= 0 ? 0 : "auto" }}
        />
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500 tabular-nums">
        <span>entry <span className="text-slate-300">{t.entry}</span></span>
        <span>now <span className="text-white font-medium">{t.price}</span></span>
        {t.stop != null && <span className="flex items-center gap-0.5"><ShieldAlert size={10} className="text-rose-400" />{t.stop}</span>}
        {t.target != null && <span className="flex items-center gap-0.5"><Target size={10} className="text-emerald-400" />{t.target}</span>}
        {t.r_multiple != null && <span>{t.r_multiple > 0 ? "+" : ""}{t.r_multiple}R</span>}
        <span className="ml-auto">{ago(t.opened_at)} ago</span>
      </div>
    </div>
  );
}
