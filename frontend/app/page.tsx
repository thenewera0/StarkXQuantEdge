"use client";

import { useCallback, useEffect, useState } from "react";
import {
  MetricCards,
  PortfolioOverview,
  AssetAllocation,
  TopPerformers,
  RecentTransactions,
  AIInsightsWidget,
} from "@/components/DashboardComponents";
import { fetchSignal, fetchSignalLite, fetchDecision, type Signal, type Decision, type EmittedSignal } from "@/lib/api";
import { SignalCard } from "@/components/SignalCard";
import { PriceChart } from "@/components/PriceChart";
import { DebatePanel } from "@/components/DebatePanel";
import { HistoryPanel } from "@/components/HistoryPanel";
import { ScannerPanel } from "@/components/ScannerPanel";
import { SummaryPanel } from "@/components/SummaryPanel";
import { TradeHistoryPanel } from "@/components/TradeHistoryPanel";
import { ArbPanel } from "@/components/ArbPanel";
import { FlashBotPanel } from "@/components/FlashBotPanel";
import { LiveTradesPanel } from "@/components/LiveTradesPanel";
import { CombinedPnl } from "@/components/CombinedPnl";
import { InvestmentsPanel } from "@/components/InvestmentsPanel";
import { AllocationModelPanel } from "@/components/AllocationModelPanel";
import { RebalancePanel } from "@/components/RebalancePanel";
import { UniversePanel } from "@/components/UniversePanel";
import { RiskPanel } from "@/components/RiskPanel";
import { PortfolioPanel } from "@/components/PortfolioPanel";
import { PerformancePanel } from "@/components/PerformancePanel";
import { NSEPanel } from "@/components/NSEPanel";
import { ViewHeader } from "@/components/PanelShell";
import { Card } from "@/components/ui";
import { Activity, Bitcoin, DollarSign, Sparkles, RefreshCw, Percent, ShieldCheck } from "lucide-react";
import { fetchLabTax, type LabTaxScenarioRow } from "@/lib/api";

type Market = "crypto" | "forex" | "nse_index" | "nse_eq";
type View = "overview" | "flash" | "live" | "markets" | "invest" | "fund" | "analytics" | "history" | "arb" | "nse";

const VIEWS: View[] = ["overview", "flash", "live", "markets", "invest", "fund", "analytics", "history", "arb", "nse"];

const WATCHLISTS: Record<Market, string[]> = {
  crypto: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
  nse_index: ["^NSEI", "^NSEBANK", "^CNXIT", "^INDIAVIX"],
  nse_eq: ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS", "SBIN.NS"],
  forex: ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD"],
};

const TIMEFRAMES = [
  { label: "1m", interval: "1m" },
  { label: "5m", interval: "5m" },
  { label: "15m", interval: "15m" },
  { label: "1h", interval: "1h" },
  { label: "4h", interval: "4h" },
  { label: "1d", interval: "1d" },
];

