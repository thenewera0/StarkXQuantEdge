"use client";

import React, { useCallback, useEffect, useState, useRef } from "react";
import {
  FlaskConical,
  ShieldCheck,
  TrendingUp,
  Activity,
  Layers,
  Clock,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Info,
  DollarSign,
  ChevronDown,
  Percent,
  Sliders,
  Scale,
} from "lucide-react";
import {
  fetchLabLeaderboard,
  fetchLabPositions,
  fetchLabEvents,
  fetchLabHealth,
  fetchLabEquity,
  fetchLabPortfolio,
  fetchLabTax,
  type VariantRow,
  type OpenPaperPosition,
  type LabEvent,
  type LabHealth,
  type EquityPoint,
  type LabPortfolioResponse,
  type LabTaxScenarioRow,
  type Tier,
  type VariantStatus,
} from "@/lib/api";
import { createChart, ColorType, IChartApi, LineSeries } from "lightweight-charts";

// Exported TypeScript Interfaces strictly per Section 7.2 Specification
export type { Tier, VariantStatus, VariantRow, OpenPaperPosition, LabEvent, LabHealth, EquityPoint };

const TIER_COLORS: Record<Tier | "paused", string> = {
  T0: "#8B98A9",
  T1: "#4DA3FF",
  T2: "#FFB020",
  T3: "#00E5A8",
  paused: "#FF4D6A",
};

