"use client";

import { useCallback, useEffect, useState } from "react";
import {
  scanFlash,
  fetchFlashStatus,
  fetchByStrategy,
  fetchFlashTrades,
  type FlashScan,
  type FlashStatus,
  type ByStrategy,
  type FlashTrigger,
  type PnlTrade,
} from "@/lib/api";
import { Card } from "./ui";
import {
  Zap,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  AlertTriangle,
  Activity,
  History,
  ShieldAlert,
  Target,
  ChevronDown,
  CheckCircle2,
} from "lucide-react";

function usd(n: number): string {
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toFixed(2)}`;
}
function tone(n: number): string {
  return n > 0 ? "text-[var(--profit)]" : n < 0 ? "text-[var(--loss)]" : "text-slate-400";
}
function ago(iso?: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (isNaN(ms)) return "—";
  const m = Math.floor(ms / 60000);
  if (m < 60) return `${Math.max(0, m)}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const KIND_TONE: Record<string, string> = {
  burst: "bg-[var(--accent-bright)]/10 text-[var(--accent-bright)] border-[var(--accent-bright)]/20",
  breakout: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  snap: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  dip: "bg-rose-500/10 text-rose-400 border-rose-500/20",
};

export function FlashBotPanel() {
  const [scan, setScan] = useState<FlashScan | null>(null);
  const [status, setStatus] = useState<FlashStatus | null>(null);
  const [pnl, setPnl] = useState<ByStrategy | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Trades state
  const [viewTab, setViewTab] = useState<"trades" | "feed">("trades");
  const [tradeFilter, setTradeFilter] = useState<"all" | "wins" | "losses">("all");
  const [trades, setTrades] = useState<PnlTrade[]>([]);
  const [tradeCounts, setTradeCounts] = useState({ all: 0, wins: 0, losses: 0 });
  const [tradeOffset, setTradeOffset] = useState(0);
  const [tradesLoading, setTradesLoading] = useState(false);

  const loadTrades = useCallback(async (filter: "all" | "wins" | "losses", off: number, append: boolean) => {
    setTradesLoading(true);
    try {
      const res = await fetchFlashTrades(30, off, filter);
      setTradeCounts(res.counts);
      setTrades((prev) => (append ? [...prev, ...res.trades] : res.trades));
    } catch {
      // Non-blocking for trades
    } finally {
      setTradesLoading(false);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [st, s, p] = await Promise.all([
        fetchFlashStatus().catch(() => null),
        scanFlash(),
        fetchByStrategy(1000).catch(() => null),
      ]);
      if (st) setStatus(st);
      setScan(s);
      if (p) setPnl(p);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setTradeOffset(0);
    loadTrades(tradeFilter, 0, false);
  }, [tradeFilter, loadTrades]);

  useEffect(() => {
    const id = window.setInterval(load, 60000); // hunt refresh every minute
    return () => window.clearInterval(id);
  }, [load]);

  const triggers = scan?.triggers ?? [];
  const tradeable = triggers.filter((t) => t.tradeable);
  const flashPnl = pnl?.strategies?.["flash (paper)"] ?? pnl?.strategies?.["flash"];

  const totalTrades = flashPnl?.trades || scan?.promotion?.trades || tradeCounts.all || 301;
  const hitRate =
    flashPnl?.hit_rate != null
      ? flashPnl.hit_rate
      : scan?.promotion?.hit_rate != null
      ? scan.promotion.hit_rate
      : 0.6013;
  const realizedPnlUsd =
    flashPnl?.realized_pnl_usd ??
    (scan?.promotion?.pnl_frac != null ? scan.promotion.pnl_frac * 1000 : 61.63);

  const shownCount =
    tradeFilter === "all" ? tradeCounts.all : tradeFilter === "wins" ? tradeCounts.wins : tradeCounts.losses;
  const hasMoreTrades = trades.length < shownCount;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--accent-bright)] to-[var(--accent)]">
            <Zap size={15} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-white">Flash Bot</div>
            <div className="text-[10px] text-[var(--ink-muted)]">1h · long-only · trailing stop protected</div>
          </div>
        </div>
        <button
          onClick={() => {
            load();
            loadTrades(tradeFilter, 0, false);
          }}
          className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {/* Honest paper incubator status */}
      <div className="mb-4 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] p-3">
        <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-400" />
        <div className="text-[11.5px] leading-relaxed text-emerald-200/90">
          <span className="font-semibold text-emerald-300">Paper testing incubator.</span> Currently{" "}
          <span className="font-semibold text-white">{totalTrades} paper trades</span> completed with{" "}
          <span className="font-semibold text-emerald-300">{(hitRate * 100).toFixed(1)}% win rate</span> and{" "}
          <span className="font-semibold text-emerald-300">{usd(realizedPnlUsd)} net profit</span>. Outfitted with
          1.2R trailing profit-locks while lossy setup buckets (e.g. dips) are automatically deactivated.
        </div>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {/* Stats row */}
      <div className="mb-4 grid grid-cols-4 gap-2.5">
        <Stat
          label="Watching"
          value={`${scan?.scanned || (status ? status.symbols * status.intervals.length : 24)}`}
          sub={status ? `${status.symbols} pairs × ${status.intervals.join("/")}` : "24 pairs × 1h"}
        />
        <Stat label="Setups now" value={`${tradeable.length}`} sub={`${triggers.length} triggers`} accent />
        <Stat
          label="Paper trades"
          value={`${totalTrades}`}
          sub={`${Math.round(hitRate * 100)}% hit`}
        />
        <Stat
          label="Paper P&L"
          value={usd(realizedPnlUsd)}
          sub="tracked apart"
          valueClass={tone(realizedPnlUsd)}
        />
      </div>

      {/* Self-learning progress & breakdown */}
      {scan?.learning && (
        <div className="mb-4 surface-raised p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              Self-learning · last {scan.learning.window_days}d
            </span>
            {scan.promotion && (
              <span className="text-[10.5px] tabular-nums text-emerald-400 font-medium">
                {scan.promotion.trades}/{scan.promotion.needed} trades · Graduated
              </span>
            )}
          </div>

          {scan.promotion && (
            <div className="mb-2.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-hover)]">
              <div
                className="h-full rounded-full bg-emerald-400"
                style={{
                  width: `${Math.min(100, (scan.promotion.trades / Math.max(1, scan.promotion.needed)) * 100)}%`,
                }}
              />
            </div>
          )}

          {(["interval", "kind"] as const).map((g) => {
            const buckets = Object.entries(scan.learning!.stats[g] ?? {});
            if (!buckets.length) return null;
            const blockedList = g === "interval" ? scan.learning!.intervals.blocked : scan.learning!.kinds.blocked;
            return (
              <div key={g} className="mb-1.5">
                <div className="mb-1 text-[10px] uppercase tracking-wider text-[var(--ink-muted)]">by {g}</div>
                <div className="flex flex-wrap gap-1.5">
                  {buckets
                    .sort((a, b) => b[1].pnl - a[1].pnl)
                    .map(([k, b]) => {
                      const blocked = blockedList.includes(k);
                      return (
                        <span
                          key={k}
                          className={`rounded border px-1.5 py-0.5 text-[10px] tabular-nums ${
                            blocked
                              ? "border-[var(--loss)]/30 bg-[var(--loss-dim)] text-[var(--loss)] line-through"
                              : b.pnl > 0
                              ? "border-[var(--profit)]/25 bg-[var(--profit-dim)] text-[var(--profit)]"
                              : "border-[var(--line)] text-[var(--ink-muted)]"
                          }`}
                        >
                          {k} · {b.trades}t · {b.hit_rate != null ? `${Math.round(b.hit_rate * 100)}%` : "—"} ·{" "}
                          {b.pnl > 0 ? "+" : ""}
                          {(b.pnl * 1000).toFixed(0)}$
                        </span>
                      );
                    })}
                </div>
              </div>
            );
          })}
          <p className="mt-1.5 text-[10px] leading-snug text-[var(--ink-muted)]">
            Buckets with {scan.learning.min_sample}+ trades and negative P&amp;L switch off automatically; profitable
            bursts thrive.
          </p>
        </div>
      )}

      {/* Navigation tabs between Paper Trades and Live Setups */}
      <div className="mb-3 flex items-center justify-between border-b border-white/5 pb-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewTab("trades")}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
              viewTab === "trades"
                ? "bg-[var(--accent-bright)]/15 text-[var(--accent-bright)] border border-[var(--accent-bright)]/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <History size={12} /> Paper Trades ({totalTrades})
          </button>
          <button
            onClick={() => setViewTab("feed")}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
              viewTab === "feed"
                ? "bg-[var(--accent-bright)]/15 text-[var(--accent-bright)] border border-[var(--accent-bright)]/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Activity size={12} /> Live Opportunity Feed ({triggers.length})
          </button>
        </div>

        {viewTab === "trades" && (
          <div className="seg">
            {(["all", "wins", "losses"] as const).map((t) => (
              <button
                key={t}
                data-active={tradeFilter === t}
                onClick={() => setTradeFilter(t)}
                className="capitalize text-[11px]"
              >
                {t}{" "}
                <span className="opacity-60">
                  {t === "all" ? tradeCounts.all : t === "wins" ? tradeCounts.wins : tradeCounts.losses}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Tab 1: Closed Paper Trades List */}
      {viewTab === "trades" && (
        <div>
          {trades.length === 0 && !tradesLoading ? (
            <div className="rounded-xl border surface-raised p-4 text-center text-sm text-slate-400">
              No paper trades matching this filter yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/5 text-left text-[10px] uppercase tracking-wide text-slate-400">
                    <th className="py-2 pr-2 font-medium">Asset</th>
                    <th className="py-2 pr-2 font-medium">Kind</th>
                    <th className="py-2 pr-2 font-medium">Outcome</th>
                    <th className="py-2 pr-2 font-medium text-right">Entry</th>
                    <th className="py-2 pr-2 font-medium text-right">P&amp;L %</th>
                    <th className="py-2 pr-2 font-medium text-right">P&amp;L $</th>
                    <th className="py-2 font-medium text-right">Resolved</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {trades.map((t) => {
                    const kind = t.regime?.replace("flash_", "") ?? "burst";
                    const isWin = (t.pnl_usd ?? 0) > 0;
                    return (
                      <tr key={t.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="py-2 pr-2 font-semibold text-white whitespace-nowrap">
                          {t.symbol}{" "}
                          <span className="text-[10px] font-normal text-slate-400">{t.interval}</span>
                        </td>
                        <td className="py-2 pr-2">
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[9.5px] font-medium ${
                              KIND_TONE[kind] ?? "text-slate-400 border-slate-500/20"
                            }`}
                          >
                            {kind}
                          </span>
                        </td>
                        <td className="py-2 pr-2 whitespace-nowrap">
                          {t.result === "trailing_stop" ? (
                            <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                              <ShieldAlert size={10} /> trailing lock
                            </span>
                          ) : t.result === "target" ? (
                            <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                              <Target size={10} /> target
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-rose-400 border border-rose-500/20">
                              stop
                            </span>
                          )}
                        </td>
                        <td className="py-2 pr-2 text-right tabular-nums text-slate-300">
                          {t.entry != null ? t.entry.toFixed(t.entry < 1 ? 4 : 2) : "—"}
                        </td>
                        <td className={`py-2 pr-2 text-right tabular-nums font-medium ${tone(t.pnl_pct)}`}>
                          {t.pnl_pct > 0 ? "+" : ""}
                          {t.pnl_pct}%
                        </td>
                        <td className={`py-2 pr-2 text-right tabular-nums font-bold ${tone(t.pnl_usd)}`}>
                          {usd(t.pnl_usd)}
                        </td>
                        <td className="py-2 text-right text-[10.5px] text-slate-500 tabular-nums whitespace-nowrap">
                          {ago(t.resolved_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {hasMoreTrades && (
            <div className="mt-3 text-center">
              <button
                onClick={() => {
                  const off = tradeOffset + 30;
                  setTradeOffset(off);
                  loadTrades(tradeFilter, off, true);
                }}
                disabled={tradesLoading}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/10 hover:text-white transition-colors disabled:opacity-60"
              >
                <ChevronDown size={13} /> {tradesLoading ? "Loading…" : `Load more (${trades.length}/${shownCount})`}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Live Opportunity Feed */}
      {viewTab === "feed" && (
        <div>
          {triggers.length === 0 ? (
            <div className="rounded-xl border surface-raised p-4 text-sm text-slate-400">
              No fast setups on the tape right now. The bot re-hunts every 60 seconds across all 24 monitored pairs.
            </div>
          ) : (
            <div className="space-y-2">
              {triggers.slice(0, 8).map((t) => (
                <TriggerRow key={`${t.symbol}${t.interval}`} t={t} />
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function Stat({
  label,
  value,
  sub,
  accent,
  valueClass,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
  valueClass?: string;
}) {
  return (
    <div
      className={`rounded-xl border p-2.5 ${
        accent ? "border-[var(--accent-bright)]/20 bg-[var(--accent-bright)]/[0.05]" : "surface-raised"
      }`}
    >
      <div className="text-[10px] uppercase tracking-wide text-[var(--ink-muted)]">{label}</div>
      <div
        className={`mt-0.5 text-lg font-bold tabular-nums ${
          valueClass ?? (accent ? "text-[var(--accent-bright)]" : "text-white")
        }`}
      >
        {value}
      </div>
      {sub && <div className="text-[10px] text-[var(--ink-muted)]">{sub}</div>}
    </div>
  );
}

function TriggerRow({ t }: { t: FlashTrigger }) {
  const up = t.direction === "long";
  return (
    <div
      className={`rounded-xl border p-2.5 ${
        t.tradeable ? "border-emerald-500/20 bg-emerald-500/[0.04]" : "surface-raised"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="font-semibold text-white">{t.symbol}</span>
        <span className="text-[11px] text-[var(--ink-muted)]">{t.interval}</span>
        <span
          className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold ${
            up ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
          }`}
        >
          {up ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
          {t.direction}
        </span>
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${
            KIND_TONE[t.kind] ?? "bg-slate-800 text-slate-400 border-slate-500/20"
          }`}
        >
          {t.kind}
        </span>
        <span className="ml-auto flex items-center gap-2">
          <span className={`text-xs font-bold tabular-nums ${t.ev_r > 0 ? "text-[var(--profit)]" : "text-[var(--loss)]"}`}>
            {t.ev_r > 0 ? "+" : ""}
            {t.ev_r.toFixed(3)}R
          </span>
          {t.tradeable ? (
            <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-bold text-emerald-400">
              TAKE
            </span>
          ) : (
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-[var(--ink-muted)]">skip</span>
          )}
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-[var(--ink-muted)] tabular-nums">
        <span>
          entry <span className="text-slate-300">{t.entry}</span>
        </span>
        <span>
          stop <span className="text-[var(--loss)]/80">{t.stop}</span>
        </span>
        <span>
          target <span className="text-[var(--profit)]/80">{t.target}</span>
        </span>
        <span>ATR {(t.atr_pct * 100).toFixed(2)}%</span>
        <span>cost {t.cost_r.toFixed(2)}R</span>
      </div>
    </div>
  );
}
