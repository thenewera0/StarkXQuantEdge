import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function SectionTitle({ icon, title, hint }: { icon?: ReactNode; title: string; hint?: string }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      {icon && <span className="text-slate-400">{icon}</span>}
      <h2 className="text-sm font-semibold tracking-tight text-white">{title}</h2>
      {hint && <span className="text-xs text-[var(--ink-muted)]">· {hint}</span>}
    </div>
  );
}

const SIGNAL_TONE: Record<string, string> = {
  "Strong Buy": "bg-[var(--profit-dim)]0/20 text-[var(--profit)] border border-emerald-500/30",
  Buy: "bg-[var(--profit-dim)]0/10 text-[var(--profit)] border border-emerald-500/20",
  Neutral: "bg-[var(--surface-raised)]0/10 text-slate-400 border border-slate-500/20",
  Sell: "bg-[var(--loss-dim)]0/10 text-[var(--loss)] border border-rose-500/20",
  "Strong Sell": "bg-[var(--loss-dim)]0/20 text-[var(--loss)] border border-rose-500/30",
};

export function signalTone(label: string): string {
  return SIGNAL_TONE[label] ?? "bg-[var(--surface-raised)]0/10 text-slate-400 border border-slate-500/20";
}

export function SignalBadge({ label, size = "md" }: { label: string; size?: "sm" | "md" | "lg" }) {
  const pad = size === "lg" ? "px-4 py-1.5 text-base" : size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm";
  return <span className={`inline-flex items-center rounded-full font-semibold shadow-sm ${signalTone(label)} ${pad}`}>{label}</span>;
}

// Circular progress ring for confidence/conviction.
export function Ring({ value, label, color = "var(--accent-bright)", size = 72 }: { value: number; label?: string; color?: string; size?: number }) {
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  const dash = (pct / 100) * c;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90 drop-shadow-[0_0_8px_rgba(0,212,255,0.4)]">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,0.05)" strokeWidth={6} fill="none" />
        <circle
          cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={6} fill="none"
          strokeDasharray={`${dash} ${c}`} strokeLinecap="round"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-sm font-bold tabular-nums text-white text-glow">{Math.round(pct)}</span>
        {label && <span className="text-[9px] uppercase tracking-wide text-[var(--accent-bright)] mt-0.5">{label}</span>}
      </div>
    </div>
  );
}

const REGIME_STYLE: Record<string, string> = {
  trending: "bg-[var(--accent)]/10 text-[var(--accent-bright)] border-[var(--accent-bright)]/30",
  choppy: "bg-[var(--warn-dim)]0/10 text-[var(--warn)] border-amber-500/30",
  high_vol: "bg-[var(--loss-dim)]0/10 text-[var(--loss)] border-rose-500/30",
};

export function RegimeBadge({ regime }: { regime?: string | null }) {
  if (!regime) return null;
  const style = REGIME_STYLE[regime] ?? "bg-[var(--surface-raised)]0/10 text-slate-400 border-slate-500/30";
  return (
    <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium capitalize ${style}`}>
      {regime.replace("_", " ")}
    </span>
  );
}

const TIER_STYLE: Record<string, string> = {
  high: "bg-violet-500/20 text-violet-300 border border-violet-500/30",
  standard: "bg-[var(--accent)]/20 text-[var(--accent-bright)] border border-[var(--accent-bright)]/30",
  watch: "bg-[var(--warn-dim)]0/10 text-[var(--warn)] border border-amber-500/20",
  no_trade: "bg-slate-800 text-slate-400 border border-slate-700",
};

export function TierBadge({ tier }: { tier?: string }) {
  if (!tier) return null;
  const style = TIER_STYLE[tier] ?? "bg-slate-800 text-slate-400 border border-slate-700";
  return (
    <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide shadow-sm ${style}`}>
      {tier.replace("_", " ")}
    </span>
  );
}
