"use client";

import { useCallback, useEffect, useState } from "react";
import { scanFundingCarry, scanTriangular, scanCross, fetchArbAlerts, type FundingScan, type TriangularScan, type CrossScan, type ArbAlert } from "@/lib/api";
import { Card } from "./ui";
import { Repeat, RefreshCw, CheckCircle2, Triangle, ArrowLeftRight, Zap } from "lucide-react";

function pct(n: number, d = 2): string {
  return `${(n * 100).toFixed(d)}%`;
}

export function ArbPanel() {
  const [scan, setScan] = useState<FundingScan | null>(null);
  const [tri, setTri] = useState<TriangularScan | null>(null);
  const [cross, setCross] = useState<CrossScan | null>(null);
  const [alerts, setAlerts] = useState<ArbAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [f, t, c, a] = await Promise.all([
        scanFundingCarry(), scanTriangular().catch(() => null), scanCross().catch(() => null),
        fetchArbAlerts(24).catch(() => []),
      ]);
      setScan(f); setTri(t); setCross(c); setAlerts(a); setError(null);
    }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (scan && !scan.enabled) return null;
  const opps = scan?.opportunities ?? [];
  const livePositive = (scan?.positive ?? 0) + (cross?.positive ?? 0) + (tri?.opportunity?.positive ? 1 : 0);

  return (
    <Card className="card-pad">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Repeat size={16} className="text-teal-500" />
          <span className="text-sm font-semibold tracking-tight">Arbitrage scanner — funding · triangular · cross-exchange</span>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800">
          <RefreshCw size={12} className={loading ? "shimmer" : ""} /> Rescan
        </button>
      </div>

      {livePositive > 0 ? (
        <div className="mb-3 flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50/80 p-3 text-sm text-emerald-800">
          <Zap size={16} className="text-emerald-600" />
          <span><span className="font-semibold">{livePositive} live opportunit{livePositive === 1 ? "y" : "ies"} clearing costs right now</span> — see the highlighted rows below.</span>
        </div>
      ) : (
        <div className="mb-3 flex items-center gap-2 rounded-xl border border-slate-100 bg-slate-50/60 p-2.5 text-[12px] text-slate-500">
          <Zap size={14} className="text-slate-400" />
          <span>Watching {scan?.scanned ?? 0} funding · {tri?.pairs ?? 0} triangular · {cross?.scanned ?? 0} cross-exchange pairs. No positive-EV arb right now.
            {alerts.length > 0 && <span className="text-slate-600"> · <b>{alerts.length}</b> caught in last 24h.</span>}
          </span>
        </div>
      )}

      <p className="mb-3 text-[11px] leading-snug text-slate-500">
        Funding carry = long spot + short perp, harvesting funding. Each detector fires only when the
        edge clears its round-trip cost — usually silent, paying mainly during funding spikes.
      </p>

      {error && <div className="mb-2 text-sm text-rose-600">{error}</div>}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
              <th className="pb-1.5 font-medium">Symbol</th>
              <th className="pb-1.5 font-medium">Funding / 8h</th>
              <th className="pb-1.5 font-medium">Annualized</th>
              <th className="pb-1.5 font-medium">EV (after cost)</th>
              <th className="pb-1.5 font-medium">Half-life</th>
              <th className="pb-1.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {opps.slice(0, 12).map((o) => (
              <tr key={o.symbol} className={`border-t border-slate-100 ${o.positive ? "bg-emerald-50/60" : ""}`}>
                <td className="py-1.5 font-medium text-slate-700">{o.symbol}</td>
                <td className="py-1.5 tabular-nums text-slate-600">{pct(o.current_funding, 4)}</td>
                <td className={`py-1.5 tabular-nums ${o.annualized_yield >= 0 ? "text-slate-600" : "text-rose-500"}`}>{pct(o.annualized_yield, 1)}</td>
                <td className={`py-1.5 font-semibold tabular-nums ${o.ev > 0 ? "text-emerald-600" : "text-rose-500"}`}>{o.ev > 0 ? "+" : ""}{pct(o.ev, 3)}</td>
                <td className="py-1.5 tabular-nums text-slate-400">{o.half_life_periods != null ? `${o.half_life_periods}p` : "—"}</td>
                <td className="py-1.5">
                  {o.positive
                    ? <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700"><CheckCircle2 size={11} /> carry</span>
                    : <span className="text-[11px] text-slate-400">skip</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {scan && (
        <div className="mt-2 text-[11px] text-slate-400">
          {scan.scanned} scanned · {scan.positive ?? 0} positive-EV {(scan.positive ?? 0) === 1 ? "carry" : "carries"}
        </div>
      )}

      {tri && tri.enabled && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2 text-[12px]">
          <Triangle size={13} className="text-teal-500" />
          <span className="font-medium text-slate-600">Triangular scan</span>
          <span className="text-slate-400">Bellman–Ford over {tri.currencies ?? 0} currencies · {tri.pairs ?? 0} pairs</span>
          <span className="ml-auto">
            {tri.opportunity && tri.opportunity.positive ? (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-700">
                {tri.opportunity.path} · +{(tri.opportunity.net * 100).toFixed(3)}%
              </span>
            ) : (
              <span className="text-slate-400">no cycle clears fees</span>
            )}
          </span>
        </div>
      )}

      {cross && cross.enabled && (
        <div className="mt-2 flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2 text-[12px]">
          <ArrowLeftRight size={13} className="text-teal-500" />
          <span className="font-medium text-slate-600">Cross-exchange (Binance↔Bybit)</span>
          <span className="text-slate-400">{cross.scanned ?? 0} pairs · needs inventory on both (Growth tier)</span>
          <span className="ml-auto">
            {(cross.positive ?? 0) > 0 && cross.opportunities?.[0] ? (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-700">
                {cross.opportunities[0].symbol} +{(cross.opportunities[0].net * 100).toFixed(3)}%
              </span>
            ) : (
              <span className="text-slate-400">no spread clears fees</span>
            )}
          </span>
        </div>
      )}
    </Card>
  );
}
