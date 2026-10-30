"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchNseStatus,
  fetchSignal,
  fetchLabPositions,
  type NSEMarketStatus,
  type Signal,
  type OpenPaperPosition,
} from "@/lib/api";
import { Card } from "./ui";
import { PriceChart } from "./PriceChart";
import { SignalCard } from "./SignalCard";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Clock,
  ExternalLink,
  Flame,
  Layers,
  Percent,
  RefreshCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";

const NSE_WATCHLIST = [
  { symbol: "^NSEI", name: "Nifty 50 Index", category: "nse_index", lot: 75 },
  { symbol: "^NSEBANK", name: "BankNifty Index", category: "nse_index", lot: 30 },
  { symbol: "^INDIAVIX", name: "India VIX", category: "nse_index", lot: 0 },
  { symbol: "RELIANCE.NS", name: "Reliance Industries", category: "nse_eq", lot: 250 },
  { symbol: "HDFCBANK.NS", name: "HDFC Bank Ltd", category: "nse_eq", lot: 550 },
  { symbol: "ICICIBANK.NS", name: "ICICI Bank Ltd", category: "nse_eq", lot: 700 },
  { symbol: "INFY.NS", name: "Infosys Ltd", category: "nse_eq", lot: 400 },
  { symbol: "TCS.NS", name: "Tata Consultancy Services", category: "nse_eq", lot: 175 },
  { symbol: "SBIN.NS", name: "State Bank of India", category: "nse_eq", lot: 750 },
];

const NSE_LAB_STRATEGIES = [
  {
    id: "l11_nse_orb_pcr_15m",
    name: "L11: Nifty 50 ORB + PCR (15m)",
    timeframe: "15m",
    tier: "T0 Collecting",
    lotSize: 75,
    desc: "Opening 15m breakout filtered by PCR skew (>1.1 for calls, <0.85 for puts) and ATR volatility cushion.",
    target: "Target: 30 trades / 20 days",
  },
  {
    id: "l12_nse_rs_vwap_1h",
    name: "L12: NSE RS Top 50 vs Nifty (1h)",
    timeframe: "1h",
    tier: "T0 Collecting",
    lotSize: "Stock Specific",
    desc: "Top 50 liquid F&O equities ranked by 20-day alpha vs Nifty 50; entries on anchored session VWAP pullbacks.",
    target: "Target: 30 trades / 20 days",
  },
  {
    id: "l13_nse_bank_nifty_statarb_1h",
    name: "L13: BankNifty vs Private Bank Stat-Arb (1h)",
    timeframe: "1h",
    tier: "T0 Collecting",
    lotSize: 30,
    desc: "Cointegrated pairs trading between BankNifty index and synthetic private banking basket; exits at mean reversion.",
    target: "Target: 30 trades / 20 days",
  },
];

