"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchSummary, type Summary, type WindowStats } from "@/lib/api";
import { Card } from "./ui";
import { CalendarDays, Brain, CheckCircle2, XCircle, RefreshCw } from "lucide-react";

const REGIME_LABEL: Record<string, string> = {
  strong_trend: "Strong trend", weak_trend: "Weak trend", range: "Range",
  high_vol: "High vol", squeeze: "Squeeze", trending: "Trending (old)",
  choppy: "Choppy (old)", unknown: "Unknown",
};

function usd(n: number | null | undefined): string {
  if (n == null) return "—";
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
function tone(n: number | null | undefined): string {
  if (n == null || n === 0) return "text-slate-700";
  return n > 0 ? "text-emerald-600" : "text-rose-600";
}

export function SummaryPanel({ refreshKey }: { refreshKey: number }) {
  const [s, setS] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setS(await fetchSummary(1000)); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  if (s && !s.enabled) return null;
  const L = s?.learning;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays size={16} className="text-indigo-500" />
          <span className="text-sm font-semibold tracking-tight">Weekly / Monthly Summary</span>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-rose-600">{error}</div>}

      <div className="grid gap-3 sm:grid-cols-3">
        {s?.week && <WindowCard title="Last 7 days" w={s.week} />}
        {s?.month && <WindowCard title="Last 30 days" w={s.month} />}
        {s?.all_time && <WindowCard title="All time" w={s.all_time} />}
      </div>

      {/* Self-learning */}
      {L && (
        <div className="mt-5">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <Brain size={13} /> What the engine self-learned
          </div>
          <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-3 text-sm text-slate-700">
            Trading is now restricted to regimes with proven positive expectancy:{" "}
            {L.tradeable_regimes.map((r) => (
              <span key={r} className="mr-1 inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-emerald-700">
                <CheckCircle2 size={11} /> {REGIME_LABEL[r] ?? r}
              </span>
            ))}
            . Excluded (proven-losing or unproven):{" "}
            {L.excluded_regimes.map((r) => (
              <span key={r} className="mr-1 inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                <XCircle size={11} /> {REGIME_LABEL[r] ?? r}
              </span>
            ))}
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {Object.entries(L.regime_performance).map(([r, p]) => (
              <div key={r} className={`flex items-center justify-between rounded-lg border p-2.5 text-sm ${p.tradeable ? "border-emerald-100 bg-white" : "border-slate-100 bg-slate-50/60"}`}>
                <div className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full ${p.tradeable ? "bg-emerald-500" : "bg-slate-300"}`} />
                  <span className="font-medium text-slate-700">{REGIME_LABEL[r] ?? r}</span>
                  <span className="text-[11px] text-slate-400">{p.trades}t · {p.hit_rate != null ? `${(p.hit_rate * 100).toFixed(0)}%` : "—"}</span>
                </div>
                <span className={`font-semibold tabular-nums ${tone(p.pnl_usd)}`}>{usd(p.pnl_usd)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function WindowCard({ title, w }: { title: string; w: WindowStats }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{title}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${tone(w.realized_pnl_usd)}`}>{usd(w.realized_pnl_usd)}</div>
      <div className="mt-1 text-xs text-slate-500">
        {w.trades} trades · {w.wins}W / {w.losses}L · {w.hit_rate != null ? `${(w.hit_rate * 100).toFixed(0)}% hit` : "—"}
      </div>
      <div className="mt-1 flex gap-3 text-[11px] text-slate-400">
        <span>best <span className="text-emerald-600">{usd(w.best_usd)}</span></span>
        <span>worst <span className="text-rose-600">{usd(w.worst_usd)}</span></span>
      </div>
    </div>
  );
}
