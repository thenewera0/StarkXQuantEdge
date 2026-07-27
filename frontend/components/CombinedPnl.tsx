"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchByStrategy, fetchLiveTrades, type ByStrategy } from "@/lib/api";
import { Card } from "./ui";
import { Wallet, Zap, Layers } from "lucide-react";

function usd(n: number): string {
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
function tone(n: number): string {
  return n > 0 ? "text-emerald-400" : n < 0 ? "text-rose-400" : "text-slate-300";
}

export function CombinedPnl({ refreshKey = 0 }: { refreshKey?: number }) {
  const [d, setD] = useState<ByStrategy | null>(null);
  const [floating, setFloating] = useState<number>(0);

  const load = useCallback(async () => {
    try {
      const [s, lt] = await Promise.all([fetchByStrategy(1000), fetchLiveTrades(1000).catch(() => null)]);
      setD(s);
      if (lt?.open_pnl_usd != null) setFloating(lt.open_pnl_usd);
    } catch { /* keep last good */ }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);
  useEffect(() => {
    const id = window.setInterval(load, 30000);
    return () => window.clearInterval(id);
  }, [load]);

  const combined = d?.combined;
  const strategies = Object.entries(d?.strategies ?? {});
  const total = (combined?.realized_pnl_usd ?? 0) + floating;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center gap-2">
        <Layers size={16} className="text-[#00d4ff]" />
        <span className="text-sm font-semibold tracking-tight text-white">Total P&amp;L — all strategies</span>
      </div>

      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-gradient-to-br from-white/[0.04] to-transparent p-5">
        <div className="text-[11px] uppercase tracking-wide text-slate-500">Combined (realized + floating)</div>
        <div className={`mt-1 text-4xl font-bold tabular-nums ${tone(total)}`}>{usd(total)}</div>
        <div className="mt-1.5 flex flex-wrap gap-x-4 text-xs text-slate-400">
          <span>realized <span className={`font-medium ${tone(combined?.realized_pnl_usd ?? 0)}`}>{usd(combined?.realized_pnl_usd ?? 0)}</span></span>
          <span>floating <span className={`font-medium ${tone(floating)}`}>{usd(floating)}</span></span>
          <span>{combined?.trades ?? 0} trades · {combined?.hit_rate != null ? `${Math.round(combined.hit_rate * 100)}%` : "—"} hit</span>
        </div>
      </div>

      <div className="mt-3 space-y-2">
        {strategies.map(([name, s]) => (
          <div key={name} className="flex items-center gap-3 rounded-xl border border-[rgba(255,255,255,0.06)] bg-white/[0.02] p-3">
            <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${s.paper ? "bg-amber-500/10" : "bg-[#0066ff]/15"}`}>
              {s.paper ? <Zap size={13} className="text-amber-400" /> : <Wallet size={13} className="text-[#00d4ff]" />}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-medium capitalize text-white">
                {name.replace("(paper)", "")}
                {s.paper && <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-bold text-amber-400 border border-amber-500/20">PAPER</span>}
              </div>
              <div className="text-[11px] text-slate-500">
                {s.trades} trades · {s.hit_rate != null ? `${Math.round(s.hit_rate * 100)}% hit` : "—"}
              </div>
            </div>
            <span className={`ml-auto text-lg font-bold tabular-nums ${tone(s.realized_pnl_usd)}`}>{usd(s.realized_pnl_usd)}</span>
          </div>
        ))}
      </div>
      <p className="mt-2.5 text-[10.5px] leading-relaxed text-slate-500">
        Paper strategies are excluded from the combined total — only real capital counts toward the track record.
      </p>
    </Card>
  );
}
