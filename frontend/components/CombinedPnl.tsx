"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchByStrategy, fetchLiveTrades, type ByStrategy } from "@/lib/api";
import { Card } from "./ui";
import { Wallet, Zap, ShieldCheck, Layers, ArrowUpRight } from "lucide-react";

function usd(n: number): string {
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function tone(n: number): string {
  return n > 0 ? "text-[var(--profit)]" : n < 0 ? "text-[var(--loss)]" : "text-slate-300";
}

export function CombinedPnl({ refreshKey = 0 }: { refreshKey?: number }) {
  const [d, setD] = useState<ByStrategy | null>(null);
  const [floating, setFloating] = useState<number>(0);

  const load = useCallback(async () => {
    try {
      const [s, lt] = await Promise.all([
        fetchByStrategy(1000),
        fetchLiveTrades(1000, "core").catch(() => null),
      ]);
      setD(s);
      if (lt?.open_pnl_usd != null) setFloating(lt.open_pnl_usd);
    } catch {
      /* keep last good */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  useEffect(() => {
    const id = window.setInterval(load, 30000);
    return () => window.clearInterval(id);
  }, [load]);

  const core = d?.strategies?.["core"];
  const flash = d?.strategies?.["flash (paper)"] ?? d?.strategies?.["flash"];
  const coreTotal = (core?.realized_pnl_usd ?? 0) + floating;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-[var(--accent-bright)]" />
          <span className="text-sm font-semibold tracking-tight text-white">Strategy P&amp;L Breakdown</span>
        </div>
        <span className="text-[10.5px] uppercase tracking-wider text-slate-400 font-medium">Independent Accounts</span>
      </div>

      {/* Account 1: Core Real Capital */}
      <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/[0.06] to-transparent p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-500/20 text-emerald-400">
              <Wallet size={12} />
            </div>
            <span className="text-xs font-semibold text-white">Core Capital Account</span>
          </div>
          <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-400 border border-emerald-500/25">
            <ShieldCheck size={10} /> REAL CAPITAL
          </span>
        </div>

        <div className={`mt-2 text-3xl font-bold tabular-nums ${tone(coreTotal)}`}>
          {usd(coreTotal)}
        </div>

        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
          <span>
            Realized:{" "}
            <span className={`font-semibold ${tone(core?.realized_pnl_usd ?? 0)}`}>
              {usd(core?.realized_pnl_usd ?? 0)}
            </span>
          </span>
          <span>
            Floating:{" "}
            <span className={`font-semibold ${tone(floating)}`}>
              {usd(floating)}
            </span>
          </span>
          <span>
            {core?.trades ?? 0} trades ·{" "}
            {core?.hit_rate != null ? `${(core.hit_rate * 100).toFixed(1)}%` : "—"} hit
          </span>
        </div>
      </div>

      {/* Account 2: Flash Paper Incubator (Strictly Separated) */}
      <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-500/20 text-amber-400">
              <Zap size={12} />
            </div>
            <div>
              <div className="text-xs font-semibold text-white">Flash Bot Incubator</div>
              <div className="text-[10px] text-slate-400">1h crypto scalper · zero real capital risk</div>
            </div>
          </div>
          <span className="rounded bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/25">
            PAPER
          </span>
        </div>

        <div className="mt-2 flex items-center justify-between pt-1 border-t border-white/5">
          <div className="text-[11px] text-slate-400">
            {flash?.trades ?? 0} paper trades ·{" "}
            {flash?.hit_rate != null ? `${(flash.hit_rate * 100).toFixed(1)}%` : "—"} hit
          </div>
          <span className={`text-base font-bold tabular-nums ${tone(flash?.realized_pnl_usd ?? 0)}`}>
            {usd(flash?.realized_pnl_usd ?? 0)}
          </span>
        </div>
      </div>

      <p className="mt-3 text-[10.5px] leading-relaxed text-slate-400">
        Flash operates in an isolated paper sandbox. It is never mixed with Core real capital, ensuring complete accounting integrity.
      </p>
    </Card>
  );
}