export default function LabPage() {
  const [leaderboard, setLeaderboard] = useState<VariantRow[]>([]);
  const [positions, setPositions] = useState<OpenPaperPosition[]>([]);
  const [events, setEvents] = useState<LabEvent[]>([]);
  const [health, setHealth] = useState<LabHealth | null>(null);
  const [portfolio, setPortfolio] = useState<LabPortfolioResponse | null>(null);
  const [taxRows, setTaxRows] = useState<LabTaxScenarioRow[]>([]);
  const [selectedVariant, setSelectedVariant] = useState<string>("trend_d1_base");
  const [equityPoints, setEquityPoints] = useState<EquityPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [sortField, setSortField] = useState<keyof VariantRow>("meanNetR");
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [lb, pos, evs, hlth, port, tx] = await Promise.all([
        fetchLabLeaderboard().catch(() => []),
        fetchLabPositions().catch(() => []),
        fetchLabEvents(30).catch(() => []),
        fetchLabHealth().catch(() => null),
        fetchLabPortfolio().catch(() => null),
        fetchLabTax().catch(() => []),
      ]);
      setLeaderboard(lb);
      setPositions(pos);
      setEvents(evs);
      setHealth(hlth);
      setPortfolio(port);
      setTaxRows(tx);
      if (lb.length > 0 && !selectedVariant) {
        setSelectedVariant(lb[0].variantId);
      }
    } finally {
      setLoading(false);
    }
  }, [selectedVariant]);

  // Initial load
  useEffect(() => {
    loadData();
    const intervalId = setInterval(loadData, 30000); // 30s background sync
    return () => clearInterval(intervalId);
  }, [loadData]);

  // Section 7.2: 5-second polling for open positions and live health
  useEffect(() => {
    const pollId = setInterval(() => {
      fetchLabPositions().then(setPositions).catch(() => {});
      fetchLabHealth().then(setHealth).catch(() => {});
    }, 5000);
    return () => clearInterval(pollId);
  }, []);

  // Fetch equity curve when selectedVariant changes
  useEffect(() => {
    if (selectedVariant) {
      fetchLabEquity(selectedVariant).then(setEquityPoints).catch(() => {});
    }
  }, [selectedVariant]);

  // Chart Rendering
  useEffect(() => {
    if (!chartContainerRef.current || equityPoints.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8B98A9",
        fontFamily: "Inter, sans-serif",
      },
      grid: {
        vertLines: { color: "#1E2733", style: 1 },
        horzLines: { color: "#1E2733", style: 1 },
      },
      rightPriceScale: {
        borderColor: "#1E2733",
      },
      timeScale: {
        borderColor: "#1E2733",
      },
      width: chartContainerRef.current.clientWidth,
      height: 320,
    });

    chartRef.current = chart;

    // Series 1: Variant Equity (Green #00E5A8)
    const varSeries = chart.addSeries(LineSeries, {
      color: "#00E5A8",
      lineWidth: 2,
      title: `${selectedVariant} (Paper)`,
    });

    // Series 2: Random Entry Control (Amber #FFB020)
    const ctrlSeries = chart.addSeries(LineSeries, {
      color: "#FFB020",
      lineWidth: 2,
      title: "Control (Random Entry)",
    });

    // Series 3: Cash After-Tax (Blue #4DA3FF)
    const cashSeries = chart.addSeries(LineSeries, {
      color: "#4DA3FF",
      lineWidth: 2,
      title: "Cash After-Tax (4.47%)",
    });

    const ptsVar = equityPoints.map((p) => ({ time: p.t, value: p.variant }));
    const ptsCtrl = equityPoints.map((p) => ({ time: p.t, value: p.control }));
    const ptsCash = equityPoints.map((p) => ({ time: p.t, value: p.cashAfterTax }));

    varSeries.setData(ptsVar as any);
    ctrlSeries.setData(ptsCtrl as any);
    cashSeries.setData(ptsCash as any);

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [equityPoints, selectedVariant]);

  // Sort Leaderboard
  const sortedLeaderboard = [...leaderboard].sort((a, b) => {
    let aVal = a[sortField];
    let bVal = b[sortField];
    if (typeof aVal === "number" && typeof bVal === "number") {
      return sortAsc ? aVal - bVal : bVal - aVal;
    }
    return String(aVal).localeCompare(String(bVal)) * (sortAsc ? 1 : -1);
  });

  const handleSort = (field: keyof VariantRow) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const defaultRow: VariantRow = {
    strategyId: "trend_d1",
    variantId: "trend_d1_base",
    timeframe: "1d",
    direction: "long",
    tier: "T0",
    status: "active",
    nTrades: 0,
    activeDays: 0,
    meanNetR: 0,
    ciLow: 0,
    ciHigh: 0,
    profitFactor: 0,
    maxDdPct: 0,
    vsControlR: 0,
    vsControlCiLow: 0,
    afterTaxUsdPerYearAt1k: { a: 0, b: 0 },
    weightPct: 6.67,
    takerMeanR: 0,
    makerMeanR: 0,
    evidenceProgress: { trades: 0, days: 0, targetTrades: 30, targetDays: 20 },
  };

  const selectedRow = leaderboard.find((r) => r.variantId === selectedVariant) || leaderboard[0] || defaultRow;

  return (
    <div className="min-h-screen bg-[#0B0F14] text-[#E6EDF3] p-4 md:p-8 space-y-6">
      {/* 1. Header & Live Mode Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#1E2733]">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-[12px] bg-[#00E5A8]/10 text-[#00E5A8] border border-[#00E5A8]/30">
            <FlaskConical size={26} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">StarkX LAB</h1>
              <span className="inline-flex items-center gap-1 rounded-[6px] bg-[#3B2A05] px-2 py-0.5 text-[11px] font-bold text-[#FFB020] border border-[#FFB020]/40">
                PAPER · VIRTUAL
              </span>
              <span className="text-xs px-2 py-0.5 rounded-[6px] bg-[#121821] text-[#8B98A9] border border-[#1E2733]">
                Strictly Zero Private Keys
              </span>
            </div>
            <p className="text-xs text-[#8B98A9] mt-0.5">
              Active Multi-Strategy Paper Trading Sandbox · Evidence-Gated Self-Improvement &amp; Hedge Allocation
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] bg-[#121821] hover:bg-[#1A2330] border border-[#1E2733] text-xs text-[#E6EDF3] transition-colors"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            Sync Lab
          </button>
        </div>
      </div>

      {/* 2. Section 7.2 Health Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3.5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <span className="text-[11px] font-medium text-[#8B98A9] block">Public Feed Latency</span>
          <div className="mt-1 flex items-center gap-1.5 text-base font-bold text-white">
            <div className="w-2 h-2 rounded-full bg-[#00E5A8] animate-pulse" />
            {health?.feedLagSec ?? 3}s Lag
          </div>
        </div>

        <div className="p-3.5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <span className="text-[11px] font-medium text-[#8B98A9] block">Ledger Reconciled</span>
          <div className="mt-1 flex items-center gap-1.5 text-base font-bold text-[#00E5A8]">
            <CheckCircle2 size={16} />
            {health?.ledgerReconciled ? "Reconciled ($0.00)" : "Pending Check"}
          </div>
        </div>

        <div className="p-3.5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <span className="text-[11px] font-medium text-[#8B98A9] block">Active Variants</span>
          <div className="mt-1 text-base font-bold text-white">
            {health?.variantsActive ?? 15} <span className="text-xs font-normal text-[#8B98A9]">/ 40 Max</span>
          </div>
        </div>

        <div className="p-3.5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <span className="text-[11px] font-medium text-[#8B98A9] block">Open Paper Positions</span>
          <div className="mt-1 text-base font-bold text-[#4DA3FF]">
            {health?.openPositions ?? positions.length} <span className="text-xs font-normal text-[#8B98A9]">positions</span>
          </div>
        </div>

        <div className="p-3.5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <span className="text-[11px] font-medium text-[#8B98A9] block">Research Trials</span>
          <div className="mt-1 text-base font-bold text-[#FFB020]">
            #{health?.trialsRegistered ?? 10} <span className="text-xs font-normal text-[#8B98A9]">trials</span>
          </div>
        </div>

        <div className="p-3.5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <span className="text-[11px] font-medium text-[#8B98A9] block">Expected False Positives</span>
          <div className="mt-1 text-base font-bold text-[#8B98A9]">
            {health?.expectedFalsePositives ?? 0.05} <span className="text-xs font-normal text-[#8B98A9]">(0.05 × T2/T3)</span>
          </div>
        </div>
      </div>

      {/* 3. Section 7.2 Main Content: Leaderboard + Live Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2/3): Sortable Leaderboard */}
        <div className="lg:col-span-2 rounded-[12px] bg-[#121821] border border-[#1E2733] p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1E2733]">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Sliders size={18} className="text-[#00E5A8]" />
                Strategy Variant Leaderboard
              </h2>
              <span className="text-xs text-[#8B98A9]">
                Click row to view individual equity curves, evidence meters, and twin metrics
              </span>
            </div>
            <span className="text-[11px] font-mono text-[#8B98A9]">
              Flat 0.5% Risk ($50/trade) · B=10,000 Bootstrap
            </span>
          </div>

          <div className="overflow-x-auto mt-4">
            <table className="w-full text-left text-xs">
              <thead className="text-[11px] text-[#8B98A9] uppercase border-b border-[#1E2733] bg-[#0B0F14]/40">
                <tr>
                  <th className="py-2.5 px-3 cursor-pointer" onClick={() => handleSort("variantId")}>
                    Variant / Timeframe
                  </th>
                  <th className="py-2.5 px-2 cursor-pointer" onClick={() => handleSort("tier")}>
                    Tier
                  </th>
                  <th className="py-2.5 px-2 cursor-pointer text-right" onClick={() => handleSort("meanNetR")}>
                    Mean Net R
                  </th>
                  <th className="py-2.5 px-2 text-right">80% CI (Day-Block)</th>
                  <th className="py-2.5 px-2 text-right" onClick={() => handleSort("profitFactor")}>
                    PF
                  </th>
                  <th className="py-2.5 px-2 text-right" onClick={() => handleSort("nTrades")}>
                    Trades / Days
                  </th>
                  <th className="py-2.5 px-2 text-right" onClick={() => handleSort("weightPct")}>
                    Weight
                  </th>
                  <th className="py-2.5 px-3 text-right">After-Tax/Yr ($1k)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2733]">
                {sortedLeaderboard.map((r) => {
                  const isSelected = r.variantId === selectedVariant;
                  const tierColor = TIER_COLORS[r.status === "paused" ? "paused" : r.tier];
                  return (
                    <tr
                      key={r.variantId}
                      onClick={() => setSelectedVariant(r.variantId)}
                      className={`hover:bg-[#1A2330]/60 cursor-pointer transition-colors ${
                        isSelected ? "bg-[#1A2330] border-l-2 border-[#00E5A8]" : ""
                      }`}
                    >
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-white flex items-center gap-1.5">
                          {r.variantId}
                          <span className="text-[10px] font-normal px-1.5 py-0.2 rounded bg-[#1E2733] text-[#8B98A9]">
                            {r.timeframe}
                          </span>
                        </div>
                        <div className="text-[10px] text-[#8B98A9]">{r.strategyId}</div>
                      </td>
                      <td className="py-2.5 px-2">
                        <span
                          className="px-2 py-0.5 rounded text-[10px] font-bold"
                          style={{
                            color: tierColor,
                            backgroundColor: `${tierColor}15`,
                            border: `1px solid ${tierColor}30`,
                          }}
                        >
                          {r.status === "paused" ? "PAUSED" : r.tier}
                        </span>
                      </td>
                      <td
                        className={`py-2.5 px-2 text-right font-bold tabular-nums ${
                          r.meanNetR >= 0 ? "text-[#00E5A8]" : "text-[#FF4D6A]"
                        }`}
                      >
                        {r.meanNetR > 0 ? "+" : ""}
                        {r.meanNetR.toFixed(3)}R
                      </td>
                      <td className="py-2.5 px-2 text-right text-[11px] tabular-nums text-[#8B98A9]">
                        [{r.ciLow.toFixed(2)}, {r.ciHigh.toFixed(2)}]
                      </td>
                      <td className="py-2.5 px-2 text-right font-medium tabular-nums text-white">
                        {r.profitFactor.toFixed(2)}x
                      </td>
                      <td className="py-2.5 px-2 text-right text-[11px] tabular-nums text-[#8B98A9]">
                        {r.nTrades}T · {r.activeDays}d
                      </td>
                      <td className="py-2.5 px-2 text-right font-bold tabular-nums text-[#4DA3FF]">
                        {r.weightPct.toFixed(1)}%
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-[11px]">
                        <span className="text-[#00E5A8]">A: ${r.afterTaxUsdPerYearAt1k.a}</span>
                        <span className="text-[#8B98A9] ml-1">/ B: ${r.afterTaxUsdPerYearAt1k.b}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column (1/3): Section 7.2 Live Open Paper Positions (5s polling) */}
        <div className="rounded-[12px] bg-[#121821] border border-[#1E2733] p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#1E2733]">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Activity size={18} className="text-[#4DA3FF]" />
                Live Open Paper Positions
              </h2>
              <span className="flex items-center gap-1 text-[10px] text-[#00E5A8]">
                <div className="w-1.5 h-1.5 rounded-full bg-[#00E5A8] animate-pulse" />
                5s Polling
              </span>
            </div>

            <div className="mt-3 space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
              {positions.length === 0 ? (
                <div className="p-6 text-center text-xs text-[#8B98A9]">
                  No active open paper positions. Scanning closed bars.
                </div>
              ) : (
                positions.map((p) => {
                  const isLong = p.side === "long";
                  return (
                    <div
                      key={p.positionId}
                      className="p-3 rounded-[8px] bg-[#0B0F14] border border-[#1E2733] hover:border-[#4DA3FF]/40 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              isLong ? "bg-[#00E5A8]/15 text-[#00E5A8]" : "bg-[#FF4D6A]/15 text-[#FF4D6A]"
                            }`}
                          >
                            {p.side.toUpperCase()}
                          </span>
                          <span className="font-bold text-xs text-white">{p.symbol}</span>
                          <span className="text-[10px] px-1 py-0.2 rounded bg-[#1E2733] text-[#8B98A9]">
                            {p.entryMode}
                          </span>
                        </div>
                        <div
                          className={`text-xs font-bold tabular-nums ${
                            p.unrealizedR >= 0 ? "text-[#00E5A8]" : "text-[#FF4D6A]"
                          }`}
                        >
                          {p.unrealizedR > 0 ? "+" : ""}
                          {p.unrealizedR.toFixed(2)}R
                        </div>
                      </div>

                      <div className="mt-2 grid grid-cols-3 gap-1 text-[11px] text-[#8B98A9]">
                        <div>
                          Entry: <span className="text-white">${p.entry.toFixed(2)}</span>
                        </div>
                        <div>
                          Stop: <span className="text-[#FF4D6A]">${p.stop.toFixed(2)}</span>
                        </div>
                        <div>
                          Target:{" "}
                          <span className="text-[#00E5A8]">{p.target ? `$${p.target.toFixed(2)}` : "Trail"}</span>
                        </div>
                      </div>

                      <div className="mt-2 flex items-center justify-between text-[10px] text-[#8B98A9] pt-1.5 border-t border-[#1E2733]">
                        <span>Variant: {p.variantId}</span>
                        <span>Age: {p.ageBars} bars</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-[#1E2733] text-[10.5px] text-[#8B98A9]">
            Stops &amp; targets resolved on 1m candles. Same-minute collision = Stop-First.
          </div>
        </div>
      </div>

      {/* 4. Section 7.2 Interactive Equity vs Control vs Cash Chart + Evidence Meters */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Chart (2/3) */}
        <div className="lg:col-span-2 rounded-[12px] bg-[#121821] border border-[#1E2733] p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#1E2733]">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <TrendingUp size={18} className="text-[#00E5A8]" />
                Variant Equity vs Control vs Cash:{" "}
                <span className="text-[#00E5A8]">{selectedVariant}</span>
              </h2>
              <span className="text-xs text-[#8B98A9]">
                Live paper equity series compared against Random-Entry Control &amp; 4.47% After-Tax Cash
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5 text-[#00E5A8]">
                <div className="w-2.5 h-0.5 bg-[#00E5A8]" /> Variant
              </span>
              <span className="flex items-center gap-1.5 text-[#FFB020]">
                <div className="w-2.5 h-0.5 bg-[#FFB020]" /> Random Control
              </span>
              <span className="flex items-center gap-1.5 text-[#4DA3FF]">
                <div className="w-2.5 h-0.5 bg-[#4DA3FF]" /> Cash After-Tax
              </span>
            </div>
          </div>

          <div ref={chartContainerRef} className="w-full mt-4" style={{ height: "320px" }} />
        </div>

        {/* Evidence Meters & Twin Comparison (1/3) */}
        <div className="rounded-[12px] bg-[#121821] border border-[#1E2733] p-5 flex flex-col justify-between">
          <div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2 pb-3 border-b border-[#1E2733]">
              <Scale size={18} className="text-[#FFB020]" />
              Evidence Progression ({selectedRow.variantId})
            </h2>

            {/* Evidence Meter: Trades */}
            <div className="mt-4 space-y-3">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-[#8B98A9]">Trade Count Qualification</span>
                  <span className="text-white font-medium">
                    {selectedRow.nTrades} / {selectedRow.evidenceProgress.targetTrades}
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-[#0B0F14] border border-[#1E2733] overflow-hidden">
                  <div
                    className="h-full bg-[#00E5A8] rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        (selectedRow.nTrades / Math.max(selectedRow.evidenceProgress.targetTrades, 1)) * 100
                      )}%`,
                    }}
                  />
                </div>
              </div>

              {/* Evidence Meter: Days */}
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-[#8B98A9]">Active Days Forward Accumulation</span>
                  <span className="text-white font-medium">
                    {selectedRow.activeDays} / {selectedRow.evidenceProgress.targetDays}d
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-[#0B0F14] border border-[#1E2733] overflow-hidden">
                  <div
                    className="h-full bg-[#4DA3FF] rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        (selectedRow.activeDays / Math.max(selectedRow.evidenceProgress.targetDays, 1)) * 100
                      )}%`,
                    }}
                  />
                </div>
              </div>

              {/* Section 4: Execution Twins Comparison */}
              <div className="mt-4 pt-3 border-t border-[#1E2733]">
                <span className="text-xs font-semibold text-white block mb-2">
                  Section 4 Execution Twins (Maker vs Taker)
                </span>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
                    <span className="text-[10px] text-[#8B98A9] block">Taker Baseline</span>
                    <span className="font-bold text-white text-sm">
                      {selectedRow.takerMeanR.toFixed(3)}R
                    </span>
                    <span className="text-[10px] text-[#8B98A9] block mt-0.5">5 bps + slippage</span>
                  </div>
                  <div className="p-2.5 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
                    <span className="text-[10px] text-[#00E5A8] block">Maker Twin</span>
                    <span className="font-bold text-[#00E5A8] text-sm">
                      {selectedRow.makerMeanR.toFixed(3)}R
                    </span>
                    <span className="text-[10px] text-[#8B98A9] block mt-0.5">2 bps (never assumed)</span>
                  </div>
                </div>
                <p className="text-[10px] text-[#8B98A9] mt-2">
                  Both series tracked simultaneously; maker advantages are never assumed without proof.
                </p>
              </div>
            </div>
          </div>

          <div className="p-3 rounded-[8px] bg-[#0B0F14] border border-[#1E2733] text-[11px] text-[#8B98A9] flex items-center justify-between">
            <span>Current Tier: <strong className="text-white">{selectedRow.tier}</strong></span>
            <span>Weight: <strong className="text-[#4DA3FF]">{selectedRow.weightPct}%</strong></span>
          </div>
        </div>
      </div>

      {/* 5. Section 7.2 Event Feed + Portfolio & Tax Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (1/3): Event Feed */}
        <div className="rounded-[12px] bg-[#121821] border border-[#1E2733] p-5">
          <div className="flex items-center justify-between pb-3 border-b border-[#1E2733]">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Clock size={18} className="text-[#4DA3FF]" />
              Lab Event Audit Feed
            </h2>
            <span className="text-[11px] text-[#8B98A9]">Live Log</span>
          </div>

          <div className="mt-3 space-y-2 max-h-[300px] overflow-y-auto pr-1 text-xs">
            {events.map((e, idx) => {
              const kindColor =
                e.kind === "FILL"
                  ? "#00E5A8"
                  : e.kind === "EXIT"
                  ? "#FFB020"
                  : e.kind === "TIER_UP"
                  ? "#4DA3FF"
                  : e.kind === "REJECTED_GEOMETRY"
                  ? "#FF4D6A"
                  : "#8B98A9";
              return (
                <div key={idx} className="p-2.5 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="font-bold" style={{ color: kindColor }}>
                      [{e.kind}]
                    </span>
                    <span className="text-[#8B98A9]">{e.ts ? e.ts.replace("T", " ").slice(0, 19) : ""}</span>
                  </div>
                  <div className="text-[#E6EDF3] mt-1 text-[11px]">{e.message}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Middle & Right Column (2/3): Portfolio Risk & Statutory Tax Panel */}
        <div className="lg:col-span-2 space-y-6">
          {/* Section 6 Lab Portfolio & Beta Exposure */}
          <div className="rounded-[12px] bg-[#121821] border border-[#1E2733] p-5">
            <div className="flex items-center justify-between pb-3 border-b border-[#1E2733]">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Layers size={18} className="text-[#00E5A8]" />
                Lab Portfolio Risk &amp; Beta-Adjusted Exposure
              </h2>
              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#00E5A8]/10 text-[#00E5A8] border border-[#00E5A8]/20">
                Cap |Beta| &le; 2.0x
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
              <div className="p-3 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
                <span className="text-[10px] text-[#8B98A9] block">Total Virtual Equity</span>
                <span className="text-base font-bold text-white">
                  ${portfolio?.totalEquityUsd.toLocaleString() ?? "150,000"}
                </span>
              </div>
              <div className="p-3 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
                <span className="text-[10px] text-[#8B98A9] block">Active T1+ Variants</span>
                <span className="text-base font-bold text-[#4DA3FF]">
                  {portfolio?.activeVariantsCount ?? 15}
                </span>
              </div>
              <div className="p-3 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
                <span className="text-[10px] text-[#8B98A9] block">BTC-Beta Exposure</span>
                <span className="text-base font-bold text-[#00E5A8]">
                  {portfolio?.betaAdjustedBtcExposure.toFixed(2) ?? "0.85"}x
                </span>
              </div>
              <div className="p-3 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
                <span className="text-[10px] text-[#8B98A9] block">Allocation Governor</span>
                <span className="text-base font-bold text-white">Hedge (&eta;=0.1)</span>
              </div>
            </div>
          </div>

          {/* Section 7.2 Statutory Tax Panel (Scenarios A and B) */}
          <div className="rounded-[12px] bg-[#121821] border border-[#1E2733] p-5">
            <div className="flex items-center justify-between pb-3 border-b border-[#1E2733]">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Percent size={18} className="text-[#FFB020]" />
                Statutory Tax Audit (Indian IT Act 1961)
              </h2>
              <span className="text-[10.5px] font-mono text-[#8B98A9]">Scenario A vs B</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              {taxRows.map((t) => (
                <div key={t.scenario} className="p-3.5 rounded-[8px] bg-[#0B0F14] border border-[#1E2733] text-xs space-y-2">
                  <div className="flex items-center justify-between font-bold text-white pb-1.5 border-b border-[#1E2733]">
                    <span>Scenario {t.scenario}</span>
                    <span className="text-[#FFB020]">{t.effectiveTaxRatePct.toFixed(1)}% Effective</span>
                  </div>
                  <div className="text-[11px] text-[#8B98A9]">{t.name}</div>
                  <div className="space-y-1 pt-1 text-[11px]">
                    <div className="flex justify-between">
                      <span className="text-[#8B98A9]">Gross Gain:</span>
                      <span className="text-[#00E5A8] font-medium">+${t.grossGainUsd.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#8B98A9]">Gross Loss:</span>
                      <span className="text-[#FF4D6A] font-medium">-${t.grossLossUsd.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#8B98A9]">TDS (1%) + Cess (4%):</span>
                      <span className="text-slate-300">${(t.tdsDeductedUsd + t.cessUsd).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between font-bold pt-1 border-t border-[#1E2733]">
                      <span className="text-white">Net After-Tax:</span>
                      <span className={t.netProfitAfterTaxUsd >= 0 ? "text-[#00E5A8]" : "text-[#FF4D6A]"}>
                        ${t.netProfitAfterTaxUsd.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-3 p-2.5 rounded-[8px] bg-[#0B0F14] border border-[#1E2733] text-[10.5px] text-[#8B98A9] flex items-center gap-2">
              <Info size={14} className="text-[#4DA3FF] shrink-0" />
              <span>
                Not tax advice; consult a Chartered Accountant. Illustrative statutory calculations under Section 115BBH &amp; Section 43(5).
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function max(a: number, b: number): number {
  return a > b ? a : b;
}
