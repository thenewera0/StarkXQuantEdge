"use client";

import { useState } from "react";
import { runScan, type EmittedSignal, type ScanResult } from "@/lib/api";
import { Card, SignalBadge, RegimeBadge } from "./ui";
import { Radar, ArrowDownRight, ArrowUpRight } from "lucide-react";

type Props = {
  onPick?: (s: EmittedSignal) => void;
  onScanned?: () => void;
};

export function ScannerPanel({ onPick, onScanned }: Props) {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function scan() {
    setScanning(true);
    setError(null);
    try {
      const r = await runScan();
      setResult(r);
      onScanned?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  }

  return (
    <Card className="card-pad">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5 text-sm font-semibold tracking-tight">
            <Radar size={15} className="text-[var(--accent-bright)]" /> Autonomous Scanner
          </div>
          <div className="mt-0.5 text-xs text-[var(--ink-muted)]">
            Sweeps popular crypto &amp; forex pairs, logs actionable signals, then the resolver verifies and the model self-improves. Runs automatically every 30 min.
          </div>
        </div>
        <button
          onClick={scan}
          disabled={scanning}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:opacity-60"
        >
          <Radar size={15} className={scanning ? "shimmer" : ""} />
          {scanning ? "Scanning pairs…" : "Scan now"}
        </button>
      </div>

      {error && <div className="mt-3 text-sm text-[var(--loss)]">{error}</div>}

      {result && (
        <div className="mt-4">
          <div className="mb-2 text-xs text-[var(--ink-muted)]">
            Scanned <span className="font-semibold text-[var(--ink-secondary)]">{result.scanned}</span> pairs ·
            emitted <span className="font-semibold text-[var(--ink-secondary)]">{result.emitted}</span> actionable
            (conf ≥ {result.min_confidence})
          </div>
          {result.signals.length === 0 ? (
            <div className="py-3 text-center text-sm text-slate-400">No actionable signals right now.</div>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {result.signals.map((s, i) => (
                <button
                  key={s.id ?? i}
                  onClick={() => onPick?.(s)}
                  className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-raised)] p-3 text-left transition hover:border-indigo-200 hover:bg-[var(--accent-dim)]/30"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[var(--ink)]">{s.symbol}</span>
                      <span className="text-[11px] text-slate-400">{s.interval}</span>
                      <RegimeBadge regime={s.regime} />
                    </div>
                    <div className="mt-1 flex items-center gap-1 text-[11px] text-[var(--ink-muted)]">
                      {s.label.includes("Buy") ? <ArrowUpRight size={12} className="text-emerald-500" /> : <ArrowDownRight size={12} className="text-rose-500" />}
                      entry {s.entry} · tgt {s.target} · stop {s.stop}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <SignalBadge label={s.label} size="sm" />
                    <span className="text-[11px] tabular-nums text-[var(--ink-muted)]">{s.confidence}%</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
