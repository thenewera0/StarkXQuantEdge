"use client";

import { useCallback, useEffect, useState } from "react";
import { scanFundingCarry, type FundingScan } from "@/lib/api";
import { Card } from "./ui";
import { Repeat, RefreshCw, CheckCircle2 } from "lucide-react";

function pct(n: number, d = 2): string {
  return `${(n * 100).toFixed(d)}%`;
}

export function ArbPanel() {
  const [scan, setScan] = useState<FundingScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setScan(await scanFundingCarry()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (scan && !scan.enabled) return null;
  const opps = scan?.opportunities ?? [];

  return (
    <Card className="card-pad">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Repeat size={16} className="text-teal-500" />
          <span className="text-sm font-semibold tracking-tight">Funding-carry scan (delta-neutral arbitrage)</span>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800">
          <RefreshCw size={12} className={loading ? "shimmer" : ""} /> Rescan
        </button>
      </div>

      <p className="mb-3 text-[11px] leading-snug text-slate-500">
        Long spot + short perp, harvesting funding. Enters only when forecast funding (AR-1) clears the
        round-trip cost of both legs. Usually silent — it pays mainly during funding spikes.
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
            {opps.map((o) => (
              <tr key={o.symbol} className="border-t border-slate-100">
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
    </Card>
  );
}
