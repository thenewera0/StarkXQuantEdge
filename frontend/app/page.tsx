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
import { ViewHeader } from "@/components/PanelShell";
import { Card } from "@/components/ui";
import { Activity, Bitcoin, DollarSign, Sparkles, RefreshCw } from "lucide-react";

type Market = "crypto" | "forex";
type View = "overview" | "flash" | "live" | "markets" | "invest" | "fund" | "analytics" | "history" | "arb";

const VIEWS: View[] = ["overview", "flash", "live", "markets", "invest", "fund", "analytics", "history", "arb"];

const WATCHLISTS: Record<Market, string[]> = {
  crypto: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
  forex: ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD"],
};

const TIMEFRAMES = [
  { label: "Intraday", interval: "15m" },
  { label: "Short", interval: "1h" },
  { label: "Short+", interval: "4h" },
  { label: "Swing", interval: "1d" },
  { label: "Long", interval: "1w" },
];

/** Sidebar drives this via the URL hash — real navigation, back button works. */
function useHashView(): View {
  const [view, setView] = useState<View>("overview");
  useEffect(() => {
    const read = () => {
      const h = (window.location.hash || "").replace("#", "") as View;
      setView(VIEWS.includes(h) ? h : "overview");
    };
    read();
    window.addEventListener("hashchange", read);
    window.addEventListener("popstate", read);   // browser back/forward
    return () => {
      window.removeEventListener("hashchange", read);
      window.removeEventListener("popstate", read);
    };
  }, []);
  // Views replace the whole page, so start each one at the top.
  useEffect(() => { document.querySelector("main")?.scrollTo({ top: 0 }); }, [view]);
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

  // Only fetch the analytics signal when that view is actually visible.
  useEffect(() => {
    if (view === "analytics") load(symbol, interval, market);
  }, [symbol, interval, market, load, view]);

  useEffect(() => {
    if (view !== "analytics") return;
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
    setMarket((s.market as Market) ?? "crypto");
    setInterval(s.interval); setSymbol(s.symbol);
    window.location.hash = "analytics";
  }

  if (!mounted) return null;

  return (
    <div className="rise w-full max-w-[1500px] mx-auto">
      {/* ---------------- OVERVIEW ---------------- */}
      {view === "overview" && (
        <>
          <ViewHeader title="Overview" subtitle="Live capital, open risk, and what the engine is doing right now." />
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
          <ViewHeader title="Flash Bot" subtitle="Fast 15m/1h hunter — momentum, breakout and mean-reversion snaps." />
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <FlashBotPanel />
            <LiveTradesPanel refreshKey={historyKey} />
          </div>
        </>
      )}

      {/* ---------------- LIVE TRADES ---------------- */}
      {view === "live" && (
        <>
          <ViewHeader title="Live Trades" subtitle="Every open position, marked to the live price." />
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
            title="Markets"
            subtitle="Every instrument the engine can see — crypto, forex, commodities, indices and rates, all on free keyless data."
          />
          <UniversePanel />
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
            title="Engine Analytics"
            subtitle="Inspect any market through the full confluence engine."
            right={
              <button onClick={() => load(symbol, interval, market)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[rgba(255,255,255,0.1)] bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10">
                <RefreshCw size={14} /> Refresh
              </button>
            }
          />

          <div className="mb-5 flex flex-wrap items-center gap-3">
            <div className="seg">
              {(["crypto", "forex"] as Market[]).map((m) => (
                <button key={m} data-active={market === m} onClick={() => switchMarket(m)} className="flex items-center gap-1.5 capitalize">
                  {m === "crypto" ? <Bitcoin size={14} /> : <DollarSign size={14} />}{m}
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
              <button key={sym} className="chip" data-active={symbol === sym} onClick={() => setSymbol(sym)}>{sym}</button>
            ))}
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="ml-auto w-40 rounded-lg border border-[rgba(255,255,255,0.1)] bg-white/5 px-3 py-2 text-sm text-white outline-none transition-colors focus:border-[var(--accent-bright)]"
              placeholder="Symbol"
            />
          </div>

          {loading && (
            <Card className="card-pad flex items-center gap-2 text-sm text-slate-400">
              <Activity size={15} className="shimmer text-[var(--accent-bright)]" /> Loading {symbol} {interval}…
            </Card>
          )}
          {error && (
            <Card className="card-pad border-rose-500/20 bg-rose-500/10 text-sm text-[var(--loss)]">{error}</Card>
          )}

          {!loading && !error && signal && (
            <div className="space-y-6">
              <PriceChart symbol={symbol} interval={interval} market={market} onPrice={handlePrice} />
              <SignalCard s={signal} livePrice={livePrice} />

              <Card className="card-pad">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-1.5 text-sm font-semibold tracking-tight text-white">
                      <Sparkles size={15} className="text-[var(--accent-bright)]" /> Deep AI Analysis
                    </div>
                    <div className="mt-0.5 text-xs text-slate-400">
                      Bull and Bear analysts argue the numbers; a Risk Manager rules on final conviction.
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
    </div>
  );
}
