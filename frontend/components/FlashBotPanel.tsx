"use client";

import { useCallback, useEffect, useState } from "react";
import { scanFlash, fetchByStrategy, type FlashScan, type ByStrategy, type FlashTrigger } from "@/lib/api";
import { Card } from "./ui";
import { Zap, RefreshCw, ArrowUpRight, ArrowDownRight, AlertTriangle, Activity } from "lucide-react";

function usd(n: number): string {
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toFixed(2)}`;
}
function tone(n: number): string {
  return n > 0 ? "text-emerald-400" : n < 0 ? "text-rose-400" : "text-slate-400";
}

const KIND_TONE: Record<string, string> = {
  burst: "bg-[#00d4ff]/10 text-[#00d4ff] border-[#00d4ff]/20",
  breakout: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  snap: "bg-amber-500/10 text-amber-400 border-amber-500/20",
};

export function FlashBotPanel() {
  const [scan, setScan] = useState<FlashScan | null>(null);
  const [pnl, setPnl] = useState<ByStrategy | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, p] = await Promise.all([scanFlash(), fetchByStrategy(1000).catch(() => null)]);
      setScan(s); if (p) setPnl(p); setError(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = window.setInterval(load, 60000);   // hunt refresh every minute
    return () => window.clearInterval(id);
  }, [load]);

  const triggers = scan?.triggers ?? [];
  const tradeable = triggers.filter((t) => t.tradeable);
  const flashPnl = pnl?.strategies?.["flash (paper)"] ?? pnl?.strategies?.["flash"];

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#00d4ff] to-[#0066ff]">
            <Zap size={15} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-white">Flash Bot</div>
            <div className="text-[10px] text-slate-500">fast 15m / 1h momentum · breakout · snap</div>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Hunt
        </button>
      </div>

      {/* Honest status: paper until it proves an edge */}
      <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-500/[0.07] p-3">
        <AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-400" />
        <div className="text-[11.5px] leading-relaxed text-amber-200/90">
          <span className="font-semibold text-amber-300">Running on paper.</span> A 2,791-trade backtest of these
          triggers (net of real fees) returned a 35% win rate and negative expectancy. It trades continuously here to
          build a live record — it moves to real capital only if that record turns genuinely profitable.
        </div>
      </div>

      {error && <div className="mb-3 text-sm text-rose-400">{error}</div>}

      {/* Stats row */}
      <div className="mb-4 grid grid-cols-4 gap-2.5">
        <Stat label="Watching" value={`${scan?.scanned ?? 0}`} sub="pairs × TF" />
        <Stat label="Setups now" value={`${tradeable.length}`} sub={`${triggers.length} triggers`} accent />
        <Stat label="Paper trades" value={`${flashPnl?.trades ?? 0}`} sub={flashPnl?.hit_rate != null ? `${Math.round(flashPnl.hit_rate * 100)}% hit` : "—"} />
        <Stat label="Paper P&L" value={usd(flashPnl?.realized_pnl_usd ?? 0)} sub="tracked apart" valueClass={tone(flashPnl?.realized_pnl_usd ?? 0)} />
      </div>

      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        <Activity size={12} /> Live opportunity feed
      </div>

      {triggers.length === 0 ? (
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-white/[0.02] p-4 text-sm text-slate-400">
          No fast setups on the tape right now. The bot re-hunts every 5 minutes.
        </div>
      ) : (
        <div className="space-y-2">
          {triggers.slice(0, 8).map((t) => <TriggerRow key={`${t.symbol}${t.interval}`} t={t} />)}
        </div>
      )}
    </Card>
  );
}

function Stat({ label, value, sub, accent, valueClass }: { label: string; value: string; sub?: string; accent?: boolean; valueClass?: string }) {
  return (
    <div className={`rounded-xl border p-2.5 ${accent ? "border-[#00d4ff]/20 bg-[#00d4ff]/[0.05]" : "border-[rgba(255,255,255,0.06)] bg-white/[0.02]"}`}>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-0.5 text-lg font-bold tabular-nums ${valueClass ?? (accent ? "text-[#00d4ff]" : "text-white")}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
    </div>
  );
}

function TriggerRow({ t }: { t: FlashTrigger }) {
  const up = t.direction === "long";
  return (
    <div className={`rounded-xl border p-2.5 ${t.tradeable ? "border-emerald-500/20 bg-emerald-500/[0.04]" : "border-[rgba(255,255,255,0.06)] bg-white/[0.02]"}`}>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="font-semibold text-white">{t.symbol}</span>
        <span className="text-[11px] text-slate-500">{t.interval}</span>
        <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold ${up ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
          {up ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}{t.direction}
        </span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${KIND_TONE[t.kind] ?? "bg-slate-500/10 text-slate-400 border-slate-500/20"}`}>{t.kind}</span>
        <span className="ml-auto flex items-center gap-2">
          <span className={`text-xs font-bold tabular-nums ${t.ev_r > 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {t.ev_r > 0 ? "+" : ""}{t.ev_r.toFixed(3)}R
          </span>
          {t.tradeable
            ? <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-bold text-emerald-400">TAKE</span>
            : <span className="rounded bg-slate-500/10 px-1.5 py-0.5 text-[10px] text-slate-500">skip</span>}
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-slate-500 tabular-nums">
        <span>entry <span className="text-slate-300">{t.entry}</span></span>
        <span>stop <span className="text-rose-400/80">{t.stop}</span></span>
        <span>target <span className="text-emerald-400/80">{t.target}</span></span>
        <span>ATR {(t.atr_pct * 100).toFixed(2)}%</span>
        <span>cost {t.cost_r.toFixed(2)}R</span>
      </div>
    </div>
  );
}
