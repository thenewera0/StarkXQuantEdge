"use client";

import { useEffect, useState } from "react";
import { fetchTrade, type TradeDetail } from "@/lib/api";
import { FactorBar } from "./FactorBar";
import { SignalBadge, RegimeBadge, TierBadge } from "./ui";
import { X, ArrowUpRight, ArrowDownRight, Brain, Target, ShieldAlert, LogIn } from "lucide-react";

const FACTORS: { key: string; label: string }[] = [
  { key: "trend", label: "trend" }, { key: "momentum", label: "momentum" },
  { key: "volatility", label: "vol / liquidity" }, { key: "structure", label: "mean-rev" },
  { key: "flow", label: "derivatives" }, { key: "sentiment", label: "sentiment" },
  { key: "macro", label: "macro" }, { key: "consensus", label: "on-chain" },
];

function num(n: number | null | undefined, d = 2): string {
  return n == null ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: d });
}

export function TradeDetailModal({ id, onClose }: { id: number; onClose: () => void }) {
  const [t, setT] = useState<TradeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTrade(id).then(setT).catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, [id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const o = t?.outcome;
  const pnlPct = o?.pnl_frac != null ? o.pnl_frac * 100 : null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="card mt-8 w-full max-w-2xl rounded-2xl p-6" onClick={(e) => e.stopPropagation()}>
        {!t && !error && <div className="py-10 text-center text-sm text-slate-400">Loading trade…</div>}
        {error && <div className="py-6 text-center text-sm text-rose-600">{error}</div>}

        {t && (
          <>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xl font-semibold tracking-tight">{t.symbol}</span>
                  <span className="text-xs text-slate-400">{t.interval}</span>
                  <RegimeBadge regime={t.regime} />
                  <TierBadge tier={t.tier ?? undefined} />
                </div>
                <div className="mt-0.5 text-xs text-slate-500">
                  Signal #{t.id} · {new Date(t.as_of).toLocaleString()}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <SignalBadge label={t.label} />
                <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X size={18} /></button>
              </div>
            </div>

            {/* Outcome banner */}
            {o && (
              <div className={`mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl p-3 ${o.result === "target" ? "bg-emerald-50" : o.result === "stop" ? "bg-rose-50" : "bg-slate-50"}`}>
                <span className={`text-sm font-semibold ${o.result === "target" ? "text-emerald-700" : o.result === "stop" ? "text-rose-700" : "text-slate-600"}`}>
                  Outcome: {o.result}
                </span>
                <div className="flex items-center gap-4 text-xs text-slate-600">
                  <span>P&L <span className={`font-semibold ${(pnlPct ?? 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>{pnlPct != null ? `${pnlPct > 0 ? "+" : ""}${pnlPct.toFixed(2)}%` : "—"}</span></span>
                  <span>MFE <span className="text-emerald-600">{o.mfe != null ? `${(o.mfe * 100).toFixed(1)}%` : "—"}</span></span>
                  <span>MAE <span className="text-rose-600">{o.mae != null ? `${(o.mae * 100).toFixed(1)}%` : "—"}</span></span>
                  <span>{o.bars_held} bars</span>
                </div>
              </div>
            )}

            {/* Trade plan */}
            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-400">
                <span className="flex items-center gap-1">{t.direction === "long" ? <ArrowUpRight size={13} className="text-emerald-500" /> : <ArrowDownRight size={13} className="text-rose-500" />}<span className="capitalize">{t.direction}</span> plan</span>
                <span className="flex gap-2 normal-case text-slate-500">{t.reward_risk != null && <span className="rounded bg-emerald-50 px-1.5 py-0.5 font-medium text-emerald-600">{t.reward_risk}R</span>}{t.size_pct != null && <span>risk {t.size_pct}%</span>}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Tile icon={<LogIn size={12} />} label="Entry" value={t.entry} />
                <Tile icon={<ShieldAlert size={12} />} label="Stop" value={t.stop} tone="risk" />
                <Tile icon={<Target size={12} />} label="Target 1" value={t.targets[0]} tone="reward" />
                {t.targets[1] != null && <Tile icon={<Target size={12} />} label="Target 2" value={t.targets[1]} tone="reward" />}
                {t.targets[2] != null && <Tile icon={<Target size={12} />} label="Target 3" value={t.targets[2]} tone="reward" />}
              </div>
              {t.invalidation && <div className="mt-2 text-[11px] text-slate-500">Invalidation: <span className="font-medium text-slate-600">{t.invalidation}</span></div>}
            </div>

            {/* Confluence numbers */}
            <div className="mt-4 grid grid-cols-4 gap-2 text-center">
              <Stat label="Composite" value={t.composite != null ? (t.composite > 0 ? `+${num(t.composite)}` : num(t.composite)) : "—"} />
              <Stat label="Confidence" value={t.confidence != null ? `${num(t.confidence, 0)}%` : "—"} />
              <Stat label="Conviction" value={t.conviction != null ? `${num(t.conviction, 0)}` : "—"} />
              <Stat label="Agreement" value={t.agreement != null ? `${(t.agreement * 100).toFixed(0)}%` : "—"} />
            </div>

            {/* Factor breakdown */}
            <div className="mt-4">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Why it fired — 8 factor families</div>
              <div className="grid gap-x-6 gap-y-0.5 sm:grid-cols-2">
                {FACTORS.map((f) => <FactorBar key={f.key} label={f.label} value={t.factors[f.key] ?? null} />)}
              </div>
            </div>

            {t.psychology && t.psychology !== "no crowd extreme" && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-indigo-100 bg-indigo-50/40 p-3 text-sm text-slate-700">
                <Brain size={15} className="mt-0.5 text-indigo-500" /><span><span className="font-medium text-indigo-600">Positioning:</span> {t.psychology}</span>
              </div>
            )}

            {t.rationale && (
              <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">AI thesis</div>
                <p className="text-sm leading-relaxed text-slate-700">{t.rationale}</p>
              </div>
            )}

            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-3 text-[11px] text-slate-500">
              {t.price != null && <span>signal price: <span className="font-medium text-slate-600">{num(t.price)}</span></span>}
              {t.atr != null && <span>ATR: <span className="font-medium text-slate-600">{num(t.atr)}</span></span>}
              {o?.resolved_at && <span>resolved: <span className="font-medium text-slate-600">{new Date(o.resolved_at).toLocaleString()}</span></span>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Tile({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: number | null | undefined; tone?: "risk" | "reward" }) {
  const c = tone === "risk" ? "text-rose-600" : tone === "reward" ? "text-emerald-600" : "text-slate-900";
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-2.5">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-slate-400"><span className="text-slate-300">{icon}</span>{label}</div>
      <div className={`mt-0.5 text-sm font-semibold tabular-nums ${c}`}>{value != null ? value.toLocaleString() : "—"}</div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-sm font-semibold tabular-nums text-slate-800">{value}</div>
    </div>
  );
}