/** Sidebar drives this via ?tab=... and URL hash — real navigation, back button works. */
function useHashView(): View {
  const [view, setView] = useState<View>("overview");
  useEffect(() => {
    const parse = () => {
      const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
      const tabParam = params?.get("tab");
      const hashParam = typeof window !== "undefined" ? (window.location.hash || "").replace("#", "") : "";
      const raw = tabParam || hashParam || "overview";

      let normalized: View = "overview";
      if (raw === "investments" || raw === "invest") normalized = "invest";
      else if (raw === "arbitrage" || raw === "arb") normalized = "arb";
      else if (raw === "nse" || raw === "indian" || raw === "nse-india") normalized = "nse";
      else if (VIEWS.includes(raw as View)) normalized = raw as View;
      setView(normalized);
    };

    parse();

    const handleCustomChange = (e: Event) => {
      const customEvent = e as CustomEvent<string>;
      const raw = customEvent.detail;
      let normalized: View = "overview";
      if (raw === "investments" || raw === "invest") normalized = "invest";
      else if (raw === "arbitrage" || raw === "arb") normalized = "arb";
      else if (raw === "nse" || raw === "indian" || raw === "nse-india") normalized = "nse";
      else if (VIEWS.includes(raw as View)) normalized = raw as View;
      setView(normalized);
    };

    window.addEventListener("hashchange", parse);
    window.addEventListener("popstate", parse);
    window.addEventListener("starkx_tab_change", handleCustomChange);
    return () => {
      window.removeEventListener("hashchange", parse);
      window.removeEventListener("popstate", parse);
      window.removeEventListener("starkx_tab_change", handleCustomChange);
    };
  }, []);

  useEffect(() => {
    document.querySelector("main")?.scrollTo({ top: 0 });
  }, [view]);

  return view;
}

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const view = useHashView();

  const [market, setMarket] = useState<Market>("crypto");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [interval, setInterval] = useState("4h");
  const [signal, setSignal] = useState<Signal | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [decision, setDecision] = useState<Decision | null>(null);
  const [debating, setDebating] = useState(false);
  const [debateError, setDebateError] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [taxRows, setTaxRows] = useState<LabTaxScenarioRow[]>([]);
  const handlePrice = useCallback((p: number) => setLivePrice(p), []);

  const load = useCallback(async (sym: string, tf: string, mkt: Market) => {
    setLoading(true); setError(null); setDecision(null); setDebateError(null); setLivePrice(null);
    try { setSignal(await fetchSignal(sym, tf, mkt)); }
    catch (e) { setSignal(null); setError(e instanceof Error ? e.message : "Request failed"); }
    finally { setLoading(false); }
  }, []);

  const runDebate = useCallback(async () => {
    setDebating(true); setDebateError(null);
    try { setDecision(await fetchDecision(symbol, interval, market)); setHistoryKey((k) => k + 1); }
    catch (e) { setDecision(null); setDebateError(e instanceof Error ? e.message : "Debate failed"); }
    finally { setDebating(false); }
  }, [symbol, interval, market]);

  // Fetch signal when markets view is visible
  useEffect(() => {
    if (view === "markets") load(symbol, interval, market);
  }, [symbol, interval, market, load, view]);

  // Fetch tax scenarios when analytics view is visible
  useEffect(() => {
    if (view === "analytics") {
      fetchLabTax().then(setTaxRows).catch(() => {});
    }
  }, [view]);

  // Listen for global symbol pick (e.g. from command palette)
  useEffect(() => {
    const handleSymbolPick = (e: any) => {
      if (e.detail?.symbol) {
        const sym = e.detail.symbol;
        setSymbol(sym);
        if (e.detail.market) {
          setMarket(e.detail.market as Market);
        } else if (sym.endsWith(".NS") || sym.startsWith("^")) {
          setMarket(sym.startsWith("^") ? "nse_index" : "nse_eq");
        }
        window.dispatchEvent(new CustomEvent("starkx_tab_change", { detail: "markets" }));
        const url = new URL(window.location.href);
        url.pathname = "/";
        url.searchParams.set("tab", "markets");
        url.hash = "markets";
        window.history.pushState({}, "", url.toString());
      }
    };
    window.addEventListener("starkx_symbol_pick", handleSymbolPick);
    return () => window.removeEventListener("starkx_symbol_pick", handleSymbolPick);
  }, []);

  useEffect(() => {
    if (view !== "markets") return;
    const id = window.setInterval(() => {
      fetchSignalLite(symbol, interval, market)
        .then((lite) => setSignal((prev) => (prev ? { ...lite, explanation: prev.explanation } : lite)))
        .catch(() => {});
    }, 30000);
    return () => window.clearInterval(id);
  }, [symbol, interval, market, view]);

  useEffect(() => { setMounted(true); }, []);

  function switchMarket(mkt: Market) { setMarket(mkt); setSymbol(WATCHLISTS[mkt][0]); }
  function pickSignal(s: EmittedSignal) {
    let mkt: Market = "crypto";
    if (s.market === "forex") mkt = "forex";
    else if (s.market === "nse_index" || s.symbol.startsWith("^")) mkt = "nse_index";
    else if (s.market === "nse_eq" || s.symbol.endsWith(".NS")) mkt = "nse_eq";
    setMarket(mkt);
    setInterval(s.interval); setSymbol(s.symbol);
    window.dispatchEvent(new CustomEvent("starkx_tab_change", { detail: "markets" }));
    const url = new URL(window.location.href);
    url.pathname = "/";
    url.searchParams.set("tab", "markets");
    url.hash = "markets";
    window.history.pushState({}, "", url.toString());
  }

  if (!mounted) return null;

  return (
    <div className="rise w-full max-w-[1500px] mx-auto">
      {/* ---------------- OVERVIEW ---------------- */}
      {view === "overview" && (
        <>
          <ViewHeader title="Overview" subtitle="Virtual capital, open risk, and what the engine is doing right now." />
          <div className="space-y-6">
            <MetricCards />
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <div className="xl:col-span-2"><PortfolioOverview /></div>
              <CombinedPnl refreshKey={historyKey} />
            </div>
            <RiskPanel refreshKey={historyKey} />
            <LiveTradesPanel refreshKey={historyKey} />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <AssetAllocation />
              <TopPerformers />
              <AIInsightsWidget />
            </div>
          </div>
        </>
      )}

      {/* ---------------- FLASH BOT ---------------- */}
      {view === "flash" && (
        <>
          <ViewHeader
            title="Flash Bot (Paper Incubator)"
            subtitle="Autonomous 1h crypto scalper testing environment. Runs 100% on paper — completely isolated virtual sandbox."
          />
          <div className="w-full">
            <FlashBotPanel />
          </div>
        </>
      )}

      {/* ---------------- LIVE TRADES ---------------- */}
      {view === "live" && (
        <>
          <ViewHeader title="Open Positions (Paper)" subtitle="Every open position, marked to the public price." />
          <div className="space-y-6">
            <RiskPanel refreshKey={historyKey} />
            <LiveTradesPanel refreshKey={historyKey} />
            <CombinedPnl refreshKey={historyKey} />
          </div>
        </>
      )}

      {/* ---------------- MARKETS ---------------- */}
      {view === "markets" && (
        <>
          <ViewHeader
            title="Markets &amp; Quantitative Scanner"
            subtitle="Free, zero-API-key live and historical streaming across Indian NSE Equities, Index F&amp;O, Crypto, and Global FX."
            right={
              <button onClick={() => load(symbol, interval, market)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[rgba(255,255,255,0.1)] bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10">
                <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh Feed
              </button>
            }
          />

          <div className="mb-5 flex flex-wrap items-center gap-3">
            <div className="seg">
              {(["crypto", "nse_index", "nse_eq", "forex"] as Market[]).map((m) => (
                <button key={m} data-active={market === m} onClick={() => switchMarket(m)} className="flex items-center gap-1.5 uppercase font-mono text-xs">
                  {m === "crypto" ? <Bitcoin size={14} /> : m.startsWith("nse") ? <Activity size={14} /> : <DollarSign size={14} />}{m.replace("_", " ")}
                </button>
              ))}
            </div>
            <div className="seg">
              {TIMEFRAMES.map((tf) => (
                <button key={tf.interval} data-active={interval === tf.interval} onClick={() => setInterval(tf.interval)}>
                  {tf.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-5 flex flex-wrap items-center gap-2">
            {WATCHLISTS[market].map((sym) => (
              <button key={sym} className="chip font-mono" data-active={symbol === sym} onClick={() => setSymbol(sym)}>{sym}</button>
            ))}
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="ml-auto w-44 rounded-lg border border-[rgba(255,255,255,0.1)] bg-white/5 px-3 py-2 text-sm font-mono text-white outline-none transition-colors focus:border-[var(--accent-bright)]"
              placeholder="Search symbol (e.g. ^NSEI)"
            />
          </div>

          {loading && (
            <Card className="card-pad flex items-center gap-2 text-sm text-slate-400">
              <Activity size={15} className="shimmer text-[var(--accent-bright)]" /> Loading live feed {symbol} {interval}…
            </Card>
          )}
          {error && (
            <Card className="card-pad border-rose-500/20 bg-rose-500/10 text-sm text-[var(--loss)]">{error}</Card>
          )}

          {!loading && !error && signal && (
            <div className="space-y-6 mb-8">
              <PriceChart symbol={symbol} interval={interval} market={market} onPrice={handlePrice} />
              <SignalCard s={signal} livePrice={livePrice} />

              <Card className="card-pad">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-1.5 text-sm font-semibold tracking-tight text-white">
                      <Sparkles size={15} className="text-[var(--accent-bright)]" /> 3-Agent AI Qualitative Debate
                    </div>
                    <div className="mt-0.5 text-xs text-slate-400">
                      Bull and Bear quant analysts debate factor confluence; Risk Manager delivers synthesized conviction score.
                    </div>
                  </div>
                  <button onClick={runDebate} disabled={debating}
                    className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-br from-[var(--accent-bright)] to-[var(--accent)] px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:opacity-90 disabled:opacity-60">
                    <Sparkles size={15} />{debating ? "Agents debating…" : decision ? "Re-run debate" : "Run AI debate"}
                  </button>
                </div>
                {debateError && <div className="mt-3 text-sm text-[var(--loss)]">{debateError}</div>}
              </Card>

              {decision && !debating && <DebatePanel d={decision} />}
            </div>
          )}

          <div className="mt-8">
            <h4 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
              <Activity size={16} className="text-[var(--accent-bright)]" /> Global Allocatable Universe Explorer
            </h4>
            <UniversePanel />
          </div>
        </>
      )}

      {/* ---------------- INVESTMENTS ---------------- */}
      {view === "invest" && (
        <>
          <ViewHeader title="Long-term Investments" subtitle="What deserves capital for months — screened on momentum, trend quality and risk-adjusted return." />
          <div className="space-y-6">
            <RebalancePanel />
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <AllocationModelPanel />
              <InvestmentsPanel />
            </div>
          </div>
        </>
      )}

      {/* ---------------- FUND / ALLOCATION ---------------- */}
      {view === "fund" && (
        <>
          <ViewHeader title="Fund Allocation" subtitle="How capital is split across strategy sleeves — risk parity, tilted by proven expectancy." />
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <PortfolioPanel />
            <CombinedPnl refreshKey={historyKey} />
          </div>
        </>
      )}

      {/* ---------------- ANALYTICS ---------------- */}
      {view === "analytics" && (
        <>
          <ViewHeader
            title="Quantitative Performance &amp; Calibration Cockpit"
            subtitle="Track realized R-distributions, Kelly tier sizing, regime breakdown, and post-tax Section 43(5) vs 115BBH efficiency."
          />
          <div className="space-y-6">
            <PerformancePanel refreshKey={historyKey} />
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <SummaryPanel refreshKey={historyKey} />
              <CombinedPnl refreshKey={historyKey} />
            </div>

            {/* Indian Statutory Tax Comparison: Crypto 115BBH vs NSE Sec 43(5) */}
            <Card className="card-pad">
              <div className="flex items-center justify-between pb-3 border-b border-[var(--line)]">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Percent size={16} className="text-[#FFB020]" />
                  Statutory Tax Drag Comparison: Crypto Sec 115BBH vs NSE F&amp;O Sec 43(5)
                </h3>
                <span className="text-[11px] font-mono text-slate-400">Indian Income Tax Act, 1961</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                {taxRows.map((t) => (
                  <div key={t.scenario} className="p-3.5 rounded-xl border border-[var(--line)] bg-[var(--surface-raised)] text-xs space-y-2">
                    <div className="flex items-center justify-between font-bold text-white pb-1.5 border-b border-[var(--line)]">
                      <span>Scenario {t.scenario}</span>
                      <span className="text-[#FFB020] font-mono">{t.effectiveTaxRatePct.toFixed(1)}% Eff. Tax</span>
                    </div>
                    <div className="text-[11px] text-slate-400 leading-tight">{t.name}</div>
                    <div className="space-y-1 pt-1 text-[11px]">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Gross Gain:</span>
                        <span className="text-[#00E5A8] font-mono font-medium">+${t.grossGainUsd.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Gross Loss:</span>
                        <span className="text-[#FF4D6A] font-mono font-medium">-${t.grossLossUsd.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">TDS (1%) + Cess:</span>
                        <span className="text-slate-300 font-mono">${(t.tdsDeductedUsd + t.cessUsd).toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between font-bold pt-1.5 border-t border-[var(--line)]">
                        <span className="text-white">Net After-Tax:</span>
                        <span className={`font-mono ${t.netProfitAfterTaxUsd >= 0 ? "text-[#00E5A8]" : "text-[#FF4D6A]"}`}>
                          ${t.netProfitAfterTaxUsd.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-3 p-2.5 rounded-lg bg-white/5 border border-white/10 text-[11px] text-slate-400 flex items-center gap-2">
                <ShieldCheck size={14} className="text-[#4DA3FF] shrink-0" />
                <span>
                  Notice: Under Section 43(5), Indian F&amp;O trading allows 100% loss offset, business expense deductions (STT, Brokerage, GST), and 8-year loss carry-forward, avoiding the punitive 31.2% flat gross tax drag of Section 115BBH.
                </span>
              </div>
            </Card>
          </div>
        </>
      )}

      {/* ---------------- HISTORY ---------------- */}
      {view === "history" && (
        <>
          <ViewHeader title="Trade History" subtitle="Every closed trade, what the engine learned, and the scanner feed." />
          <div className="space-y-6">
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <SummaryPanel refreshKey={historyKey} />
              <ScannerPanel onPick={pickSignal} onScanned={() => setHistoryKey((k) => k + 1)} />
            </div>
            <TradeHistoryPanel refreshKey={historyKey} />
            <div id="transactions"><RecentTransactions /></div>
            <HistoryPanel refreshKey={historyKey} />
          </div>
        </>
      )}

      {/* ---------------- ARBITRAGE ---------------- */}
      {view === "arb" && (
        <>
          <ViewHeader title="Arbitrage" subtitle="Funding carry, triangular cycles and cross-exchange spreads — EV-gated after costs." />
          <ArbPanel />
        </>
      )}

      {/* ---------------- NSE INDIA F&O ---------------- */}
      {view === "nse" && (
        <>
          <ViewHeader
            title="NSE India Equities &amp; F&amp;O Trading Engine"
            subtitle="Live IST market hours, zero-cost public session data, option chain Greek radar, and Section 43(5) tax sleeve."
          />
          <NSEPanel />
        </>
      )}
    </div>
  );
}
