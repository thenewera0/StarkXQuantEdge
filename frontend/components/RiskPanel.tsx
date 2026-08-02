"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchRiskExposure, type RiskExposure } from "@/lib/api";
import { Card } from "./ui";
import { Shield, RefreshCw, AlertTriangle, TrendingDown } from "lucide-react";

const usd = (n: number) =>
  `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function RiskPanel({ refreshKey }: { refreshKey?: number }) {
  const [r, setR] = useState<RiskExposure | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setR(await fetchRiskExposure()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  const over = !!r && r.gross_used > r.gross_ceiling;
  const usedPct = r ? Math.min(100, (r.gross_used / Math.max(r.gross_ceiling, 0.01)) * 100) : 0;
  const throttled = !!r && r.throttle < 1;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className={`flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br ${
            over ? "from-[var(--loss)] to-[var(--warn)]"
                 : "from-[var(--accent-bright)] to-[var(--accent)]"}`}>
            <Shield size={16} className="text-white" />
          </span>
          <div>
            <h3 className="text-[13.5px] font-semibold text-[var(--ink)]">Risk & Exposure</h3>
            <p className="text-[11px] text-[var(--ink-muted)]">
              Capital is the limit, not the position count
            </p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-xs text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {r && (
        <>
          {/* Gross exposure against its ceiling */}
          <div className="mb-4">
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
                Gross exposure
              </span>
              <span className={`text-[13px] font-bold tabular-nums ${over ? "text-[var(--loss)]" : "text-[var(--ink)]"}`}>
                {r.gross_used.toFixed(2)}x
                <span className="ml-1 text-[11px] font-normal text-[var(--ink-muted)]">
                  / {r.gross_ceiling.toFixed(1)}x ceiling
                </span>
              </span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-[var(--surface-raised)]">
              <div
                style={{ width: `${usedPct}%` }}
                className={over ? "h-full bg-[var(--loss)]" : "h-full bg-[var(--accent-bright)]"}
              />
            </div>
            <div className="mt-1.5 flex justify-between text-[10.5px] tabular-nums text-[var(--ink-muted)]">
              <span>{usd(r.open_notional_usd)} of notional open</span>
              <span>{usd(r.remaining_usd)} still available</span>
            </div>
          </div>

          {over && (
            <div className="mb-3 flex items-start gap-2 rounded-xl border border-[var(--loss)]/30 bg-[var(--loss-dim)] p-3">
              <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[var(--loss)]" />
              <p className="text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
                <b className="text-[var(--loss)]">Over the ceiling.</b> These positions were opened before the
                exposure limit existed. Each one individually &ldquo;risks&rdquo; only a small percent, but that is
                only true if the stop fills at the stop price &mdash; a gap through it costs far more at{" "}
                {r.gross_used.toFixed(1)}x. No new risk will be added until these close.
              </p>
            </div>
          )}

          {throttled && (
            <div className="mb-3 flex items-start gap-2 rounded-xl border border-[var(--warn)]/25 bg-[var(--warn-dim)] p-3">
              <TrendingDown size={15} className="mt-0.5 shrink-0 text-[var(--warn)]" />
              <p className="text-[11.5px] leading-relaxed text-[var(--ink-secondary)]">
                <b className="text-[var(--warn)]">De-risked by drawdown.</b> Equity is below its high-water
                mark of {usd(r.high_water_usd)}, so the exposure budget is throttled to{" "}
                <b>{(r.throttle * 100).toFixed(0)}%</b>. It restores itself as equity recovers.
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Stat label="Equity" value={usd(r.equity_usd)} />
            <Stat label="Open" value={`${r.open_positions} / ${r.max_concurrent}`} />
            <Stat label="Per class max" value={`${r.class_cap}`} />
            <Stat
              label="Can open"
              value={r.can_open ? "Yes" : "No"}
              tone={r.can_open ? "good" : "bad"}
            />
          </div>

          {Object.keys(r.open_by_market).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] text-[var(--ink-muted)]">
              {Object.entries(r.open_by_market).map(([m, n]) => (
                <span key={m} className="capitalize">
                  {m} {n}
                  {n >= r.class_cap && <span className="text-[var(--warn)]"> (full)</span>}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </Card>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  const colour =
    tone === "good" ? "text-[var(--profit)]" : tone === "bad" ? "text-[var(--loss)]" : "text-[var(--ink)]";
  return (
    <div className="surface-raised rounded-xl px-3 py-2.5">
      <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">{label}</div>
      <div className={`mt-0.5 text-lg font-bold tabular-nums ${colour}`}>{value}</div>
    </div>
  );
}
