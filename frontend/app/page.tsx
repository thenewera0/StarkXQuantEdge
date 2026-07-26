"use client";

import { useCallback, useEffect, useState } from "react";
import { 
  MetricCards, 
  PortfolioOverview, 
  AssetAllocation, 
  TopPerformers, 
  RecentTransactions, 
  AIInsightsWidget 
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
import { Card } from "@/components/ui";
import { Activity, Bitcoin, DollarSign, Sparkles, RefreshCw } from "lucide-react";

type Market = "crypto" | "forex";

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

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
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
    setLoading(true);
    setError(null);
    setDecision(null);
    setDebateError(null);
    setLivePrice(null);
    try {
      setSignal(await fetchSignal(sym, tf, mkt));
    } catch (e) {
      setSignal(null);
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const runDebate = useCallback(async () => {
    setDebating(true);
    setDebateError(null);
    try {
      setDecision(await fetchDecision(symbol, interval, market));
      setHistoryKey((k) => k + 1);
    } catch (e) {
      setDecision(null);
      setDebateError(e instanceof Error ? e.message : "Debate failed");
    } finally {
      setDebating(false);
    }
  }, [symbol, interval, market]);

  useEffect(() => { load(symbol, interval, market); }, [symbol, interval, market, load]);

  useEffect(() => {
    const id = window.setInterval(() => {
      fetchSignalLite(symbol, interval, market)
        .then((lite) => setSignal((prev) => (prev ? { ...lite, explanation: prev.explanation } : lite)))
        .catch(() => {});
    }, 30000);
    return () => window.clearInterval(id);
  }, [symbol, interval, market]);

  useEffect(() => {
    setMounted(true);
  }, []);

  function switchMarket(mkt: Market) {
    setMarket(mkt);
    setSymbol(WATCHLISTS[mkt][0]);
  }

  function pickSignal(s: EmittedSignal) {
    setMarket((s.market as Market) ?? "crypto");
    setInterval(s.interval);
    setSymbol(s.symbol);
  }

  if (!mounted) return null;

  return (
    <div className="rise w-full max-w-[1400px] mx-auto space-y-8">
      {/* Top row: Metric cards */}
      <MetricCards />
      
      {/* Middle row: Portfolio Area Chart */}
      <div id="portfolio" className="w-full">
        <PortfolioOverview />
      </div>
      
      {/* Bottom row grid: Allocation, Performers, Transactions, AI */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1">
          <AssetAllocation />
        </div>
        <div className="lg:col-span-1">
          <TopPerformers />
        </div>
        <div id="transactions" className="lg:col-span-1">
          <RecentTransactions />
        </div>
        <div className="lg:col-span-1">
          <AIInsightsWidget />
        </div>
      </div>

      <div id="analytics" className="pt-8 border-t border-[rgba(255,255,255,0.05)]">
        <h2 className="text-xl font-bold text-white mb-6">Engine Analytics</h2>
        
        {/* Controls */}
        <div className="mb-6 flex flex-wrap items-center gap-3">
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
          <button onClick={() => load(symbol, interval, market)} className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-[rgba(255,255,255,0.1)] bg-white/5 px-3 py-2 text-sm text-slate-300 hover:bg-white/10 transition-colors">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <div id="watchlist" className="mb-6 flex flex-wrap items-center gap-2">
          {WATCHLISTS[market].map((sym) => (
            <button key={sym} className="chip" data-active={symbol === sym} onClick={() => setSymbol(sym)}>{sym}</button>
          ))}
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="ml-auto w-40 rounded-lg border border-[rgba(255,255,255,0.1)] bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-[#00d4ff] transition-colors"
            placeholder="Symbol"
          />
        </div>

        {loading && (
          <Card className="card-pad flex items-center gap-2 text-sm text-slate-400">
            <Activity size={15} className="shimmer text-[#00d4ff]" /> Loading {symbol} {interval}…
          </Card>
        )}

        {error && (
          <Card className="card-pad text-sm text-rose-400 bg-rose-500/10 border-rose-500/20">
            {error}
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <SummaryPanel refreshKey={historyKey} />
          <ScannerPanel onPick={pickSignal} onScanned={() => setHistoryKey((k) => k + 1)} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <TradeHistoryPanel refreshKey={historyKey} />
          <ArbPanel />
        </div>

        {!loading && !error && signal && (
          <div className="space-y-6">
            <PriceChart symbol={symbol} interval={interval} market={market} onPrice={handlePrice} />
            <SignalCard s={signal} livePrice={livePrice} />

            <Card className="card-pad border-[rgba(0,102,255,0.3)] bg-gradient-to-br from-[#090b14] to-[#05070c]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-1.5 text-sm font-semibold tracking-tight text-white">
                    <Sparkles size={15} className="text-[#00d4ff]" /> Deep AI Analysis
                  </div>
                  <div className="mt-0.5 text-xs text-slate-400">
                    Bull and Bear analysts argue the data; a Risk Manager rules on the final conviction.
                  </div>
                </div>
                <button
                  onClick={runDebate}
                  disabled={debating}
                  className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-[#0066ff] to-[#00d4ff] px-4 py-2 text-sm font-medium text-white shadow-[0_0_15px_rgba(0,102,255,0.3)] transition hover:opacity-90 disabled:opacity-60"
                >
                  <Sparkles size={15} />
                  {debating ? "Agents debating…" : decision ? "Re-run AI debate" : "Run AI debate"}
                </button>
              </div>

              {debating && (
                <div className="mt-4 space-y-1.5 text-xs text-slate-400">
                  <div className="shimmer text-[#00d4ff]">Bull analyst building the long case…</div>
                  <div className="shimmer text-rose-400">Bear analyst rebutting…</div>
                  <div className="shimmer text-violet-400">Risk manager weighing the verdict…</div>
                </div>
              )}
              {debateError && <div className="mt-3 text-sm text-rose-400 bg-rose-500/10 p-2 rounded">{debateError}</div>}
            </Card>

            {decision && !debating && <DebatePanel d={decision} />}

            <HistoryPanel refreshKey={historyKey} />
          </div>
        )}
      </div>
    </div>
  );
}
