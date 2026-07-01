"use client";

import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  createChart,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { fetchCandles } from "@/lib/api";

type Props = { symbol: string; interval: string; market: string };

export function PriceChart({ symbol, interval, market }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let chart: IChartApi | null = null;
    let cancelled = false;

    fetchCandles(symbol, interval, market)
      .then((data) => {
        if (cancelled || !containerRef.current) return;
        setError(null);
        chart = createChart(containerRef.current, {
          autoSize: true,
          height: 340,
          layout: {
            background: { type: ColorType.Solid, color: "#ffffff" },
            textColor: "#64748b",
            fontFamily: "var(--font-sans)",
          },
          grid: {
            vertLines: { color: "#f1f5f9" },
            horzLines: { color: "#f1f5f9" },
          },
          rightPriceScale: { borderColor: "#e2e8f0" },
          timeScale: { borderColor: "#e2e8f0", timeVisible: true, secondsVisible: false },
          crosshair: { mode: 1 },
        });

        const candle = chart.addSeries(CandlestickSeries, {
          upColor: "#10b981",
          downColor: "#f43f5e",
          borderVisible: false,
          wickUpColor: "#10b981",
          wickDownColor: "#f43f5e",
        });
        candle.setData(
          data.candles.map((c) => ({ ...c, time: c.time as UTCTimestamp })),
        );

        const addLine = (pts: { time: number; value: number }[], color: string, width: 1 | 2) => {
          if (!chart || !pts.length) return;
          const s = chart.addSeries(LineSeries, {
            color,
            lineWidth: width,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          s.setData(pts.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
        };
        addLine(data.ema50, "#6366f1", 2);
        addLine(data.ema200, "#94a3b8", 1);
        addLine(data.ut_stop, "#f59e0b", 1);

        chart.timeScale().fitContent();
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Chart failed");
      });

    return () => {
      cancelled = true;
      if (chart) chart.remove();
    };
  }, [symbol, interval, market]);

  return (
    <div className="card card-pad">
      <div className="mb-2 flex items-center justify-between px-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Price</span>
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
