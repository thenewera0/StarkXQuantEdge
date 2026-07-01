import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function SectionTitle({ icon, title, hint }: { icon?: ReactNode; title: string; hint?: string }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      {icon && <span className="text-slate-400">{icon}</span>}
      <h2 className="text-sm font-semibold tracking-tight text-slate-800">{title}</h2>
      {hint && <span className="text-xs text-slate-400">· {hint}</span>}
    </div>
  );
}

const SIGNAL_TONE: Record<string, string> = {
  "Strong Buy": "bg-emerald-600",
  Buy: "bg-emerald-500",
  Neutral: "bg-slate-400",
  Sell: "bg-rose-500",
  "Strong Sell": "bg-rose-600",
};

export function signalTone(label: string): string {
  return SIGNAL_TONE[label] ?? "bg-slate-400";
}

export function SignalBadge({ label, size = "md" }: { label: string; size?: "sm" | "md" | "lg" }) {
  const pad = size === "lg" ? "px-4 py-1.5 text-base" : size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm";
  return <span className={`inline-flex items-center rounded-full font-semibold text-white ${signalTone(label)} ${pad}`}>{label}</span>;
}

// Circular progress ring for confidence/conviction.
export function Ring({ value, label, color = "#4f46e5", size = 72 }: { value: number; label?: string; color?: string; size?: number }) {
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  const dash = (pct / 100) * c;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#eceff5" strokeWidth={6} fill="none" />
        <circle
          cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={6} fill="none"
          strokeDasharray={`${dash} ${c}`} strokeLinecap="round"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-sm font-semibold tabular-nums text-slate-800">{Math.round(pct)}</span>
        {label && <span className="text-[9px] uppercase tracking-wide text-slate-400">{label}</span>}
      </div>
    </div>
  );
}

const REGIME_STYLE: Record<string, string> = {
  trending: "bg-indigo-50 text-indigo-600 border-indigo-100",
  choppy: "bg-amber-50 text-amber-600 border-amber-100",
  high_vol: "bg-rose-50 text-rose-600 border-rose-100",
};

export function RegimeBadge({ regime }: { regime?: string | null }) {
  if (!regime) return null;
  const style = REGIME_STYLE[regime] ?? "bg-slate-50 text-slate-500 border-slate-100";
  return (
    <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium capitalize ${style}`}>
      {regime.replace("_", " ")}
    </span>
  );
}

const TIER_STYLE: Record<string, string> = {
  high: "bg-violet-100 text-violet-700",
  standard: "bg-indigo-50 text-indigo-600",
  watch: "bg-amber-50 text-amber-600",
  no_trade: "bg-slate-100 text-slate-400",
};

export function TierBadge({ tier }: { tier?: string }) {
  if (!tier) return null;
  const style = TIER_STYLE[tier] ?? "bg-slate-100 text-slate-500";
  return (
    <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${style}`}>
      {tier.replace("_", " ")}
    </span>
  );
}
