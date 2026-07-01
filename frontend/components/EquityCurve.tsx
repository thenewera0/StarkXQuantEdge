"use client";

import type { EquityPoint } from "@/lib/api";

/** Lightweight SVG cumulative-P&L curve. Green fill above 0, red below. */
export function EquityCurve({ points, height = 140 }: { points: EquityPoint[]; height?: number }) {
  if (!points || points.length < 2) {
    return <div className="py-8 text-center text-xs text-slate-400">Equity curve appears once trades close.</div>;
  }

  const W = 600;
  const H = height;
  const pad = 8;
  const ys = points.map((p) => p.cum_pnl_usd);
  const min = Math.min(0, ...ys);
  const max = Math.max(0, ...ys);
  const range = max - min || 1;
  const n = points.length;

  const x = (i: number) => pad + (i / (n - 1)) * (W - 2 * pad);
  const y = (v: number) => pad + (1 - (v - min) / range) * (H - 2 * pad);
  const zeroY = y(0);

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.cum_pnl_usd).toFixed(1)}`).join(" ");
  const area = `${line} L ${x(n - 1).toFixed(1)} ${zeroY.toFixed(1)} L ${x(0).toFixed(1)} ${zeroY.toFixed(1)} Z`;
  const last = ys[ys.length - 1];
  const positive = last >= 0;
  const stroke = positive ? "#10b981" : "#f43f5e";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} preserveAspectRatio="none">
      <defs>
        <linearGradient id="eqfill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.20" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <line x1={pad} y1={zeroY} x2={W - pad} y2={zeroY} stroke="#e2e8f0" strokeWidth="1" strokeDasharray="3 3" />
      <path d={area} fill="url(#eqfill)" />
      <path d={line} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(n - 1)} cy={y(last)} r="3.5" fill={stroke} stroke="#fff" strokeWidth="1.5" />
    </svg>
  );
}
