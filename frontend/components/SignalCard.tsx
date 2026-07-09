import type { Signal } from "@/lib/api";
import { FactorBar } from "./FactorBar";
import { Card, Ring, RegimeBadge, SignalBadge, TierBadge, signalTone } from "./ui";
import { ArrowDownRight, ArrowUpRight, Target, ShieldAlert, LogIn, Brain, Activity, MinusCircle } from "lucide-react";

// Display order + on-chain relabel (the 'consensus' slot now carries on-chain F6).
const CATEGORIES: { key: keyof Signal["categories"]; label: string }[] = [
  { key: "trend", label: "trend" },
  { key: "momentum", label: "momentum" },
  { key: "volatility", label: "vol / liquidity" },
  { key: "structure", label: "mean-rev" },
  { key: "flow", label: "derivatives" },
  { key: "sentiment", label: "sentiment" },
  { key: "macro", label: "macro" },
  { key: "consensus", label: "on-chain" },
];

export function SignalCard({ s, livePrice }: { s: Signal; livePrice?: number | null }) {
  const lv = s.levels;
  const silenced = s.actionable === false;
  const delta = livePrice != null && s.price ? (livePrice - s.price) / s.price : null;

  return (
    <Card className="card-pad">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xl font-semibold tracking-tight">{s.symbol}</span>
            <RegimeBadge regime={s.regime} />
            <TierBadge tier={s.tier} />
            {s.strategy === "range-fade" && (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-600">FADE</span>
            )}
          </div>
          <div className="mt-0.5 text-xs text-slate-500">
            {s.interval} · {new Date(s.as_of).toLocaleString()}
          </div>
          {livePrice != null && (
            <div className="mt-1.5 flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-600">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" /> LIVE
              </span>
              <span className="text-lg font-semibold tabular-nums text-slate-900">
                {livePrice.toLocaleString(undefined, { maximumFractionDigits: livePrice >= 100 ? 2 : 6 })}
              </span>
              {delta != null && (
                <span className={`text-xs font-medium tabular-nums ${delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                  {delta >= 0 ? "+" : ""}{(delta * 100).toFixed(2)}% since signal
                </span>
              )}
            </div>
          )}
        </div>
        <SignalBadge label={s.label} size="lg" />
      </div>

      {silenced && (
        <div className="mt-4 flex items-center gap-2 rounded-xl border border-slate-100 bg-slate-50/70 p-3 text-sm text-slate-500">
          <MinusCircle size={16} className="text-slate-400" />
          <span>
            No actionable trade — <span className="font-medium text-slate-600">{(s.silence_reason ?? "").replace(/_/g, " ")}</span>.
            Silence is a position; the engine only fires when regime, evidence, and risk geometry align.
          </span>
        </div>
      )}

      {/* Composite + confidence */}
      <div className="mt-5 flex items-center gap-6">
        <Ring value={s.confidence} label="conf" color={s.composite >= 0 ? "#10b981" : "#f43f5e"} size={84} />
        <div className="flex-1">
          <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
            <span>Confluence {s.agreement != null && <span className="text-slate-400">· {Math.round(s.agreement * 100)}% agree</span>}</span>
            <span className="font-semibold tabular-nums text-slate-800">{s.composite > 0 ? `+${s.composite}` : s.composite}</span>
          </div>
          <div className="relative h-2.5 w-full rounded-full bg-gradient-to-r from-rose-200 via-slate-100 to-emerald-200">
            <div className="absolute left-1/2 top-0 h-full w-px bg-slate-300" />
            <div className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow"
              style={{ left: `${((Math.max(-100, Math.min(100, s.composite)) + 100) / 200) * 100}%`, background: signalTone(s.label).includes("emerald") ? "#10b981" : signalTone(s.label).includes("rose") ? "#f43f5e" : "#64748b" }} />
          </div>
          {/* Calibrated edge: honest win probability + expected value net of cost */}
          {(s.win_prob != null || s.ev_r != null) && (
            <div className="mt-2 flex items-center gap-4 text-[11px]">
              {s.win_prob != null && (
                <span className="text-slate-500">calibrated win prob{" "}
                  <span className="font-semibold tabular-nums text-slate-800">{Math.round(s.win_prob * 100)}%</span>
                </span>
              )}
              {s.ev_r != null && (
                <span className="text-slate-500">edge (EV){" "}
                  <span className={`font-semibold tabular-nums ${s.ev_r > 0 ? "text-emerald-600" : "text-rose-600"}`}>
                    {s.ev_r > 0 ? "+" : ""}{s.ev_r.toFixed(2)}R
                  </span>
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Trade plan (only when actionable) */}
      {!silenced && lv.direction !== "flat" && (
        <div className="mt-5">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Trade plan</span>
            <span className="flex items-center gap-2 text-[11px] text-slate-500">
              {s.reward_risk != null && <span className="rounded bg-emerald-50 px-1.5 py-0.5 font-medium text-emerald-600">{s.reward_risk}R</span>}
              {s.size_pct != null && <span>risk {s.size_pct}%</span>}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Tile icon={<LogIn size={13} />} label="Entry" value={lv.entry} tone="ink"
              badge={<span className="inline-flex items-center gap-0.5 text-[11px] font-medium capitalize text-slate-500">
                {lv.direction === "long" ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{lv.direction}</span>} />
            <Tile icon={<ShieldAlert size={13} />} label="Stop" value={lv.stop} tone="risk" />
            <Tile icon={<Target size={13} />} label="Target 1" value={s.targets?.[0] ?? lv.target} tone="reward" />
            <Tile icon={<Target size={13} />} label="Target 2" value={s.targets?.[1] ?? null} tone="reward" />
            <Tile icon={<Target size={13} />} label="Target 3" value={s.targets?.[2] ?? null} tone="reward" />
          </div>
          {s.invalidation && <div className="mt-2 text-[11px] text-slate-500">Invalidation: <span className="font-medium text-slate-600">{s.invalidation}</span></div>}
        </div>
      )}

      {/* Psychology */}
      {s.psychology && s.psychology !== "no crowd extreme" && (
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-indigo-100 bg-indigo-50/40 p-3">
          <Brain size={15} className="mt-0.5 text-indigo-500" />
          <div className="text-sm text-slate-700"><span className="font-medium text-indigo-600">Positioning:</span> {s.psychology}</div>
        </div>
      )}

      {/* Factor breakdown */}
      <div className="mt-6">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Confluence breakdown (8 families)</div>
        <div className="grid gap-x-6 gap-y-0.5 sm:grid-cols-2">
          {CATEGORIES.map((c) => <FactorBar key={c.key} label={c.label} value={s.categories[c.key]} />)}
        </div>
      </div>

      {/* Rationale */}
      {s.explanation && (
        <div className="mt-6 rounded-xl border border-slate-100 bg-slate-50/70 p-4">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Thesis</span>
            <span className="text-[10px] text-slate-400">{s.explanation.source === "openrouter" ? s.explanation.model : "deterministic fallback"}</span>
          </div>
          <p className="text-sm leading-relaxed text-slate-700">{s.explanation.rationale}</p>
        </div>
      )}

      {/* Market context strip */}
      <div className="mt-5 flex flex-wrap gap-x-5 gap-y-1 border-t border-slate-100 pt-4 text-[11px] text-slate-500">
        {s.fear_greed?.value != null && <Ctx label="F&G" value={`${s.fear_greed.value} (${s.fear_greed.classification})`} />}
        {s.derivatives?.funding_rate != null && <Ctx label="Funding" value={`${(s.derivatives.funding_rate * 100).toFixed(3)}%`} />}
        {s.derivatives?.long_short_ratio != null && <Ctx label="L/S" value={s.derivatives.long_short_ratio.toFixed(2)} />}
        {s.derivatives?.oi_change != null && <Ctx label="OI 4h" value={`${(s.derivatives.oi_change * 100).toFixed(2)}%`} />}
        {s.macro?.btc_dominance != null && <Ctx label="BTC dom" value={`${s.macro.btc_dominance}%`} />}
        {s.onchain && s.onchain.available === false && <Ctx label="On-chain" value="n/a" />}
      </div>

      <p className="mt-3 flex items-center gap-1 text-[11px] leading-snug text-slate-400">
        <Activity size={11} /> {s.disclaimer}
      </p>
    </Card>
  );
}

function Tile({ icon, label, value, tone, badge }: { icon: React.ReactNode; label: string; value: number | null | undefined; tone: "ink" | "risk" | "reward"; badge?: React.ReactNode }) {
  const color = tone === "risk" ? "text-rose-600" : tone === "reward" ? "text-emerald-600" : "text-slate-900";
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-slate-400"><span className="text-slate-300">{icon}</span>{label}</div>
        {badge}
      </div>
      <div className={`mt-1 text-base font-semibold tabular-nums ${color}`}>{value != null ? value.toLocaleString() : "—"}</div>
    </div>
  );
}

function Ctx({ label, value }: { label: string; value: string }) {
  return <span><span className="text-slate-400">{label}:</span> <span className="font-medium text-slate-600">{value}</span></span>;
}
