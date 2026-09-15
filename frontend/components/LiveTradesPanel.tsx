"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchLiveTrades, closeTrade, type LiveTrades, type LiveTrade } from "@/lib/api";
import { Card } from "./ui";
import { Radio, RefreshCw, ArrowUpRight, ArrowDownRight, Zap, Target, ShieldAlert, CheckCircle2 } from "lucide-react";

function usd(n: number): string {
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toFixed(2)}`;
}
function tone(n: number): string {
  return n > 0 ? "text-[var(--profit)]" : n < 0 ? "text-[var(--loss)]" : "text-slate-400";
}
function ago(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h` : `${Math.floor(h / 24)}d`;
}

export function LiveTradesPanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const [d, setD] = useState<LiveTrades | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setD(await fetchLiveTrades(1000, "core")); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);
  // Live refresh every 20s so P&L actually moves.
  useEffect(() => {
    const id = window.setInterval(load, 20000);
    return () => window.clearInterval(id);
  }, [load]);

  const trades = d?.trades ?? [];
  const live = trades.filter((t) => !t.paper);

  return (
    <Card className="card-pad" >
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio size={16} className="text-[var(--accent-bright)]" />
          <span className="text-sm font-semibold tracking-tight text-white">Running Trades</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--profit-dim)]0/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--profit)] border border-emerald-500/20">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> LIVE
          </span>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {/* Floating P&L summary - Core Real Capital */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        <div className="rounded-xl border surface-raised p-3">
          <div className="text-[10px] uppercase tracking-wide text-[var(--ink-muted)]">Open positions</div>
          <div className="mt-1 text-xl font-bold tabular-nums text-white">{d?.count ?? live.length}</div>
          <div className="text-[10px] text-[var(--ink-muted)]">real capital execution</div>
        </div>
        <div className="rounded-xl border surface-raised p-3">
          <div className="text-[10px] uppercase tracking-wide text-[var(--ink-muted)]">Floating P&L</div>
          <div className={`mt-1 text-xl font-bold tabular-nums ${tone(d?.open_pnl_usd ?? 0)}`}>{usd(d?.open_pnl_usd ?? 0)}</div>
          <div className="text-[10px] text-[var(--ink-muted)]">marked to live price</div>
        </div>
        <div className="rounded-xl border surface-raised p-3">
          <div className="text-[10px] uppercase tracking-wide text-[var(--ink-muted)]">Active Capital Risk</div>
          <div className="mt-1 text-xl font-bold tabular-nums text-emerald-400">
            {(d?.count ?? live.length) > 0 ? `$${((d?.count ?? live.length) * 1000).toLocaleString()}` : "$0"}
          </div>
          <div className="text-[10px] text-[var(--ink-muted)]">$1,000/trade fixed risk</div>
        </div>
      </div>

      {(d?.unpriced ?? 0) > 0 && (
        <div className="mb-3 rounded-xl border border-[var(--warn)]/25 bg-[var(--warn-dim)] p-2.5 text-[11px] text-[var(--ink-secondary)]">
          {d?.unpriced} open position{(d?.unpriced ?? 0) > 1 ? "s have" : " has"} no live quote right now.
          They are listed below without a mark rather than hidden &mdash; an open risk is never dropped
          from this view just because a price feed is unavailable.
        </div>
      )}

      {trades.length === 0 && (
        <div className="rounded-xl border surface-raised p-4 text-sm text-slate-400">
          No positions open right now. The engine opens a trade when a setup clears its expected-value bar.
        </div>
      )}

      <div className="space-y-2">
        {trades.map((t) => <TradeRow key={t.id} t={t} onClose={load} />)}
      </div>
    </Card>
  );
}

function TradeRow({ t, onClose }: { t: LiveTrade; onClose: () => void }) {
  const [closing, setClosing] = useState(false);
  const up = t.direction === "long";
  const prog = Math.max(-100, Math.min(100, t.progress_pct ?? 0));
  const isProfit = (t.pnl_usd ?? 0) > 0;

  const handleClose = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (closing) return;
    const confirmMsg = isProfit
      ? `Lock in profit on ${t.symbol} now? (Current floating P&L: ${usd(t.pnl_usd ?? 0)})`
      : `Close ${t.symbol} position now at market? (Current P&L: ${usd(t.pnl_usd ?? 0)})`;
    if (!window.confirm(confirmMsg)) return;

    setClosing(true);
    try {
      await closeTrade(t.id);
      onClose();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to close trade");
    } finally {
      setClosing(false);
    }
  };

  return (
    <div className="rounded-xl border surface-raised p-3 transition-colors hover:bg-[var(--surface-hover)]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold text-white">{t.symbol}</span>
        <span className="text-[11px] text-[var(--ink-muted)]">{t.interval}</span>
        <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold ${up ? "bg-[var(--profit-dim)]0/10 text-[var(--profit)]" : "bg-[var(--loss-dim)]0/10 text-[var(--loss)]"}`}>
          {up ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}{t.direction}
        </span>
        {t.strategy === "flash" && (
          <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold bg-[var(--accent-bright)]/10 text-[var(--accent-bright)] border border-[var(--accent-bright)]/20">
            <Zap size={10} /> flash
          </span>
        )}
        {t.paper && <span className="rounded bg-[var(--warn-dim)]0/10 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--warn)] border border-amber-500/20">PAPER</span>}
        <span className="ml-auto text-right">
          <span className={`text-base font-bold tabular-nums ${tone(t.pnl_usd ?? 0)}`}>
            {t.priced ? usd(t.pnl_usd ?? 0) : "—"}
          </span>
          {t.priced && t.pnl_pct != null && (
            <span className={`ml-2 text-xs tabular-nums ${tone(t.pnl_pct)}`}>
              {t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct}%
            </span>
          )}
        </span>
      </div>

      {/* progress toward target */}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={`h-full rounded-full transition-all ${prog >= 0 ? "bg-emerald-400" : "bg-rose-400"}`}
          style={{ width: `${Math.abs(prog)}%`, marginLeft: prog >= 0 ? 0 : "auto" }}
        />
      </div>

      <div className="mt-2.5 flex items-center justify-between pt-1 border-t border-white/[0.04]">
        <div className="flex flex-wrap gap-x-3.5 gap-y-1 text-[11px] text-[var(--ink-muted)] tabular-nums">
          <span>entry <span className="text-slate-300">{t.entry}</span></span>
          <span>now <span className="text-white font-medium">{t.priced ? t.price : "no quote"}</span></span>
          {t.stop != null && <span className="flex items-center gap-0.5"><ShieldAlert size={10} className="text-[var(--loss)]" />{t.stop}</span>}
          {t.target != null && <span className="flex items-center gap-0.5"><Target size={10} className="text-[var(--profit)]" />{t.target}</span>}
          {t.r_multiple != null && <span>{t.r_multiple > 0 ? "+" : ""}{t.r_multiple}R</span>}
          <span>{ago(t.opened_at)} ago</span>
        </div>
        <button
          onClick={handleClose}
          disabled={closing}
          className={`ml-2 shrink-0 inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-semibold transition-all cursor-pointer ${
            isProfit
              ? "bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/30"
              : "bg-slate-700/40 text-slate-300 hover:bg-slate-700/60 border border-slate-600/30"
          }`}
          title="Immediately book profit or close this trade at current live market price"
        >
          {closing ? (
            <RefreshCw size={10} className="animate-spin" />
          ) : isProfit ? (
            <>
              <CheckCircle2 size={10} />
              <span>Take Profit</span>
            </>
          ) : (
            <span>Close</span>
          )}
        </button>
      </div>
    </div>
  );
}
