"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  Download,
  Activity,
  Layers,
  Scale,
  Percent,
  TrendingUp,
  FileSpreadsheet,
  Lock,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Info,
} from "lucide-react";
import { createChart, ColorType, IChartApi, ISeriesApi } from "lightweight-charts";

// Exported TypeScript Interfaces strictly per Section 8 Specification
export type Stage = "A" | "B" | "C" | "D";

export interface SleeveStatus {
  sleeve: "trend" | "carry";
  stage: Stage;
  allocationPct: number;
  economic: boolean;
  reason: string;
  netPctYtd: number;
  drawdownPct: number;
}

export interface TargetPosition {
  asset: string;
  signal: number;
  volPct: number;
  targetWeight: number;
  currentWeight: number;
  action: "HOLD" | "BUY" | "SELL";
  estTaxCostUsd: number;
}

export interface PortfolioSnapshot {
  asOf: string;
  equityUsd: number;
  cashPct: number;
  grossExposurePct: number;
  volTargetPct: number;
  realizedVolPct: number;
  drawdownPct: number;
  governor: "NORMAL" | "HALVED" | "CASH";
  ledgerReconciled: boolean;
  deltaUsd: number;
}

export interface BenchmarkPoint {
  t: string;
  portfolio: number;
  btcBuyHold: number;
  cashAfterTax: number;
}

export interface TaxScenarioRow {
  fy: string;
  scenario: "A" | "B";
  realizedGainUsd: number;
  taxUsd: number;
  tdsCreditUsd: number;
  gstFeesUsd: number;
  afterTaxPnlUsd: number;
}

const MANDATORY_TAX_DISCLAIMER = "Not tax advice; consult a CA";

