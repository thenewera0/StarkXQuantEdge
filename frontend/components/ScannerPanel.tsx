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
            <Radar size={15} className="text-indigo-500" /> Autonomous Scanner
          </div>
          <div className="mt-0.5 text-xs text-slate-500">
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

      {error && <div className="mt-3 text-sm text-rose-600">{error}</div>}

      {result && (
        <div className="mt-4">
          <div className="mb-2 text-xs text-slate-500">
            Scanned <span className="font-semibold text-slate-700">{result.scanned}</span> pairs ·
            emitted <span className="font-semibold text-slate-700">{result.emitted}</span> actionable
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
                  className="flex items-center justify-between rounded-xl border border-slate-100 bg-white p-3 text-left transition hover:border-indigo-200 hover:bg-indigo-50/30"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-800">{s.symbol}</span>
                      <span className="text-[11px] text-slate-400">{s.interval}</span>
                      <RegimeBadge regime={s.regime} />
                    </div>
                    <div className="mt-1 flex items-center gap-1 text-[11px] text-slate-500">
                      {s.label.includes("Buy") ? <ArrowUpRight size={12} className="text-emerald-500" /> : <ArrowDownRight size={12} className="text-rose-500" />}
                      entry {s.entry} · tgt {s.target} · stop {s.stop}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <SignalBadge label={s.label} size="sm" />
                    <span className="text-[11px] tabular-nums text-slate-500">{s.confidence}%</span>
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
