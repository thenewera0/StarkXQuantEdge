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

      {s?.risk_state && (s.risk_state.circuit_halted || s.risk_state.drifting) && (
        <div className={`mb-3 flex items-center gap-2 rounded-xl border p-3 text-sm ${
          s.risk_state.circuit_halted ? "border-rose-200 bg-rose-50/70 text-rose-700" : "border-amber-200 bg-amber-50/70 text-amber-700"}`}>
          <span className={`h-2 w-2 rounded-full ${s.risk_state.circuit_halted ? "bg-rose-500" : "bg-amber-500"} animate-pulse`} />
          {s.risk_state.circuit_halted ? (
            <span><span className="font-semibold">Circuit breaker engaged</span> — trading halted for 24h after a {s.risk_state.day_r}R day. Auto-clears as the window rolls off.</span>
          ) : (
            <span><span className="font-semibold">Drift detected</span> — expectancy shifted down; EV bar raised and size cut to {Math.round((s.risk_state.size_mult ?? 1) * 100)}%. Auto-recovers as the run ages out.</span>
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        {s?.week && <WindowCard title="Last 7 days" w={s.week} />}
        {s?.month && <WindowCard title="Last 30 days" w={s.month} />}
        {s?.all_time && <WindowCard title="All time" w={s.all_time} />}
      </div>

      {s?.allocator && Object.keys(s.allocator.weights).length > 0 && (
        <div className="mt-3 rounded-xl border border-slate-100 bg-white p-3">
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Strategy allocator (capital by family)</div>
          <div className="space-y-1.5">
            {Object.entries(s.allocator.weights).map(([fam, w]) => (
              <div key={fam} className="flex items-center gap-2 text-sm">
                <span className="w-24 shrink-0 capitalize text-slate-600">{fam}</span>
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div className="absolute inset-y-0 left-0 rounded-full bg-indigo-400" style={{ width: `${Math.round(w * 100)}%` }} />
                </div>
                <span className="w-10 shrink-0 text-right font-semibold tabular-nums text-slate-700">{Math.round(w * 100)}%</span>
                <span className="w-24 shrink-0 text-right text-[11px] text-slate-400">
                  {s.allocator!.stats[fam]?.n ?? 0}t · {(s.allocator!.stats[fam]?.r_mean ?? 0).toFixed(2)}R
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

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

          {L.direction_performance && Object.keys(L.direction_performance).length > 0 && (
            <div className="mt-3 rounded-xl border border-slate-100 bg-white p-3">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Direction gate</div>
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(L.direction_performance).map(([d, p]) => {
                  const on = (L.tradeable_directions ?? []).includes(d);
                  return (
                    <div key={d} className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <span className={`h-1.5 w-1.5 rounded-full ${on ? "bg-emerald-500" : "bg-rose-400"}`} />
                        <span className="font-medium capitalize text-slate-700">{d}</span>
                        <span className="text-[11px] text-slate-400">{p.trades}t · {on ? "trading" : "paused"}</span>
                      </span>
                      <span className={`font-semibold tabular-nums ${tone(p.pnl_usd)}`}>{usd(p.pnl_usd)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {L.paused_symbols && L.paused_symbols.length > 0 && (
            <div className="mt-3 rounded-xl border border-rose-100 bg-rose-50/40 p-3 text-sm text-slate-700">
              <span className="font-medium text-rose-600">Paused symbols</span> (proven-losing, auto-re-tested):{" "}
              {L.paused_symbols.map((s) => (
                <span key={s} className="mr-1 inline-block rounded bg-rose-100 px-1.5 py-0.5 text-xs font-medium text-rose-700">{s}</span>
              ))}
            </div>
          )}

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
