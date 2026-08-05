"use client";

import { useCallback, useEffect, useState } from "react";
import { scanFlash, fetchFlashStatus, fetchByStrategy,
  type FlashScan, type FlashStatus, type ByStrategy, type FlashTrigger } from "@/lib/api";
import { Card } from "./ui";
import { Zap, RefreshCw, ArrowUpRight, ArrowDownRight, AlertTriangle, Activity } from "lucide-react";

function usd(n: number): string {
  const s = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${s}$${Math.abs(n).toFixed(2)}`;
}
function tone(n: number): string {
  return n > 0 ? "text-[var(--profit)]" : n < 0 ? "text-[var(--loss)]" : "text-slate-400";
}

const KIND_TONE: Record<string, string> = {
  burst: "bg-[var(--accent-bright)]/10 text-[var(--accent-bright)] border-[var(--accent-bright)]/20",
  breakout: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  snap: "bg-[var(--warn-dim)]0/10 text-[var(--warn)] border-amber-500/20",
};

export function FlashBotPanel() {
  const [scan, setScan] = useState<FlashScan | null>(null);
  const [status, setStatus] = useState<FlashStatus | null>(null);
  const [pnl, setPnl] = useState<ByStrategy | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [st, s, p] = await Promise.all([
        fetchFlashStatus().catch(() => null),
        scanFlash(),
        fetchByStrategy(1000).catch(() => null),
      ]);
      if (st) setStatus(st);
      setScan(s); if (p) setPnl(p); setError(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = window.setInterval(load, 60000);   // hunt refresh every minute
    return () => window.clearInterval(id);
  }, [load]);

  const triggers = scan?.triggers ?? [];
  const tradeable = triggers.filter((t) => t.tradeable);
  const flashPnl = pnl?.strategies?.["flash (paper)"] ?? pnl?.strategies?.["flash"];

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--accent-bright)] to-[var(--accent)]">
            <Zap size={15} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-white">Flash Bot</div>
            <div className="text-[10px] text-[var(--ink-muted)]">fast 15m / 1h momentum · breakout · snap</div>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Hunt
        </button>
      </div>

      {/* Honest status: paper until it proves an edge */}
      <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-500/20 bg-[var(--warn-dim)]0/[0.07] p-3">
        <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[var(--warn)]" />
        <div className="text-[11.5px] leading-relaxed text-amber-200/90">
          <span className="font-semibold text-amber-300">Running on paper.</span> A 2,791-trade backtest of these
          triggers (net of real fees) returned a 35% win rate and negative expectancy. It trades continuously here to
          build a live record — it moves to real capital only if that record turns genuinely profitable.
        </div>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {/* Stats row */}
      <div className="mb-4 grid grid-cols-4 gap-2.5">
        <Stat
          label="Watching"
          value={`${scan?.scanned ?? (status ? status.symbols * status.intervals.length : 0)}`}
          sub={status ? `${status.symbols} pairs × ${status.intervals.join("/")}` : "pairs × TF"}
        />
        <Stat label="Setups now" value={`${tradeable.length}`} sub={`${triggers.length} triggers`} accent />
        <Stat
          label="Paper trades"
          value={`${flashPnl?.trades ?? scan?.stats?.trades ?? status?.stats?.trades ?? 0}`}
          sub={
            flashPnl?.hit_rate != null ? `${Math.round(flashPnl.hit_rate * 100)}% hit`
            : scan?.stats?.hit_rate != null ? `${Math.round(scan.stats.hit_rate * 100)}% hit`
            : "—"
          }
        />
        <Stat label="Paper P&L" value={usd(flashPnl?.realized_pnl_usd ?? 0)} sub="tracked apart" valueClass={tone(flashPnl?.realized_pnl_usd ?? 0)} />
      </div>

      {/* What the bot has learned from its OWN trades, and progress toward real capital */}
      {scan?.learning && (
        <div className="mb-4 surface-raised p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              Self-learning · last {scan.learning.window_days}d
            </span>
            {scan.promotion && (
              <span className="text-[10.5px] tabular-nums text-[var(--ink-muted)]">
                {scan.promotion.trades}/{scan.promotion.needed} trades to graduate
              </span>
            )}
          </div>

          {scan.promotion && (
            <div className="mb-2.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-hover)]">
              <div className="h-full rounded-full bg-[var(--accent)]"
                style={{ width: `${Math.min(100, (scan.promotion.trades / Math.max(1, scan.promotion.needed)) * 100)}%` }} />
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
                  {buckets.sort((a, b) => b[1].pnl - a[1].pnl).map(([k, b]) => {
                    const blocked = blockedList.includes(k);
                    return (
                      <span key={k}
                        className={`rounded border px-1.5 py-0.5 text-[10px] tabular-nums ${
                          blocked ? "border-[var(--loss)]/30 bg-[var(--loss-dim)] text-[var(--loss)] line-through"
                            : b.pnl > 0 ? "border-[var(--profit)]/25 bg-[var(--profit-dim)] text-[var(--profit)]"
                              : "border-[var(--line)] text-[var(--ink-muted)]"}`}>
                        {k} · {b.trades}t · {b.hit_rate != null ? `${Math.round(b.hit_rate * 100)}%` : "—"} · {b.pnl > 0 ? "+" : ""}{(b.pnl * 1000).toFixed(0)}$
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
          <p className="mt-1.5 text-[10px] leading-snug text-[var(--ink-muted)]">
            Buckets with {scan.learning.min_sample}+ trades and negative P&amp;L switch off automatically;
            thin ones keep exploring so the bot can still discover what works.
          </p>
        </div>
      )}

      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
        <Activity size={12} /> Live opportunity feed
      </div>

      {triggers.length === 0 ? (
        <div className="rounded-xl border surface-raised p-4 text-sm text-slate-400">
          No fast setups on the tape right now. The bot re-hunts every 5 minutes.
        </div>
      ) : (
        <div className="space-y-2">
          {triggers.slice(0, 8).map((t) => <TriggerRow key={`${t.symbol}${t.interval}`} t={t} />)}
        </div>
      )}
    </Card>
  );
}

function Stat({ label, value, sub, accent, valueClass }: { label: string; value: string; sub?: string; accent?: boolean; valueClass?: string }) {
  return (
    <div className={`rounded-xl border p-2.5 ${accent ? "border-[var(--accent-bright)]/20 bg-[var(--accent-bright)]/[0.05]" : "surface-raised"}`}>
      <div className="text-[10px] uppercase tracking-wide text-[var(--ink-muted)]">{label}</div>
      <div className={`mt-0.5 text-lg font-bold tabular-nums ${valueClass ?? (accent ? "text-[var(--accent-bright)]" : "text-white")}`}>{value}</div>
      {sub && <div className="text-[10px] text-[var(--ink-muted)]">{sub}</div>}
    </div>
  );
}

function TriggerRow({ t }: { t: FlashTrigger }) {
  const up = t.direction === "long";
  return (
    <div className={`rounded-xl border p-2.5 ${t.tradeable ? "border-emerald-500/20 bg-[var(--profit-dim)]0/[0.04]" : "surface-raised"}`}>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="font-semibold text-white">{t.symbol}</span>
        <span className="text-[11px] text-[var(--ink-muted)]">{t.interval}</span>
        <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-semibold ${up ? "bg-[var(--profit-dim)]0/10 text-[var(--profit)]" : "bg-[var(--loss-dim)]0/10 text-[var(--loss)]"}`}>
          {up ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}{t.direction}
        </span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${KIND_TONE[t.kind] ?? "bg-[var(--surface-raised)]0/10 text-slate-400 border-slate-500/20"}`}>{t.kind}</span>
        <span className="ml-auto flex items-center gap-2">
          <span className={`text-xs font-bold tabular-nums ${t.ev_r > 0 ? "text-[var(--profit)]" : "text-[var(--loss)]"}`}>
            {t.ev_r > 0 ? "+" : ""}{t.ev_r.toFixed(3)}R
          </span>
          {t.tradeable
            ? <span className="rounded bg-[var(--profit-dim)]0/15 px-1.5 py-0.5 text-[10px] font-bold text-[var(--profit)]">TAKE</span>
            : <span className="rounded bg-[var(--surface-raised)]0/10 px-1.5 py-0.5 text-[10px] text-[var(--ink-muted)]">skip</span>}
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-[var(--ink-muted)] tabular-nums">
        <span>entry <span className="text-slate-300">{t.entry}</span></span>
        <span>stop <span className="text-[var(--loss)]/80">{t.stop}</span></span>
        <span>target <span className="text-[var(--profit)]/80">{t.target}</span></span>
        <span>ATR {(t.atr_pct * 100).toFixed(2)}%</span>
        <span>cost {t.cost_r.toFixed(2)}R</span>
      </div>
    </div>
  );
}
