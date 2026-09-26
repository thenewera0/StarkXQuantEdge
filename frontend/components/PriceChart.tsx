"use client";

import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Compass,
  Layers,
  ShieldAlert,
  SlidersHorizontal,
  Target,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { fetchCandles, type Candles, type PriceActionData } from "@/lib/api";

type Props = {
  symbol: string;
  interval: string;
  market: string;
  onPrice?: (p: number) => void;
};

const OVERLAY_REFRESH_MS = 30000;

export function PriceChart({ symbol, interval, market, onPrice }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema50Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema200Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const utRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const priceLinesRef = useRef<any[]>([]);
  const lastDataRef = useRef<Candles | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<"ws" | "poll">("poll");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [priceAction, setPriceAction] = useState<PriceActionData | null>(null);

  // Chart feature toggles
  const [showSR, setShowSR] = useState<boolean>(true);
  const [showMarkers, setShowMarkers] = useState<boolean>(true);
  const [showIndicators, setShowIndicators] = useState<boolean>(true);
  const [showHud, setShowHud] = useState<boolean>(true);

  // Sync S/R price lines
  const updateSRLines = (pa: PriceActionData | null, candle: ISeriesApi<"Candlestick"> | null) => {
    if (!candle) return;
    // Clear existing price lines
    priceLinesRef.current.forEach((line) => {
      try {
        candle.removePriceLine(line);
      } catch {
        /* noop */
      }
    });
    priceLinesRef.current = [];

    if (!showSR || !pa) return;

    // Draw Support Zones
    (pa.support_zones || []).slice(0, 4).forEach((zone) => {
      try {
        const line = candle.createPriceLine({
          price: zone.price,
          color: "rgba(16, 185, 129, 0.85)", // emerald
          lineWidth: zone.strength >= 3 ? 2 : 1,
          lineStyle: zone.strength >= 3 ? LineStyle.Solid : LineStyle.Dashed,
          axisLabelVisible: true,
          title: `SUP ${zone.touches}x ($${zone.price < 1 ? zone.price.toFixed(4) : zone.price.toFixed(2)})`,
        });
        priceLinesRef.current.push(line);
      } catch {
        /* noop */
      }
    });

    // Draw Resistance Zones
    (pa.resistance_zones || []).slice(0, 4).forEach((zone) => {
      try {
        const line = candle.createPriceLine({
          price: zone.price,
          color: "rgba(244, 63, 94, 0.85)", // rose
          lineWidth: zone.strength >= 3 ? 2 : 1,
          lineStyle: zone.strength >= 3 ? LineStyle.Solid : LineStyle.Dashed,
          axisLabelVisible: true,
          title: `RES ${zone.touches}x ($${zone.price < 1 ? zone.price.toFixed(4) : zone.price.toFixed(2)})`,
        });
        priceLinesRef.current.push(line);
      } catch {
        /* noop */
      }
    });
  };

  // Sync pattern markers
  const updateMarkers = (pa: PriceActionData | null) => {
    if (!markersPluginRef.current) return;
    if (!showMarkers || !pa || !pa.chart_markers || pa.chart_markers.length === 0) {
      try {
        markersPluginRef.current.setMarkers([]);
      } catch {
        /* noop */
      }
      return;
    }

    try {
      const markers = pa.chart_markers.map((m) => ({
        time: m.time as UTCTimestamp,
        position: m.position,
        color: m.color,
        shape: m.shape,
        text: m.text,
      }));
      markersPluginRef.current.setMarkers(markers);
    } catch {
      /* noop */
    }
  };

  // Re-apply toggles whenever showSR or showMarkers change
  useEffect(() => {
    updateSRLines(priceAction, candleSeriesRef.current);
  }, [showSR, priceAction]);

  useEffect(() => {
    updateMarkers(priceAction);
  }, [showMarkers, priceAction]);

  useEffect(() => {
    ema50Ref.current?.applyOptions({ visible: showIndicators });
    ema200Ref.current?.applyOptions({ visible: showIndicators });
    utRef.current?.applyOptions({ visible: showIndicators });
  }, [showIndicators]);

  // Main Chart & WebSocket lifecycle
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let chart: IChartApi | null = null;
    let candle: ISeriesApi<"Candlestick"> | null = null;
    let ema50: ISeriesApi<"Line"> | null = null;
    let ema200: ISeriesApi<"Line"> | null = null;
    let ut: ISeriesApi<"Line"> | null = null;

    let cancelled = false;
    let overlayTimer: ReturnType<typeof setInterval> | null = null;
    let ws: WebSocket | null = null;
    let wsRetry: ReturnType<typeof setTimeout> | null = null;

    const asTs = (t: number) => t as UTCTimestamp;
    const isCrypto = market.toLowerCase() === "crypto";

    async function loadRest(first: boolean) {
      try {
        const data = await fetchCandles(symbol, interval, market);
        if (cancelled) return;
        lastDataRef.current = data;

        if (!chart && containerRef.current) {
          chart = createChart(containerRef.current, {
            autoSize: true,
            height: 360,
            layout: {
              background: { type: ColorType.Solid, color: "#0d1322" },
              textColor: "#94a3b8",
              fontFamily: "var(--font-sans), system-ui, sans-serif",
            },
            grid: {
              vertLines: { color: "#1c253c" },
              horzLines: { color: "#1c253c" },
            },
            rightPriceScale: {
              borderColor: "#2e3a5c",
              autoScale: true,
            },
            timeScale: {
              borderColor: "#2e3a5c",
              timeVisible: true,
              secondsVisible: false,
            },
            crosshair: { mode: 1 },
          });
          chartRef.current = chart;

          candle = chart.addSeries(CandlestickSeries, {
            upColor: "#10b981",
            downColor: "#f43f5e",
            borderVisible: false,
            wickUpColor: "#10b981",
            wickDownColor: "#f43f5e",
          });
          candleSeriesRef.current = candle;
          markersPluginRef.current = createSeriesMarkers(candle, []);

          ema50 = chart.addSeries(LineSeries, {
            color: "#6366f1",
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            visible: showIndicators,
          });
          ema50Ref.current = ema50;

          ema200 = chart.addSeries(LineSeries, {
            color: "#94a3b8",
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            visible: showIndicators,
          });
          ema200Ref.current = ema200;

          ut = chart.addSeries(LineSeries, {
            color: "#f59e0b",
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            visible: showIndicators,
          });
          utRef.current = ut;
        }

        candle?.setData(data.candles.map((c) => ({ ...c, time: asTs(c.time) })));
        ema50?.setData(data.ema50.map((p) => ({ time: asTs(p.time), value: p.value })));
        ema200?.setData(data.ema200.map((p) => ({ time: asTs(p.time), value: p.value })));
        ut?.setData(data.ut_stop.map((p) => ({ time: asTs(p.time), value: p.value })));

        if (data.candles.length) {
          onPrice?.(data.candles[data.candles.length - 1].close);
        }

        if (data.price_action) {
          setPriceAction(data.price_action);
          updateSRLines(data.price_action, candle);
          updateMarkers(data.price_action);
        }

        if (first) {
          chart?.timeScale().fitContent();
        }

        setError(null);
        setUpdatedAt(new Date());
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Chart failed");
      }
    }

    function openWs() {
      if (!isCrypto || cancelled) return;
      const stream = `${symbol.toLowerCase()}@kline_${interval}`;
      ws = new WebSocket(`wss://stream.binance.com:9443/ws/${stream}`);
      ws.onopen = () => {
        if (!cancelled) setLive("ws");
      };
      ws.onmessage = (ev) => {
        if (cancelled || !candle) return;
        try {
          const k = JSON.parse(ev.data).k;
          if (!k) return;
          const bar = {
            time: asTs(Math.floor(k.T / 1000)),
            open: parseFloat(k.o),
            high: parseFloat(k.h),
            low: parseFloat(k.l),
            close: parseFloat(k.c),
          };
          candle.update(bar);
          onPrice?.(bar.close);
          setUpdatedAt(new Date());
        } catch {
          /* ignore malformed frame */
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        setLive("poll");
        wsRetry = setTimeout(openWs, 3000);
      };
      ws.onerror = () => {
        try {
          ws?.close();
        } catch {
          /* noop */
        }
      };
    }

    loadRest(true).then(() => openWs());
    overlayTimer = setInterval(() => loadRest(false), OVERLAY_REFRESH_MS);

    return () => {
      cancelled = true;
      if (overlayTimer) clearInterval(overlayTimer);
      if (wsRetry) clearTimeout(wsRetry);
      if (ws) {
        ws.onclose = null;
        try {
          ws.close();
        } catch {
          /* noop */
        }
      }
      if (markersPluginRef.current) {
        try {
          markersPluginRef.current.detach();
        } catch {
          /* noop */
        }
        markersPluginRef.current = null;
      }
      if (chart) {
        chart.remove();
        chartRef.current = null;
        candleSeriesRef.current = null;
      }
    };
  }, [symbol, interval, market, onPrice]);

  return (
    <div className="card card-pad space-y-3">
      {/* Header & Controls Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-y-2 px-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
            {symbol} <span className="text-slate-400 font-normal">{interval}</span>
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-[var(--profit-dim)] px-2 py-0.5 text-[10px] font-semibold text-[var(--profit)] border border-[var(--profit)]/20">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--profit)]" />
            {live === "ws" ? "STREAM" : "POLL"}
          </span>
          {updatedAt && (
            <span className="text-[10px] text-slate-400 font-mono">
              {updatedAt.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Feature Toggles */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <button
            onClick={() => setShowSR(!showSR)}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-colors border ${
              showSR
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                : "bg-white/5 text-slate-400 border-white/10 hover:bg-white/10"
            }`}
            title="Toggle Support and Resistance Levels"
          >
            <Layers size={12} /> S/R Zones
            {priceAction?.support_zones?.length ? (
              <span className="text-[10px] opacity-80">
                ({priceAction.support_zones.length + priceAction.resistance_zones.length})
              </span>
            ) : null}
          </button>

          <button
            onClick={() => setShowMarkers(!showMarkers)}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-colors border ${
              showMarkers
                ? "bg-indigo-500/15 text-indigo-400 border-indigo-500/30"
                : "bg-white/5 text-slate-400 border-white/10 hover:bg-white/10"
            }`}
            title="Toggle Candlestick Pattern Markers & Liquidity Sweeps"
          >
            <Zap size={12} /> Patterns
            {priceAction?.patterns?.length ? (
              <span className="text-[10px] opacity-80">({priceAction.patterns.length})</span>
            ) : null}
          </button>

          <button
            onClick={() => setShowIndicators(!showIndicators)}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-colors border ${
              showIndicators
                ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                : "bg-white/5 text-slate-400 border-white/10 hover:bg-white/10"
            }`}
            title="Toggle EMA50, EMA200, UT Bot Stop"
          >
            <SlidersHorizontal size={12} /> EMAs
          </button>

          <button
            onClick={() => setShowHud(!showHud)}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-colors border ${
              showHud
                ? "bg-blue-500/15 text-blue-400 border-blue-500/30"
                : "bg-white/5 text-slate-400 border-white/10 hover:bg-white/10"
            }`}
            title="Toggle Price Action Intelligence HUD"
          >
            <Compass size={12} /> PA Intel
          </button>
        </div>
      </div>

      {/* Price Action Intelligence HUD */}
      {showHud && priceAction && (
        <div className="rounded-xl border border-white/10 bg-[#0b101c]/90 p-2.5 backdrop-blur shadow-sm space-y-2">
          {/* Top Row: Bias, Structure, and Score */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2">
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                Price Action:
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wide border ${
                  priceAction.bias === "bullish"
                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                    : priceAction.bias === "bearish"
                    ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
                    : "bg-slate-500/15 text-slate-300 border-slate-500/30"
                }`}
              >
                {priceAction.bias === "bullish" ? (
                  <TrendingUp size={13} />
                ) : priceAction.bias === "bearish" ? (
                  <TrendingDown size={13} />
                ) : (
                  <Activity size={13} />
                )}
                {priceAction.bias} ({priceAction.score > 0 ? "+" : ""}
                {priceAction.score.toFixed(0)})
              </span>

              <span className="rounded bg-white/5 px-2 py-0.5 text-[11px] font-medium text-slate-300 border border-white/10">
                Structure:{" "}
                <span className="text-white capitalize">
                  {priceAction.market_structure?.trend?.replace(/_/g, " ") || "ranging"}
                </span>
              </span>
            </div>

            {/* Rejection / Trap Diagnosis */}
            {priceAction.last_candle && (
              <div className="text-[11px] flex items-center gap-2">
                {priceAction.last_candle.rejection === "bearish_rejection" ? (
                  <span className="inline-flex items-center gap-1 text-rose-400 font-semibold bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                    <ShieldAlert size={12} /> Upper Wick Rejection (
                    {(priceAction.last_candle.upper_wick_ratio * 100).toFixed(0)}%)
                  </span>
                ) : priceAction.last_candle.rejection === "bullish_rejection" ? (
                  <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                    <ShieldAlert size={12} /> Lower Wick Absorption (
                    {(priceAction.last_candle.lower_wick_ratio * 100).toFixed(0)}%)
                  </span>
                ) : (
                  <span className="text-slate-400">
                    Candle Body: {(priceAction.last_candle.body_ratio * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Bottom Row: S/R Clearance, Recent Patterns, and Sweeps */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 text-xs">
            {/* Support Clearance */}
            <div className="rounded-lg bg-white/[0.02] p-2 border border-white/5">
              <div className="text-[10px] uppercase font-semibold text-slate-400 flex items-center justify-between">
                <span>Nearest Support</span>
                <span className="text-emerald-400">
                  {priceAction.dist_support_pct != null
                    ? `-${(priceAction.dist_support_pct * 100).toFixed(1)}%`
                    : "—"}
                </span>
              </div>
              <div className="mt-1 font-mono font-bold text-slate-200">
                {priceAction.nearest_support != null
                  ? `$${
                      priceAction.nearest_support < 1
                        ? priceAction.nearest_support.toFixed(4)
                        : priceAction.nearest_support.toFixed(2)
                    }`
                  : "None Detected"}
              </div>
            </div>

            {/* Resistance Clearance */}
            <div className="rounded-lg bg-white/[0.02] p-2 border border-white/5">
              <div className="text-[10px] uppercase font-semibold text-slate-400 flex items-center justify-between">
                <span>Nearest Resistance</span>
                <span className="text-rose-400">
                  {priceAction.dist_resistance_pct != null
                    ? `+${(priceAction.dist_resistance_pct * 100).toFixed(1)}%`
                    : "—"}
                </span>
              </div>
              <div className="mt-1 font-mono font-bold text-slate-200 flex items-center justify-between">
                <span>
                  {priceAction.nearest_resistance != null
                    ? `$${
                        priceAction.nearest_resistance < 1
                          ? priceAction.nearest_resistance.toFixed(4)
                          : priceAction.nearest_resistance.toFixed(2)
                      }`
                    : "Clear Sky"}
                </span>
                {priceAction.room_to_run_atr != null && (
                  <span className="text-[10px] font-normal text-slate-400">
                    {priceAction.room_to_run_atr.toFixed(1)}x ATR Room
                  </span>
                )}
              </div>
            </div>

            {/* Patterns & Liquidity Sweep Status */}
            <div className="rounded-lg bg-white/[0.02] p-2 border border-white/5 sm:col-span-2 md:col-span-1">
              <div className="text-[10px] uppercase font-semibold text-slate-400">
                Live Chart Reading
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1">
                {priceAction.liquidity_sweep && (
                  <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-bold text-amber-400 border border-amber-500/30">
                    ⚡ {priceAction.liquidity_sweep.direction === "bearish" ? "Bear Trap" : "Bull Trap"}
                  </span>
                )}
                {priceAction.patterns && priceAction.patterns.length > 0 ? (
                  priceAction.patterns.slice(0, 2).map((p, idx) => (
                    <span
                      key={idx}
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold border ${
                        p.direction === "bullish"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : p.direction === "bearish"
                          ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                          : "bg-slate-500/10 text-slate-300 border-slate-500/20"
                      }`}
                    >
                      {p.name}
                    </span>
                  ))
                ) : (
                  <span className="text-[11px] text-slate-400">Clean Trend Formation</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Chart Canvas */}
      {error ? (
        <div className="px-1 py-12 text-center text-sm text-slate-400">{error}</div>
      ) : (
        <div className="relative">
          <div ref={containerRef} className="h-[360px] w-full rounded-lg overflow-hidden" />
          {/* Overlaid Legend */}
          {showIndicators && (
            <div className="absolute top-2 left-3 flex items-center gap-3 text-[11px] bg-slate-900/70 backdrop-blur px-2.5 py-1 rounded-md border border-white/10 text-[var(--ink-muted)] pointer-events-none">
              <Legend color="#6366f1" label="EMA50" />
              <Legend color="#94a3b8" label="EMA200" />
              <Legend color="#f59e0b" label="UT Stop" />
            </div>
          )}
        </div>
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
