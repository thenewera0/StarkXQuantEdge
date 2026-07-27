"use client";

import type { ReactNode } from "react";

/** Shared panel chrome so every surface in the app speaks one visual language. */
export function Panel({
  icon, title, subtitle, action, children, className = "", accent,
}: {
  icon?: ReactNode; title: string; subtitle?: string; action?: ReactNode;
  children: ReactNode; className?: string; accent?: boolean;
}) {
  return (
    <section className={`card ${className}`}>
      <header className="flex items-start justify-between gap-3 border-b border-[rgba(255,255,255,0.06)] px-5 py-3.5">
        <div className="flex items-center gap-2.5 min-w-0">
          {icon && (
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
              accent ? "bg-gradient-to-br from-[#00d4ff] to-[#0066ff] text-white" : "bg-white/[0.06] text-[#00d4ff]"}`}>
              {icon}
            </span>
          )}
          <div className="min-w-0">
            <h3 className="truncate text-[13.5px] font-semibold tracking-tight text-white">{title}</h3>
            {subtitle && <p className="truncate text-[11px] text-slate-500">{subtitle}</p>}
          </div>
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </header>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

/** Page-level heading for a view. */
export function ViewHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[26px] font-bold leading-tight tracking-tight text-white">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function EmptyState({ icon, title, hint }: { icon?: ReactNode; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[rgba(255,255,255,0.08)] bg-white/[0.015] px-6 py-10 text-center">
      {icon && <span className="text-slate-600">{icon}</span>}
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {hint && <p className="max-w-sm text-[12px] leading-relaxed text-slate-500">{hint}</p>}
    </div>
  );
}

/** Compact KPI used across views — one consistent metric treatment. */
export function Kpi({
  label, value, sub, tone = "neutral", size = "md",
}: {
  label: string; value: string; sub?: string;
  tone?: "neutral" | "good" | "bad" | "accent"; size?: "sm" | "md" | "lg";
}) {
  const toneCls = tone === "good" ? "text-emerald-400" : tone === "bad" ? "text-rose-400"
    : tone === "accent" ? "text-[#00d4ff]" : "text-white";
  const sizeCls = size === "lg" ? "text-3xl" : size === "sm" ? "text-base" : "text-xl";
  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-white/[0.02] px-3.5 py-3">
      <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1 font-bold tabular-nums leading-none ${sizeCls} ${toneCls}`}>{value}</div>
      {sub && <div className="mt-1 text-[10.5px] text-slate-500">{sub}</div>}
    </div>
  );
}
