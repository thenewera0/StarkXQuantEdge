"use client";

import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { fetchCandles } from "@/lib/api";

type Props = { symbol: string; interval: string; market: string };

const REFRESH_MS = 15000; // live poll cadence

export function PriceChart({ symbol, interval, market }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let chart: IChartApi | null = null;
    let candle: ISeriesApi<"Candlestick"> | null = null;
    let ema50: ISeriesApi<"Line"> | null = null;
    let ema200: ISeriesApi<"Line"> | null = null;
    let ut: ISeriesApi<"Line"> | null = null;
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const asTs = (t: number) => t as UTCTimestamp;

    async function refresh(first: boolean) {
      try {
        const data = await fetchCandles(symbol, interval, market);
        if (cancelled) return;
        if (!chart && containerRef.current) {
          chart = createChart(containerRef.current, {
            autoSize: true,
            height: 340,
            layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#64748b", fontFamily: "var(--font-sans)" },
            grid: { vertLines: { color: "#f1f5f9" }, horzLines: { color: "#f1f5f9" } },
            rightPriceScale: { borderColor: "#e2e8f0" },
            timeScale: { borderColor: "#e2e8f0", timeVisible: true, secondsVisible: false },
            crosshair: { mode: 1 },
          });
          candle = chart.addSeries(CandlestickSeries, {
            upColor: "#10b981", downColor: "#f43f5e", borderVisible: false,
            wickUpColor: "#10b981", wickDownColor: "#f43f5e",
          });
          ema50 = chart.addSeries(LineSeries, { color: "#6366f1", lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
          ema200 = chart.addSeries(LineSeries, { color: "#94a3b8", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
          ut = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        }
        candle?.setData(data.candles.map((c) => ({ ...c, time: asTs(c.time) })));
        ema50?.setData(data.ema50.map((p) => ({ time: asTs(p.time), value: p.value })));
        ema200?.setData(data.ema200.map((p) => ({ time: asTs(p.time), value: p.value })));
        ut?.setData(data.ut_stop.map((p) => ({ time: asTs(p.time), value: p.value })));
        if (first) chart?.timeScale().fitContent();
        setError(null);
        setUpdatedAt(new Date());
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Chart failed");
      }
    }

    refresh(true);
    timer = setInterval(() => refresh(false), REFRESH_MS);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      if (chart) chart.remove();
    };
  }, [symbol, interval, market]);

  return (
    <div className="card card-pad">
      <div className="mb-2 flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Price</span>
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-600">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" /> LIVE
          </span>
          {updatedAt && <span className="text-[10px] text-slate-400">{updatedAt.toLocaleTimeString()}</span>}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <Legend color="#6366f1" label="EMA50" />
          <Legend color="#94a3b8" label="EMA200" />
          <Legend color="#f59e0b" label="UT Bot stop" />
        </div>
      </div>
      {error ? (
        <div className="px-1 py-8 text-center text-sm text-slate-400">{error}</div>
      ) : (
        <div ref={containerRef} className="h-[340px] w-full" />
      )}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
