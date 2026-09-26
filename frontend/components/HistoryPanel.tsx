"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchRecent, fetchStats, type RecentSignal, type Stats } from "@/lib/api";
import { Card } from "./ui";
import { History, RefreshCw, Target, CircleDot, Zap } from "lucide-react";

type StratFilter = "all" | "core" | "flash";

const LABEL_COLOR: Record<string, string> = {
  "Strong Buy": "text-[var(--profit)]", Buy: "text-[var(--profit)]",
  Neutral: "text-[var(--ink-muted)]",
  Sell: "text-[var(--loss)]", "Strong Sell": "text-[var(--loss)]",
};

export function HistoryPanel({ refreshKey }: { refreshKey: number }) {
  const [strat, setStrat] = useState<StratFilter>("all");
  const [rows, setRows] = useState<RecentSignal[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([fetchRecent(20, strat), fetchStats(strat)]);
      setRows(r); setStats(s); setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load history");
    }
  }, [strat]);

  useEffect(() => { load(); }, [load, refreshKey, strat]);

  if (stats && !stats.enabled) {
    return (
      <Card className="card-pad text-sm text-[var(--ink-muted)]">
        <div className="mb-1 flex items-center gap-2 font-semibold text-[var(--ink-secondary)]"><History size={15} /> Signal history</div>
        Persistence isn&apos;t configured — logged decisions and accuracy will appear here once the database is connected.
      </Card>
    );
  }

  return (
    <Card className="card-pad">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <History size={15} className="text-slate-400" />
          <span className="text-sm font-semibold tracking-tight">Signal History &amp; Accuracy</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="seg">
            {(["all", "core", "flash"] as StratFilter[]).map((s) => (
              <button
                key={s}
                data-active={strat === s}
                onClick={() => setStrat(s)}
                className="capitalize text-xs"
              >
                {s === "all" ? "All" : s === "core" ? "Core" : "Flash"}
              </button>
            ))}
          </div>
          <button onClick={load} className="flex items-center gap-1 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)]">
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      {stats && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <StatTile label={`${strat.toUpperCase()} Resolved`} value={`${stats.resolved ?? 0}`} icon={<CircleDot size={14} />} />
          <StatTile label="Hit rate" value={stats.hit_rate != null ? `${(stats.hit_rate * 100).toFixed(0)}%` : "—"} icon={<Target size={14} />} accent="emerald" />
          <StatTile label="Avg P&L" value={stats.avg_pnl != null ? `${(stats.avg_pnl * 100).toFixed(2)}%` : "—"} icon={<Target size={14} />} accent={stats.avg_pnl != null && stats.avg_pnl < 0 ? "rose" : "emerald"} />
        </div>
      )}

      {error && <div className="text-sm text-[var(--loss)]">{error}</div>}

      {rows.length === 0 ? (
        <div className="py-6 text-center text-sm text-slate-400">No {strat} signals logged yet. Run an analysis or scan to record one.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
                <th className="py-1.5 pr-3 font-medium">Asset</th>
                <th className="py-1.5 pr-3 font-medium">Type</th>
                <th className="py-1.5 pr-3 font-medium">TF</th>
                <th className="py-1.5 pr-3 font-medium">Signal</th>
                <th className="py-1.5 pr-3 font-medium">Conf</th>
                <th className="py-1.5 pr-3 font-medium">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const isFlash = r.strategy === "flash";
                return (
                  <tr key={r.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-raised)]">
                    <td className="py-2 pr-3 font-medium text-[var(--ink)]">{r.symbol}</td>
                    <td className="py-2 pr-3">
                      {isFlash ? (
                        <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[9px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <Zap size={9} /> FLASH
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          CORE
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-[var(--ink-muted)]">{r.interval}</td>
                    <td className={`py-2 pr-3 font-medium ${LABEL_COLOR[r.label] ?? "text-[var(--ink-secondary)]"}`}>{r.label}</td>
                    <td className="py-2 pr-3 tabular-nums text-[var(--ink-secondary)]">{r.final_confidence != null ? `${r.final_confidence}%` : `${r.confidence}%`}</td>
                    <td className="py-2 pr-3">
                      {r.result ? (
                        <span className={r.result === "target" ? "text-[var(--profit)]" : "text-[var(--loss)]"}>
                          {r.result}{r.pnl != null ? ` (${(r.pnl * 100).toFixed(1)}%)` : ""}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-slate-400"><CircleDot size={11} /> open</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function StatTile({ label, value, icon, accent }: { label: string; value: string; icon: React.ReactNode; accent?: "emerald" | "rose" }) {
  const v = accent === "emerald" ? "text-[var(--profit)]" : accent === "rose" ? "text-[var(--loss)]" : "text-[var(--ink)]";
  return (
    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-raised)] p-3 text-center">
      <div className="flex items-center justify-center gap-1 text-[11px] uppercase tracking-wide text-slate-400">{icon}{label}</div>
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${v}`}>{value}</div>
    </div>
  );
}
