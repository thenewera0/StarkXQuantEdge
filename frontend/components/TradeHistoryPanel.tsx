"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchTrades, type PnlTrade } from "@/lib/api";
import { Card } from "./ui";
import { TradeDetailModal } from "./TradeDetailModal";
import { History, Search, ChevronDown } from "lucide-react";

type Tab = "all" | "wins" | "losses";
const PAGE = 50;

function usd(n: number): string {
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
function tone(n: number): string {
  return n > 0 ? "text-emerald-600" : n < 0 ? "text-rose-600" : "text-slate-600";
}

export function TradeHistoryPanel({ refreshKey }: { refreshKey: number }) {
  const [tab, setTab] = useState<Tab>("all");
  const [rows, setRows] = useState<PnlTrade[]>([]);
  const [counts, setCounts] = useState({ all: 0, wins: 0, losses: 0 });
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const load = useCallback(async (t: Tab, off: number, append: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetchTrades(t, PAGE, off);
      setCounts(r.counts);
      setRows((prev) => (append ? [...prev, ...r.trades] : r.trades));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { setOffset(0); load(tab, 0, false); }, [tab, load, refreshKey]);

  const shown = tab === "all" ? counts.all : tab === "wins" ? counts.wins : counts.losses;
  const hasMore = rows.length < shown;

  return (
    <Card className="card-pad">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <History size={16} className="text-indigo-500" />
          <span className="text-sm font-semibold tracking-tight">Trade History</span>
          <span className="text-xs text-slate-400">click any trade for full details</span>
        </div>
        <div className="seg">
          {(["all", "wins", "losses"] as Tab[]).map((t) => (
            <button key={t} data-active={tab === t} onClick={() => setTab(t)} className="capitalize">
              {t} <span className="opacity-60">{t === "all" ? counts.all : t === "wins" ? counts.wins : counts.losses}</span>
            </button>
          ))}
        </div>
      </div>

      {error && <div className="mb-2 text-sm text-rose-600">{error}</div>}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400">
              <th className="py-1.5 pr-3 font-medium">Asset</th>
              <th className="py-1.5 pr-3 font-medium">Dir</th>
              <th className="py-1.5 pr-3 font-medium">Regime</th>
              <th className="py-1.5 pr-3 font-medium">Result</th>
              <th className="py-1.5 pr-3 font-medium text-right">P&amp;L %</th>
              <th className="py-1.5 pr-3 font-medium text-right">P&amp;L $</th>
              <th className="py-1.5 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t, i) => (
              <tr key={t.id ?? i} onClick={() => t.id && setOpenId(t.id)}
                  className={`group border-t border-slate-100 ${t.id ? "cursor-pointer hover:bg-indigo-50/40" : ""}`}>
                <td className="py-2 pr-3 font-medium text-slate-800">{t.symbol} <span className="text-[11px] text-slate-400">{t.interval}</span></td>
                <td className="py-2 pr-3 capitalize text-slate-500">{t.direction}</td>
                <td className="py-2 pr-3 text-[11px] capitalize text-slate-400">{t.regime?.replace("_", " ") ?? "—"}</td>
                <td className="py-2 pr-3"><span className={t.result === "target" ? "text-emerald-600" : t.result === "stop" ? "text-rose-600" : "text-slate-500"}>{t.result}</span></td>
                <td className={`py-2 pr-3 text-right tabular-nums ${tone(t.pnl_pct)}`}>{t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct}%</td>
                <td className={`py-2 pr-3 text-right font-medium tabular-nums ${tone(t.pnl_usd)}`}>{usd(t.pnl_usd)}</td>
                <td className="py-2 text-right">{t.id && <Search size={13} className="ml-auto text-slate-300 group-hover:text-indigo-500" />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && !loading && <div className="py-4 text-center text-sm text-slate-400">No trades in this view yet.</div>}

      {hasMore && (
        <div className="mt-3 text-center">
          <button onClick={() => { const off = offset + PAGE; setOffset(off); load(tab, off, true); }}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-60">
            <ChevronDown size={14} /> {loading ? "Loading…" : `Load more (${rows.length}/${shown})`}
          </button>
        </div>
      )}

      {openId != null && <TradeDetailModal id={openId} onClose={() => setOpenId(null)} />}
    </Card>
  );
}