export default function PortfolioPage() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  // States with default mock values corresponding to v2 engine
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot>({
    asOf: new Date().toISOString(),
    equityUsd: 1000.0,
    cashPct: 41.6,
    grossExposurePct: 58.4,
    volTargetPct: 15.0,
    realizedVolPct: 14.2,
    drawdownPct: 8.2,
    governor: "NORMAL",
    ledgerReconciled: true,
    deltaUsd: 0.0,
  });

  const [sleeves, setSleeves] = useState<SleeveStatus[]>([
    {
      sleeve: "trend",
      stage: "A",
      allocationPct: 58.4,
      economic: true,
      reason: "7-factor composite signal positive; 15% vol-target active",
      netPctYtd: 18.4,
      drawdownPct: 8.2,
    },
    {
      sleeve: "carry",
      stage: "A",
      allocationPct: 0.0,
      economic: false,
      reason: "Forecast net APR 3.32% below 10.50% configured hurdle (cash 6.5% + spread 2% + liquidation 2%)",
      netPctYtd: 0.0,
      drawdownPct: 0.0,
    },
  ]);

  const [targets, setTargets] = useState<TargetPosition[]>([
    {
      asset: "BTCUSDT",
      signal: 0.5714,
      volPct: 41.2,
      targetWeight: 0.208,
      currentWeight: 0.195,
      action: "HOLD",
      estTaxCostUsd: 0.0,
    },
    {
      asset: "ETHUSDT",
      signal: 0.2857,
      volPct: 52.8,
      targetWeight: 0.124,
      currentWeight: 0.120,
      action: "HOLD",
      estTaxCostUsd: 0.0,
    },
    {
      asset: "SOLUSDT",
      signal: 0.7143,
      volPct: 68.4,
      targetWeight: 0.152,
      currentWeight: 0.080,
      action: "BUY",
      estTaxCostUsd: 0.0,
    },
    {
      asset: "BNBUSDT",
      signal: 0.4286,
      volPct: 38.9,
      targetWeight: 0.100,
      currentWeight: 0.100,
      action: "HOLD",
      estTaxCostUsd: 0.0,
    },
  ]);

  const [benchmarks, setBenchmarks] = useState<BenchmarkPoint[]>([
    { t: "2026-01-01", portfolio: 1.0, btcBuyHold: 1.0, cashAfterTax: 1.0 },
    { t: "2026-03-01", portfolio: 1.042, btcBuyHold: 1.085, cashAfterTax: 1.007 },
    { t: "2026-06-01", portfolio: 1.091, btcBuyHold: 0.924, cashAfterTax: 1.018 },
    { t: "2026-09-01", portfolio: 1.148, btcBuyHold: 1.12, cashAfterTax: 1.029 },
    { t: "2026-10-28", portfolio: 1.184, btcBuyHold: 1.142, cashAfterTax: 1.036 },
  ]);

  const [taxRows, setTaxRows] = useState<TaxScenarioRow[]>([
    {
      fy: "FY2026-27",
      scenario: "A",
      realizedGainUsd: 342.5,
      taxUsd: 106.86,
      tdsCreditUsd: 12.4,
      gstFeesUsd: 1.84,
      afterTaxPnlUsd: 233.8,
    },
    {
      fy: "FY2026-27",
      scenario: "B",
      realizedGainUsd: 280.1,
      taxUsd: 87.39,
      tdsCreditUsd: 12.4,
      gstFeesUsd: 1.84,
      afterTaxPnlUsd: 190.87,
    },
  ]);

  const [promotionData, setPromotionData] = useState<any>(null);

  // Fetch from FastAPI backend if available
  useEffect(() => {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${backendUrl}/v2/snapshot`)
      .then((r) => r.json())
      .then((d) => setSnapshot(d))
      .catch(() => {});

    fetch(`${backendUrl}/v2/sleeves`)
      .then((r) => r.json())
      .then((d) => setSleeves(d))
      .catch(() => {});

    fetch(`${backendUrl}/v2/targets`)
      .then((r) => r.json())
      .then((d) => setTargets(d))
      .catch(() => {});

    fetch(`${backendUrl}/v2/benchmarks`)
      .then((r) => r.json())
      .then((d) => setBenchmarks(d))
      .catch(() => {});

    fetch(`${backendUrl}/v2/tax`)
      .then((r) => r.json())
      .then((d) => setTaxRows(d))
      .catch(() => {});

    fetch(`${backendUrl}/v2/promotion`)
      .then((r) => r.json())
      .then((d) => setPromotionData(d))
      .catch(() => {});
  }, []);

  // Initialize Lightweight-Charts
  useEffect(() => {
    if (!chartContainerRef.current) return;

    chartContainerRef.current.innerHTML = "";

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#121821" },
        textColor: "#8B98A9",
      },
      grid: {
        vertLines: { color: "#1E2733" },
        horzLines: { color: "#1E2733" },
      },
      crosshair: {
        vertLine: { color: "#4DA3FF", width: 1, style: 2 },
        horzLine: { color: "#4DA3FF", width: 1, style: 2 },
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

    // Series 1: Sleeve T Portfolio (Green #00E5A8)
    const portfolioSeries = chart.addLineSeries({
      color: "#00E5A8",
      lineWidth: 2,
      title: "Sleeve T (Vol-Targeted)",
    });

    // Series 2: BTC Buy & Hold (Amber #FFB020)
    const btcSeries = chart.addLineSeries({
      color: "#FFB020",
      lineWidth: 2,
      title: "BTC Buy-and-Hold",
    });

    // Series 3: Cash After-Tax (Blue #4DA3FF)
    const cashSeries = chart.addLineSeries({
      color: "#4DA3FF",
      lineWidth: 2,
      title: "Cash After-Tax (6.5%)",
    });

    const ptsPortfolio = benchmarks.map((b) => ({ time: b.t, value: b.portfolio }));
    const ptsBtc = benchmarks.map((b) => ({ time: b.t, value: b.btcBuyHold }));
    const ptsCash = benchmarks.map((b) => ({ time: b.t, value: b.cashAfterTax }));

    portfolioSeries.setData(ptsPortfolio as any);
    btcSeries.setData(ptsBtc as any);
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
      chart.remove();
    };
  }, [benchmarks]);

  const handleDownloadCaCsv = () => {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.open(`${backendUrl}/v2/tax/ca-export`, "_blank");
  };

  return (
    <div className="min-h-screen bg-[#0B0F14] text-[#E6EDF3] p-6 space-y-6 max-w-7xl mx-auto">
      {/* Statutory Header & Ledger-verified Banner */}
      <header className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-[#1E2733] gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-[#E6EDF3]">
              StarkX QuantEdge v2
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-[12px] bg-[#121821] border border-[#1E2733] text-[#4DA3FF]">
              EVIDENCE-GATED PORTFOLIO (PAPER-FIRST)
            </span>
          </div>
          <p className="text-xs text-[#8B98A9] mt-1">
            Vol-Targeted Systematic Trend (15%) • Gated Basis Carry • Statutory FIFO Lot Accounting
          </p>
        </div>

        {/* Ledger-verified Badge */}
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-[12px] border text-xs font-medium ${
              snapshot.ledgerReconciled
                ? "bg-[#121821] border-[#00E5A8]/30 text-[#00E5A8]"
                : "bg-[#121821] border-[#FF4D6A]/30 text-[#FF4D6A]"
            }`}
          >
            {snapshot.ledgerReconciled ? (
              <ShieldCheck className="w-4 h-4 text-[#00E5A8]" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-[#FF4D6A]" />
            )}
            <span>
              {snapshot.ledgerReconciled
                ? `Ledger Verified (Δ $${snapshot.deltaUsd.toFixed(4)} <= $0.01)`
                : `Reconciliation Break (Δ $${snapshot.deltaUsd.toFixed(4)})`}
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-[12px] bg-[#121821] border border-[#1E2733] text-xs text-[#8B98A9]">
            <Lock className="w-3.5 h-3.5 text-[#FFB020]" />
            <span>V2_LIVE_ENABLED=false</span>
          </div>
        </div>
      </header>

      {/* Mandatory Statutory Tax Banner (Rule 0.6) */}
      <div className="flex items-center justify-between p-3 rounded-[12px] bg-[#121821] border border-[#FFB020]/30 text-xs text-[#FFB020]">
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 flex-shrink-0" />
          <span className="font-semibold">{MANDATORY_TAX_DISCLAIMER}</span>
          <span className="text-[#8B98A9]">
            — All tax figures are labelled hypothetical statutory scenarios (Scenario A vs Scenario B) under Indian VDA provisions.
          </span>
        </div>
        <span className="text-[11px] text-[#8B98A9]">Income Tax Act S.115BBH / S.194S</span>
      </div>

      {/* Top Metric Cards: Portfolio State & Governor */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <div className="text-xs text-[#8B98A9] uppercase tracking-wider">Account Equity</div>
          <div className="text-2xl font-bold mt-1 text-[#E6EDF3]">
            ${snapshot.equityUsd.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className="flex items-center justify-between text-xs text-[#8B98A9] mt-2">
            <span>Gross Exposure: {snapshot.grossExposurePct}%</span>
            <span>Cash: {snapshot.cashPct}%</span>
          </div>
        </div>

        <div className="p-4 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <div className="text-xs text-[#8B98A9] uppercase tracking-wider">Vol Target (Annualized)</div>
          <div className="text-2xl font-bold mt-1 text-[#00E5A8]">{snapshot.volTargetPct}%</div>
          <div className="text-xs text-[#8B98A9] mt-2">
            Realized Vol: <span className="text-[#E6EDF3] font-medium">{snapshot.realizedVolPct}%</span>
          </div>
        </div>

        <div className="p-4 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <div className="text-xs text-[#8B98A9] uppercase tracking-wider">Peak Drawdown</div>
          <div
            className={`text-2xl font-bold mt-1 ${
              snapshot.drawdownPct >= 10 ? "text-[#FF4D6A]" : "text-[#E6EDF3]"
            }`}
          >
            -{snapshot.drawdownPct}%
          </div>
          <div className="text-xs text-[#8B98A9] mt-2">
            Governor Trigger: 10% Halve / 20% Cash
          </div>
        </div>

        <div className="p-4 rounded-[12px] bg-[#121821] border border-[#1E2733]">
          <div className="text-xs text-[#8B98A9] uppercase tracking-wider">Drawdown Governor</div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`px-2 py-0.5 text-sm font-semibold rounded-[6px] ${
                snapshot.governor === "NORMAL"
                  ? "bg-[#00E5A8]/10 text-[#00E5A8] border border-[#00E5A8]/20"
                  : snapshot.governor === "HALVED"
                  ? "bg-[#FFB020]/10 text-[#FFB020] border border-[#FFB020]/20"
                  : "bg-[#FF4D6A]/10 text-[#FF4D6A] border border-[#FF4D6A]/20"
              }`}
            >
              {snapshot.governor}
            </span>
          </div>
          <div className="text-xs text-[#8B98A9] mt-2">
            {snapshot.governor === "NORMAL"
              ? "1.0x Full Target Allocation"
              : snapshot.governor === "HALVED"
              ? "0.5x Throttled Targets"
              : "0.0x All Orders Halted (Cash)"}
          </div>
        </div>
      </div>

      {/* Sleeve Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sleeves.map((sl) => (
          <div
            key={sl.sleeve}
            className="p-5 rounded-[12px] bg-[#121821] border border-[#1E2733] flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold capitalize text-[#E6EDF3]">
                    Sleeve {sl.sleeve === "trend" ? "T (Trend)" : "C (Carry)"}
                  </span>
                  <span className="px-2 py-0.5 text-xs font-semibold rounded-[6px] bg-[#0B0F14] border border-[#1E2733] text-[#4DA3FF]">
                    Stage {sl.stage} (Shadow)
                  </span>
                </div>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-[6px] font-semibold border ${
                    sl.economic
                      ? "bg-[#00E5A8]/10 text-[#00E5A8] border-[#00E5A8]/30"
                      : "bg-[#8B98A9]/10 text-[#8B98A9] border-[#1E2733]"
                  }`}
                >
                  {sl.economic ? "ECONOMIC" : "UNECONOMIC"}
                </span>
              </div>

              <p className="text-xs text-[#8B98A9] mt-2.5">{sl.reason}</p>

              <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-[#1E2733]">
                <div>
                  <div className="text-[11px] text-[#8B98A9]">Target Allocation</div>
                  <div className="text-base font-bold text-[#E6EDF3] mt-0.5">
                    {sl.allocationPct}%
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-[#8B98A9]">Net YTD Return</div>
                  <div className="text-base font-bold text-[#00E5A8] mt-0.5">
                    +{sl.netPctYtd}%
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-[#8B98A9]">Max Drawdown</div>
                  <div className="text-base font-bold text-[#E6EDF3] mt-0.5">
                    -{sl.drawdownPct}%
                  </div>
                </div>
              </div>
            </div>

            {/* Rule 0.5 Honest Label */}
            <div className="text-[10px] text-[#8B98A9] italic mt-4 pt-3 border-t border-[#1E2733]">
              *Net of costs, after-tax scenario A/B, versus cash and buy-and-hold.
            </div>
          </div>
        ))}
      </div>

      {/* Equity vs Benchmarks Interactive Chart */}
      <div className="p-5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#1E2733] gap-2">
          <div>
            <h2 className="text-base font-bold text-[#E6EDF3]">
              Equity versus Benchmarks (Normalized)
            </h2>
            <p className="text-xs text-[#8B98A9]">
              Sleeve T Vol-Targeted (15%) vs BTC Buy-and-Hold vs After-Tax Cash (6.5% APR)
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-[#00E5A8]" />
              <span className="text-[#00E5A8]">Sleeve T (Vol-Targeted)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-[#FFB020]" />
              <span className="text-[#FFB020]">BTC Buy-and-Hold</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-[#4DA3FF]" />
              <span className="text-[#4DA3FF]">Cash After-Tax</span>
            </div>
          </div>
        </div>

        <div ref={chartContainerRef} className="w-full mt-4" />
      </div>

      {/* Target Positions & Execution Table */}
      <div className="p-5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
        <div className="flex items-center justify-between pb-4 border-b border-[#1E2733]">
          <div>
            <h2 className="text-base font-bold text-[#E6EDF3]">Daily Target Positions (00:05 UTC)</h2>
            <p className="text-xs text-[#8B98A9]">
              Decisions on CLOSED daily bars • No-trade band: |Δw| &gt; max(20% w_target, 2%)
            </p>
          </div>
          <div className="text-xs text-[#8B98A9]">Closed Bar: 00:00 UTC</div>
        </div>

        <div className="overflow-x-auto mt-4">
          <table className="w-full text-left text-xs text-[#E6EDF3]">
            <thead className="text-[#8B98A9] border-b border-[#1E2733] pb-2">
              <tr>
                <th className="py-2.5 px-3">Asset</th>
                <th className="py-2.5 px-3">7-Factor Signal</th>
                <th className="py-2.5 px-3">30d Vol (EWMA)</th>
                <th className="py-2.5 px-3">Target Weight</th>
                <th className="py-2.5 px-3">Current Weight</th>
                <th className="py-2.5 px-3">Action</th>
                <th className="py-2.5 px-3">Est. Tax Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E2733]">
              {targets.map((t) => (
                <tr key={t.asset} className="hover:bg-[#0B0F14]/50 transition-colors">
                  <td className="py-3 px-3 font-semibold text-[#E6EDF3]">{t.asset}</td>
                  <td className="py-3 px-3 font-mono">
                    <span
                      className={
                        t.signal > 0
                          ? "text-[#00E5A8]"
                          : t.signal < 0
                          ? "text-[#FF4D6A]"
                          : "text-[#8B98A9]"
                      }
                    >
                      {t.signal > 0 ? `+${t.signal.toFixed(4)}` : t.signal.toFixed(4)}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono">{t.volPct.toFixed(1)}%</td>
                  <td className="py-3 px-3 font-mono font-medium">
                    {(t.targetWeight * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 px-3 font-mono text-[#8B98A9]">
                    {(t.currentWeight * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`px-2 py-0.5 text-[11px] font-semibold rounded-[4px] ${
                        t.action === "BUY"
                          ? "bg-[#00E5A8]/10 text-[#00E5A8] border border-[#00E5A8]/30"
                          : t.action === "SELL"
                          ? "bg-[#FF4D6A]/10 text-[#FF4D6A] border border-[#FF4D6A]/30"
                          : "bg-[#1E2733] text-[#8B98A9]"
                      }`}
                    >
                      {t.action}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono text-[#8B98A9]">
                    ${t.estTaxCostUsd.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Tax & Compliance Panel (Scenario A vs B) */}
      <div className="p-5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#1E2733] gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-[#E6EDF3]">
                Statutory Tax Assessment (Scenarios A &amp; B)
              </h2>
              <span className="text-xs px-2 py-0.5 rounded-[6px] bg-[#1E2733] text-[#8B98A9]">
                FIFO Lot Ledger
              </span>
            </div>
            <p className="text-xs text-[#8B98A9] mt-0.5">
              Scenario A: 31.2% on positive disposals (no loss offset) • Scenario B: Netted at 31.2% • 1% TDS credit
            </p>
          </div>
          <button
            onClick={handleDownloadCaCsv}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-[12px] bg-[#1E2733] hover:bg-[#283545] text-xs font-semibold text-[#E6EDF3] transition-colors border border-[#1E2733]"
          >
            <FileSpreadsheet className="w-4 h-4 text-[#00E5A8]" />
            <span>Export CA CSV Schedule</span>
          </button>
        </div>

        <div className="overflow-x-auto mt-4">
          <table className="w-full text-left text-xs text-[#E6EDF3]">
            <thead className="text-[#8B98A9] border-b border-[#1E2733] pb-2">
              <tr>
                <th className="py-2.5 px-3">Financial Year</th>
                <th className="py-2.5 px-3">Scenario</th>
                <th className="py-2.5 px-3">Realized Gain/Loss</th>
                <th className="py-2.5 px-3">Tax Liability (31.2%)</th>
                <th className="py-2.5 px-3">194S TDS Credit (1%)</th>
                <th className="py-2.5 px-3">GST on Fees (18%)</th>
                <th className="py-2.5 px-3">After-Tax PnL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E2733]">
              {taxRows.map((r, idx) => (
                <tr key={`${r.fy}-${r.scenario}-${idx}`} className="hover:bg-[#0B0F14]/50">
                  <td className="py-3 px-3 font-semibold">{r.fy}</td>
                  <td className="py-3 px-3">
                    <span
                      className={`px-2 py-0.5 text-[11px] font-semibold rounded-[4px] ${
                        r.scenario === "A"
                          ? "bg-[#FFB020]/10 text-[#FFB020] border border-[#FFB020]/20"
                          : "bg-[#4DA3FF]/10 text-[#4DA3FF] border border-[#4DA3FF]/20"
                      }`}
                    >
                      Scenario {r.scenario} {r.scenario === "A" ? "(No Offset)" : "(Netted)"}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono font-medium text-[#00E5A8]">
                    +${r.realizedGainUsd.toFixed(2)}
                  </td>
                  <td className="py-3 px-3 font-mono text-[#FF4D6A]">
                    ${r.taxUsd.toFixed(2)}
                  </td>
                  <td className="py-3 px-3 font-mono text-[#4DA3FF]">
                    ${r.tdsCreditUsd.toFixed(2)}
                  </td>
                  <td className="py-3 px-3 font-mono text-[#8B98A9]">
                    ${r.gstFeesUsd.toFixed(2)}
                  </td>
                  <td className="py-3 px-3 font-mono font-bold text-[#E6EDF3]">
                    ${r.afterTaxPnlUsd.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Evidence Gates & Promotion Tracker */}
      <div className="p-5 rounded-[12px] bg-[#121821] border border-[#1E2733]">
        <div className="pb-4 border-b border-[#1E2733]">
          <h2 className="text-base font-bold text-[#E6EDF3]">
            Evidence Gates &amp; Stage Promotion Tracker
          </h2>
          <p className="text-xs text-[#8B98A9] mt-0.5">
            Stage A (Research) → Stage B (Shadow) → Stage C (Paper-Executed) → Stage D (Micro-Live)
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          {/* Sleeve T Gates */}
          <div className="p-4 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
            <div className="flex items-center justify-between pb-2 border-b border-[#1E2733]">
              <span className="font-semibold text-sm text-[#E6EDF3]">Sleeve T (Trend) Gates</span>
              <span className="text-xs text-[#8B98A9]">Trial #517 Registered</span>
            </div>
            <ul className="mt-3 space-y-2 text-xs">
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">1. Pre-registration Spec SHA-256</span>
                <span className="text-[#00E5A8] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 3704e9e7... PASS
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">2. >= 2 Full Market Cycles</span>
                <span className="text-[#00E5A8] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 9.2 Years PASS
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">3. Max DD &lt;= 60% of Buy-and-Hold</span>
                <span className="text-[#00E5A8] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 8.6% vs 83.2% PASS
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">4. Basket Pre-tax Net Sharpe &gt;= 0.60</span>
                <span className="text-[#00E5A8] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 1.12 PASS
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">5. 36 Monthly Dates vs Cash (&gt;= 70%)</span>
                <span className="text-[#FF4D6A] font-semibold flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5" /> 16.7% (6/36) FAIL
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">6. 4 Neighbourhood Variants Robustness</span>
                <span className="text-[#00E5A8] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> All 4 Passed PASS
                </span>
              </li>
            </ul>
          </div>

          {/* Sleeve C Gates */}
          <div className="p-4 rounded-[8px] bg-[#0B0F14] border border-[#1E2733]">
            <div className="flex items-center justify-between pb-2 border-b border-[#1E2733]">
              <span className="font-semibold text-sm text-[#E6EDF3]">Sleeve C (Carry) Gates</span>
              <span className="text-xs text-[#8B98A9]">Trial #518 Registered</span>
            </div>
            <ul className="mt-3 space-y-2 text-xs">
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">1. Pre-registration Spec SHA-256</span>
                <span className="text-[#00E5A8] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 3704e9e7... PASS
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">2. Historical Stress Windows (3/3)</span>
                <span className="text-[#00E5A8] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Zero Liq PASS
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">3. Net APR &gt;= configured hurdle (12m, 24m)</span>
                <span className="text-[#FF5C5C] font-semibold flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5" /> 6.95% &lt; 10.5% FAIL
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">4. Liquidation Buffer Rule</span>
                <span className="text-[#00E5A8] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> &gt;= 3x ATR(1d) PASS
                </span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-[#8B98A9]">5. Execution Mode</span>
                <span className="text-[#4DA3FF] font-semibold flex items-center gap-1">
                  Paper Only
                </span>
              </li>
            </ul>
          </div>
        </div>

        {/* Stage Progression Checklist Notice */}
        <div className="mt-4 p-3 rounded-[8px] bg-[#0B0F14] border border-[#1E2733] text-xs text-[#8B98A9] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-[#4DA3FF]" />
            <span>
              Stage C → D requires &gt;= 180 days paper execution, simulated 95th pctl drawdown, completed checklist, and CA sign-off.
            </span>
          </div>
          <span className="text-[11px] font-mono text-[#8B98A9]">docs/CAPITAL_READINESS_CHECKLIST.md</span>
        </div>
      </div>
    </div>
  );
}