export function NSEPanel() {
  const [nseStatus, setNseStatus] = useState<NSEMarketStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [positions, setPositions] = useState<OpenPaperPosition[]>([]);

  // Selected symbol for interactive chart & confluence
  const [selectedSymbol, setSelectedSymbol] = useState("^NSEI");
  const [selectedInterval, setSelectedInterval] = useState("1h");
  const [signal, setSignal] = useState<Signal | null>(null);
  const [loadingSignal, setLoadingSignal] = useState(false);
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const handlePrice = useCallback((p: number) => setLivePrice(p), []);

  const selectedItem = NSE_WATCHLIST.find((w) => w.symbol === selectedSymbol) || NSE_WATCHLIST[0];

  const loadStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const data = await fetchNseStatus();
      setNseStatus(data);
    } catch {
      // fallback handled gracefully
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  const loadPositions = useCallback(async () => {
    try {
      const all = await fetchLabPositions();
      // Filter for NSE related positions
      const nsePos = all.filter(
        (p) =>
          p.symbol.includes(".NS") ||
          p.symbol.startsWith("^") ||
          p.symbol.includes("NIFTY") ||
          p.variantId.includes("nse")
      );
      setPositions(nsePos);
    } catch {
      // ignore
    }
  }, []);

  const loadSignal = useCallback(async (sym: string, intv: string) => {
    setLoadingSignal(true);
    try {
      const market = sym.startsWith("^") ? "nse_index" : "nse_eq";
      const sig = await fetchSignal(sym, intv, market);
      setSignal(sig);
    } catch {
      setSignal(null);
    } finally {
      setLoadingSignal(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    loadPositions();
    const timer = setInterval(() => {
      loadStatus();
      loadPositions();
    }, 10000);
    return () => clearInterval(timer);
  }, [loadStatus, loadPositions]);

  useEffect(() => {
    loadSignal(selectedSymbol, selectedInterval);
  }, [selectedSymbol, selectedInterval, loadSignal]);

  const pcr = nseStatus?.pcr_oi ?? 1.05;
  const pcrSentiment =
    pcr >= 1.2
      ? { label: "Strongly Bullish (Heavy Put Writing)", color: "text-[#00E5A8]" }
      : pcr >= 1.0
      ? { label: "Mildly Bullish / Neutral", color: "text-emerald-400" }
      : pcr >= 0.8
      ? { label: "Mildly Bearish (Call Overhang)", color: "text-amber-400" }
      : { label: "Strongly Bearish (Heavy Call Writing)", color: "text-[#FF4D6A]" };

  return (
    <div className="space-y-6">
      {/* 1. Indian Market Telemetry & IST Clock */}
      <Card className="card-pad border-[var(--accent-bright)]/20 bg-gradient-to-r from-[#0d1627] via-[#090f1d] to-[#0c1424]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <span className="flex h-3 w-3 relative">
                <span
                  className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                    nseStatus?.is_open ? "bg-emerald-400" : "bg-amber-400"
                  }`}
                />
                <span
                  className={`relative inline-flex rounded-full h-3 w-3 ${
                    nseStatus?.is_open ? "bg-emerald-500" : "bg-amber-500"
                  }`}
                />
              </span>
              <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                NSE India F&amp;O Trading Engine
                <span className="rounded-md bg-white/10 px-2 py-0.5 text-xs font-mono font-medium text-slate-300">
                  Zero-Broker-Key Live Pipeline
                </span>
              </h2>
            </div>
            <p className="text-xs text-slate-400">
              Direct public session feed with automated IST market hours, Indian F&amp;O lot sizing, and Section 43(5) tax accounting.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 font-mono text-right shadow-inner">
              <div className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1 justify-end">
                <Clock size={11} className="text-[#00d4ff]" /> Indian Standard Time
              </div>
              <div className="text-base font-bold text-white tracking-wide">
                {nseStatus?.ist_clock || "14:45:00 IST"}
              </div>
              <div className="text-[10px] text-slate-400">
                {nseStatus?.is_open ? "09:15 – 15:30 IST Session" : "Closed (Reopens 09:15 IST)"}
              </div>
            </div>

            <button
              onClick={() => {
                loadStatus();
                loadPositions();
                loadSignal(selectedSymbol, selectedInterval);
              }}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white transition"
              title="Refresh NSE Market Feed"
            >
              <RefreshCw size={16} className={loadingStatus ? "animate-spin" : ""} />
            </button>
          </div>
        </div>

        {/* Ticker Row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-5 pt-4 border-t border-white/10">
          <div className="rounded-xl border border-white/5 bg-[#0a0f1d] p-3">
            <div className="text-[10px] font-mono text-slate-400">NIFTY 50 (^NSEI)</div>
            <div className="mt-1 text-base font-bold text-white font-mono">
              ₹{Number(nseStatus?.nifty?.price || 23015.55).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </div>
            <div className={`text-[11px] font-medium flex items-center gap-0.5 ${(nseStatus?.nifty?.change_pct || 0) >= 0 ? "text-[#00E5A8]" : "text-[#FF4D6A]"}`}>
              {(nseStatus?.nifty?.change_pct || 0) >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
              {(nseStatus?.nifty?.change_pct || 0) > 0 ? "+" : ""}
              {(nseStatus?.nifty?.change_pct || 0).toFixed(2)}%
            </div>
          </div>

          <div className="rounded-xl border border-white/5 bg-[#0a0f1d] p-3">
            <div className="text-[10px] font-mono text-slate-400">BANK NIFTY (^NSEBANK)</div>
            <div className="mt-1 text-base font-bold text-white font-mono">
              ₹{Number(nseStatus?.banknifty?.price || 54636.15).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </div>
            <div className={`text-[11px] font-medium flex items-center gap-0.5 ${(nseStatus?.banknifty?.change_pct || 0) >= 0 ? "text-[#00E5A8]" : "text-[#FF4D6A]"}`}>
              {(nseStatus?.banknifty?.change_pct || 0) >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
              {(nseStatus?.banknifty?.change_pct || 0) > 0 ? "+" : ""}
              {(nseStatus?.banknifty?.change_pct || 0).toFixed(2)}%
            </div>
          </div>

          <div className="rounded-xl border border-white/5 bg-[#0a0f1d] p-3">
            <div className="text-[10px] font-mono text-slate-400">INDIA VIX (^INDIAVIX)</div>
            <div className="mt-1 text-base font-bold text-[#FFB020] font-mono">
              {(nseStatus?.india_vix?.price || 15.4).toFixed(2)}
            </div>
            <div className="text-[10px] text-slate-400">Annualized Volatility</div>
          </div>

          <div className="rounded-xl border border-white/5 bg-[#0a0f1d] p-3">
            <div className="text-[10px] font-mono text-slate-400">PUT / CALL RATIO (PCR)</div>
            <div className="mt-1 text-base font-bold text-[#00d4ff] font-mono">
              {pcr.toFixed(2)}
            </div>
            <div className="text-[10px] text-slate-400">Chg OI: {(nseStatus?.pcr_change_oi || 1.12).toFixed(2)}</div>
          </div>

          <div className="rounded-xl border border-white/5 bg-[#0a0f1d] p-3">
            <div className="text-[10px] font-mono text-slate-400">MAX PAIN STRIKE</div>
            <div className="mt-1 text-base font-bold text-white font-mono">
              {Number(nseStatus?.max_pain || 23000).toLocaleString("en-IN")}
            </div>
            <div className="text-[10px] text-slate-400">Option Expiry Anchor</div>
          </div>

          <div className="rounded-xl border border-white/5 bg-[#0a0f1d] p-3">
            <div className="text-[10px] font-mono text-slate-400">KEY S/R RANGE</div>
            <div className="mt-1 text-xs font-bold text-white font-mono flex items-center justify-between">
              <span className="text-[#00E5A8]">{Number(nseStatus?.put_floor || 22800).toLocaleString("en-IN")}</span>
              <span className="text-slate-500">|</span>
              <span className="text-[#FF4D6A]">{Number(nseStatus?.call_wall || 23200).toLocaleString("en-IN")}</span>
            </div>
            <div className="text-[10px] text-slate-400 flex justify-between">
              <span>Put Floor</span>
              <span>Call Wall</span>
            </div>
          </div>
        </div>

        {/* Warning & Rules Bar */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white/5 p-2.5 text-xs text-slate-300">
          <div className="flex items-center gap-2">
            <ShieldAlert size={14} className="text-[#FFB020] shrink-0" />
            <span>
              <b>MIS 15:15 IST Mandatory Square-Off:</b> All intraday F&amp;O orders auto-liquidate at 15:15 IST. No fresh orders allowed after 14:45 IST.
            </span>
          </div>
          <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
            <span>Market Regime:</span>
            <span className={pcrSentiment.color}>{pcrSentiment.label}</span>
          </div>
        </div>
      </Card>

      {/* 2. Indian Watchlist & Interactive Trading Chart */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 max-w-full">
            {NSE_WATCHLIST.map((item) => {
              const isSelected = selectedSymbol === item.symbol;
              return (
                <button
                  key={item.symbol}
                  onClick={() => setSelectedSymbol(item.symbol)}
                  className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-mono transition-all shrink-0 ${
                    isSelected
                      ? "bg-[var(--accent-bright)] text-black font-bold shadow-[0_0_10px_rgba(0,212,255,0.4)]"
                      : "bg-[#0b101c] text-slate-300 border border-white/10 hover:border-white/20 hover:text-white"
                  }`}
                >
                  <span>{item.symbol}</span>
                  {item.lot > 0 && (
                    <span className={`text-[10px] px-1 py-0.2 rounded ${isSelected ? "bg-black/20 text-black" : "bg-white/10 text-slate-400"}`}>
                      Lot: {item.lot}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-[#080d1a] p-1 text-xs font-mono">
            {["5m", "15m", "1h", "4h", "1d"].map((intv) => (
              <button
                key={intv}
                onClick={() => setSelectedInterval(intv)}
                className={`rounded px-2.5 py-1 transition ${
                  selectedInterval === intv ? "bg-white/20 text-white font-bold" : "text-slate-400 hover:text-white"
                }`}
              >
                {intv}
              </button>
            ))}
          </div>
        </div>

        {/* Chart + Signal Card */}
        <div className="space-y-6">
          <PriceChart
            symbol={selectedSymbol}
            interval={selectedInterval}
            market={selectedItem.category}
            onPrice={handlePrice}
          />

          {loadingSignal && (
            <Card className="card-pad flex items-center gap-2 text-sm text-slate-400">
              <Activity size={15} className="animate-spin text-[var(--accent-bright)]" /> Computing institutional NSE factor confluence…
            </Card>
          )}

          {!loadingSignal && signal && (
            <SignalCard s={signal} livePrice={livePrice} />
          )}
        </div>
      </div>

      {/* 3. Open Paper Trades & Positions for NSE */}
      <Card className="card-pad">
        <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-4">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-[var(--accent-bright)]" />
            <h3 className="text-sm font-semibold text-white">NSE Open Positions &amp; Paper F&amp;O Book</h3>
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
              {positions.length} Active
            </span>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Execution: Zero-Cost Paper Ledger · Fixed 1R Friction
          </span>
        </div>

        {positions.length === 0 ? (
          <div className="rounded-xl border border-white/5 bg-[#070b14] p-6 text-center text-xs text-slate-400 space-y-2">
            <Zap size={24} className="mx-auto text-slate-600 mb-1" />
            <div>No open NSE positions right now.</div>
            <div className="text-[11px] text-slate-500">
              The engine initiates trades when L11 (Nifty ORB 15m), L12 (RS Top 50), or L13 (BankNifty Stat-Arb) setups clear EV and PCR gates.
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-white/5 text-[11px] text-slate-400">
                  <th className="py-2 px-3">Position ID</th>
                  <th className="py-2 px-3">Variant / Strategy</th>
                  <th className="py-2 px-3">Symbol</th>
                  <th className="py-2 px-3">Side</th>
                  <th className="py-2 px-3">Entry (₹)</th>
                  <th className="py-2 px-3">Stop Loss (₹)</th>
                  <th className="py-2 px-3">Target (₹)</th>
                  <th className="py-2 px-3">Unrealized R</th>
                  <th className="py-2 px-3">Age Bars</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {positions.map((p) => {
                  const isLong = p.side === "long";
                  return (
                    <tr key={p.positionId} className="hover:bg-white/[0.02] transition">
                      <td className="py-2.5 px-3 text-slate-300 font-semibold">{p.positionId}</td>
                      <td className="py-2.5 px-3 text-[#00d4ff]">{p.variantId}</td>
                      <td className="py-2.5 px-3 font-bold text-white">{p.symbol}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold ${
                            isLong ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                          }`}
                        >
                          {isLong ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
                          {p.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-200">₹{p.entry.toLocaleString("en-IN")}</td>
                      <td className="py-2.5 px-3 text-rose-400">₹{p.stop.toLocaleString("en-IN")}</td>
                      <td className="py-2.5 px-3 text-emerald-400">{p.target ? `₹${p.target.toLocaleString("en-IN")}` : "Runner"}</td>
                      <td className="py-2.5 px-3 font-bold text-slate-200">
                        {p.unrealizedR > 0 ? `+${p.unrealizedR.toFixed(2)}R` : `${p.unrealizedR.toFixed(2)}R`}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{p.ageBars} bars</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 4. Institutional NSE Catalog (L11–L13) */}
      <Card className="card-pad">
        <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-4">
          <div className="flex items-center gap-2">
            <Flame size={16} className="text-[#FFB020]" />
            <h3 className="text-sm font-semibold text-white">StarkX Institutional Catalog: Indian NSE Strategies</h3>
          </div>
          <a
            href="/lab"
            className="inline-flex items-center gap-1 text-xs text-[var(--accent-bright)] hover:underline"
          >
            Open StarkX Lab <ExternalLink size={12} />
          </a>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {NSE_LAB_STRATEGIES.map((s) => (
            <div
              key={s.id}
              className="rounded-xl border border-white/10 bg-[#070b16] p-4 space-y-3 hover:border-white/20 transition"
            >
              <div className="flex items-center justify-between">
                <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] font-mono font-semibold text-slate-300">
                  {s.timeframe}
                </span>
                <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[10px] font-mono text-indigo-400 border border-indigo-500/20">
                  {s.tier}
                </span>
              </div>

              <div>
                <h4 className="text-sm font-bold text-white tracking-tight">{s.name}</h4>
                <p className="mt-1 text-xs text-slate-400 leading-relaxed">{s.desc}</p>
              </div>

              <div className="pt-2 border-t border-white/5 flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span>Lot: <b>{s.lotSize}</b></span>
                <span className="text-slate-500">{s.target}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* 5. Indian Statutory Charges & Section 43(5) Tax Sleeve */}
      <Card className="card-pad">
        <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-4">
          <div className="flex items-center gap-2">
            <Scale size={16} className="text-[#00d4ff]" />
            <h3 className="text-sm font-semibold text-white">
              Indian Statutory Friction &amp; Tax Structure (Sec 43(5) vs Sec 115BBH)
            </h3>
          </div>
          <span className="text-[11px] font-mono text-slate-400">Government of India / SEBI Tariffs</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Statutory Charges Table */}
          <div className="rounded-xl border border-white/10 bg-[#080d19] p-4 text-xs space-y-3 font-mono">
            <div className="font-bold text-white text-sm pb-1 border-b border-white/10 flex items-center gap-1.5">
              <Percent size={14} className="text-[#FFB020]" />
              Exact F&amp;O Transaction Friction (Turnover Based)
            </div>
            <div className="space-y-1.5 text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-400">Securities Transaction Tax (STT):</span>
                <span>0.125% on Option Premium / 0.02% Futures</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">NSE Exchange Turnover:</span>
                <span>0.00325% of Turnover</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">State Stamp Duty:</span>
                <span>0.003% (₹300 per crore)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">SEBI Regulatory Turnover Fee:</span>
                <span>₹10 per crore</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Goods &amp; Services Tax (GST):</span>
                <span>18% on (Brokerage + Exchange Fees)</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-white/10 font-bold text-white">
                <span>Model Drag per Nifty F&amp;O Turn:</span>
                <span className="text-[#00E5A8]">~0.0195R (Negligible Drag)</span>
              </div>
            </div>
          </div>

          {/* Section 43(5) vs Section 115BBH Card */}
          <div className="rounded-xl border border-white/10 bg-[#080d19] p-4 text-xs space-y-3">
            <div className="font-bold text-white text-sm pb-1 border-b border-white/10 flex items-center gap-1.5">
              <ShieldCheck size={14} className="text-[#00E5A8]" />
              Section 43(5) Non-Speculative Business Advantage
            </div>
            <p className="text-slate-300 text-[11px] leading-relaxed">
              Unlike Crypto under <b>Section 115BBH</b> (which levies a punitive flat 30% + 4% cess with <b>zero loss offset</b> and 1% TDS), Indian F&amp;O under <b>Section 43(5)</b> is treated as non-speculative business income:
            </p>
            <ul className="space-y-1 text-[11px] text-slate-300 list-disc list-inside">
              <li><b>100% Netting:</b> Losses in trade A directly offset profits in trade B.</li>
              <li><b>Full Expense Deductions:</b> STT, brokerage, platform fees, and research are 100% tax-deductible.</li>
              <li><b>8-Year Loss Carry-Forward:</b> Net annual losses can offset future profits up to 8 financial years.</li>
            </ul>
            <div className="pt-2 text-[10px] text-slate-500 font-mono">
              Statutory notice: Decision-support illustration only. Consult your Chartered Accountant.
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
