"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchRecent, fetchStats, type RecentSignal, type Stats } from "@/lib/api";
import { Card } from "./ui";
import { History, RefreshCw, Target, CircleDot } from "lucide-react";

const LABEL_COLOR: Record<string, string> = {
  "Strong Buy": "text-emerald-600", Buy: "text-emerald-600",
  Neutral: "text-slate-500",
  Sell: "text-rose-600", "Strong Sell": "text-rose-600",
};

export function HistoryPanel({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<RecentSignal[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([fetchRecent(15), fetchStats()]);
      setRows(r); setStats(s); setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load history");
    }
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (stats && !stats.enabled) {
    return (
      <Card className="card-pad text-sm text-slate-500">
        <div className="mb-1 flex items-center gap-2 font-semibold text-slate-700"><History size={15} /> Signal history</div>
        Persistence isn&apos;t configured — logged decisions and accuracy will appear here once the database is connected.
      </Card>
    );
  }

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History size={15} className="text-slate-400" />
          <span className="text-sm font-semibold tracking-tight">Signal History &amp; Accuracy</span>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {stats && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <StatTile label="Resolved" value={`${stats.resolved ?? 0}`} icon={<CircleDot size={14} />} />
          <StatTile label="Hit rate" value={stats.hit_rate != null ? `${(stats.hit_rate * 100).toFixed(0)}%` : "—"} icon={<Target size={14} />} accent="emerald" />
          <StatTile label="Avg P&L" value={stats.avg_pnl != null ? `${(stats.avg_pnl * 100).toFixed(2)}%` : "—"} icon={<Target size={14} />} accent={stats.avg_pnl != null && stats.avg_pnl < 0 ? "rose" : "emerald"} />
        </div>
      )}

      {error && <div className="text-sm text-rose-600">{error}</div>}

      {rows.length === 0 ? (
        <div className="py-6 text-center text-sm text-slate-400">No signals logged yet. Run an AI debate to record one.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
                <th className="py-1.5 pr-3 font-medium">Symbol</th>
                <th className="py-1.5 pr-3 font-medium">TF</th>
                <th className="py-1.5 pr-3 font-medium">Signal</th>
                <th className="py-1.5 pr-3 font-medium">Conf</th>
                <th className="py-1.5 pr-3 font-medium">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50/60">
                  <td className="py-2 pr-3 font-medium text-slate-800">{r.symbol}</td>
                  <td className="py-2 pr-3 text-slate-500">{r.interval}</td>
                  <td className={`py-2 pr-3 font-medium ${LABEL_COLOR[r.label] ?? "text-slate-600"}`}>{r.label}</td>
                  <td className="py-2 pr-3 tabular-nums text-slate-600">{r.final_confidence != null ? `${r.final_confidence}%` : `${r.confidence}%`}</td>
                  <td className="py-2 pr-3">
                    {r.result ? (
                      <span className={r.result === "target" ? "text-emerald-600" : "text-rose-600"}>
                        {r.result}{r.pnl != null ? ` (${(r.pnl * 100).toFixed(1)}%)` : ""}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-slate-400"><CircleDot size={11} /> open</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function StatTile({ label, value, icon, accent }: { label: string; value: string; icon: React.ReactNode; accent?: "emerald" | "rose" }) {
  const v = accent === "emerald" ? "text-emerald-600" : accent === "rose" ? "text-rose-600" : "text-slate-800";
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-3 text-center">
      <div className="flex items-center justify-center gap-1 text-[11px] uppercase tracking-wide text-slate-400">{icon}{label}</div>
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${v}`}>{value}</div>
    </div>
  );
}
