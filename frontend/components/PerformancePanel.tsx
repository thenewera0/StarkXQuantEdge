"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchPerformance, type Performance } from "@/lib/api";
import { Card } from "./ui";
import { EquityCurve } from "./EquityCurve";
import { Wallet, TrendingUp, TrendingDown, RefreshCw, Layers, LineChart, Gauge } from "lucide-react";

const REGIME_LABEL: Record<string, string> = {
  strong_trend: "Strong trend", weak_trend: "Weak trend", range: "Range",
  high_vol: "High vol", squeeze: "Squeeze", unknown: "Unknown",
};

const SIZES = [100, 1000, 10000];

function usd(n: number | null | undefined): string {
  if (n == null) return "—";
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function tone(n: number | null | undefined): string {
  if (n == null || n === 0) return "text-slate-600";
  return n > 0 ? "text-emerald-600" : "text-rose-600";
}

export function PerformancePanel({ refreshKey }: { refreshKey: number }) {
  const [perf, setPerf] = useState<Performance | null>(null);
  const [size, setSize] = useState(1000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (s: number) => {
    setLoading(true);
    setError(null);
    try {
      setPerf(await fetchPerformance(s));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load performance");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(size); }, [load, size, refreshKey]);

  if (perf && !perf.enabled) {
    return (
      <Card className="card-pad text-sm text-slate-500">
        <div className="mb-1 flex items-center gap-2 font-semibold text-slate-700"><Wallet size={15} /> Performance</div>
        Persistence isn&apos;t configured, so paper-trading P&amp;L will appear here once the database is connected.
      </Card>
    );
  }

  const c = perf?.combined;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Wallet size={16} className="text-indigo-500" />
          <span className="text-sm font-semibold tracking-tight">Paper-Trading Performance</span>
          <span className="text-xs text-slate-400">every asset · {usd(size)}/trade</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="seg">
            {SIZES.map((s) => (
              <button key={s} data-active={size === s} onClick={() => setSize(s)}>${s.toLocaleString()}</button>
            ))}
          </div>
          <button onClick={() => load(size)} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800">
            <RefreshCw size={12} className={loading ? "shimmer" : ""} /> Refresh
          </button>
        </div>
      </div>

      {error && <div className="mb-3 text-sm text-rose-600">{error}</div>}

      {/* Combined headline */}
      {c && (
        <>
          <div className="rounded-2xl border border-slate-100 bg-gradient-to-br from-slate-50 to-white p-5">
            <div className="text-xs uppercase tracking-wide text-slate-400">Combined P&amp;L (all trades, all assets)</div>
            <div className={`mt-1 text-4xl font-semibold tabular-nums ${tone(c.total_pnl_usd)}`}>
              {usd(c.total_pnl_usd)}
            </div>
            <div className="mt-1 flex flex-wrap gap-4 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1">Realized: <span className={`font-medium ${tone(c.realized_pnl_usd)}`}>{usd(c.realized_pnl_usd)}</span></span>
              <span className="inline-flex items-center gap-1">Floating (open): <span className={`font-medium ${tone(c.open_pnl_usd)}`}>{usd(c.open_pnl_usd)}</span></span>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Closed trades" value={`${c.closed_trades}`} />
            <Metric label="Open trades" value={`${c.open_trades}`} />
            <Metric label="Hit rate" value={c.hit_rate != null ? `${(c.hit_rate * 100).toFixed(0)}%` : "—"} />
            <Metric label="W / L" value={`${c.wins} / ${c.losses}`} />
          </div>
        </>
      )}

      {/* Equity curve */}
      {perf?.equity_curve && perf.equity_curve.length > 1 && (
        <div className="mt-5">
          <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <LineChart size={13} /> Equity curve (cumulative realized P&amp;L)
          </div>
          <EquityCurve points={perf.equity_curve} />
        </div>
      )}

      {/* Per-regime breakdown */}
      {perf?.per_regime && perf.per_regime.length > 0 && (
        <div className="mt-5">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <Gauge size={13} /> P&amp;L by regime
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            {perf.per_regime.map((r) => (
              <div key={r.regime} className="rounded-xl border border-slate-100 bg-white p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-700">{REGIME_LABEL[r.regime] ?? r.regime}</span>
                  <span className={`text-sm font-semibold tabular-nums ${tone(r.pnl_usd)}`}>{usd(r.pnl_usd)}</span>
                </div>
                <div className="mt-0.5 text-[11px] text-slate-400">
                  {r.trades} trades · {r.hit_rate != null ? `${(r.hit_rate * 100).toFixed(0)}% hit` : "—"}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-asset breakdown */}
      {perf?.per_symbol && perf.per_symbol.length > 0 && (
        <div className="mt-5">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <Layers size={13} /> P&amp;L by asset (realized)
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {perf.per_symbol.map((s) => (
              <div key={s.symbol} className="flex items-center justify-between rounded-xl border border-slate-100 bg-white px-3 py-2">
                <div className="flex items-center gap-2">
                  {s.pnl_usd >= 0 ? <TrendingUp size={14} className="text-emerald-500" /> : <TrendingDown size={14} className="text-rose-500" />}
                  <span className="font-medium text-slate-800">{s.symbol}</span>
                  <span className="text-[11px] text-slate-400">{s.trades}t · {s.wins}W</span>
                </div>
                <span className={`text-sm font-semibold tabular-nums ${tone(s.pnl_usd)}`}>{usd(s.pnl_usd)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trade log */}
      {perf?.trades && perf.trades.length > 0 && (
        <div className="mt-5">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Closed trades</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
                  <th className="py-1.5 pr-3 font-medium">Asset</th>
                  <th className="py-1.5 pr-3 font-medium">Dir</th>
                  <th className="py-1.5 pr-3 font-medium">Result</th>
                  <th className="py-1.5 pr-3 font-medium text-right">P&amp;L %</th>
                  <th className="py-1.5 pr-3 font-medium text-right">P&amp;L $</th>
                </tr>
              </thead>
              <tbody>
                {perf.trades.map((t, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="py-2 pr-3 font-medium text-slate-800">{t.symbol} <span className="text-[11px] text-slate-400">{t.interval}</span></td>
                    <td className="py-2 pr-3 capitalize text-slate-500">{t.direction}</td>
                    <td className="py-2 pr-3">
                      <span className={t.result === "target" ? "text-emerald-600" : t.result === "stop" ? "text-rose-600" : "text-slate-500"}>{t.result}</span>
                    </td>
                    <td className={`py-2 pr-3 text-right tabular-nums ${tone(t.pnl_pct)}`}>{t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct}%</td>
                    <td className={`py-2 pr-3 text-right font-medium tabular-nums ${tone(t.pnl_usd)}`}>{usd(t.pnl_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(!c || c.closed_trades === 0) && !loading && (
        <div className="py-4 text-center text-sm text-slate-400">No closed trades yet. Open signals are being tracked; P&amp;L fills in as targets/stops hit.</div>
      )}
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-3 text-center">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-0.5 text-lg font-semibold tabular-nums text-slate-800">{value}</div>
    </div>
  );
}
