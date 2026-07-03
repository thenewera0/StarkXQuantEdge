"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchSignal, fetchSignalLite, fetchDecision, type Signal, type Decision } from "@/lib/api";
import { SignalCard } from "@/components/SignalCard";
import { PriceChart } from "@/components/PriceChart";
import { DebatePanel } from "@/components/DebatePanel";
import { HistoryPanel } from "@/components/HistoryPanel";
import { ScannerPanel } from "@/components/ScannerPanel";
import { PerformancePanel } from "@/components/PerformancePanel";
import { SummaryPanel } from "@/components/SummaryPanel";
import { Card } from "@/components/ui";
import type { EmittedSignal } from "@/lib/api";
import { Activity, Bitcoin, DollarSign, Sparkles, Gauge, RefreshCw } from "lucide-react";

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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export default function Home() {
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
  const [dbOn, setDbOn] = useState<boolean | null>(null);
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

  // Live auto-refresh: re-fetch the DETERMINISTIC signal every 30s (NO LLM cost).
  // Preserve the existing rationale so the card keeps its narrative between full loads.
  useEffect(() => {
    const id = window.setInterval(() => {
      fetchSignalLite(symbol, interval, market)
        .then((lite) => setSignal((prev) => (prev ? { ...lite, explanation: prev.explanation } : lite)))
        .catch(() => {});
    }, 30000);
    return () => window.clearInterval(id);
  }, [symbol, interval, market]);

  useEffect(() => {
    fetch(`${API_BASE}/db/status`).then((r) => r.json()).then((d) => setDbOn(!!d.reachable)).catch(() => setDbOn(false));
  }, []);

  function switchMarket(mkt: Market) {
    setMarket(mkt);
    setSymbol(WATCHLISTS[mkt][0]);
  }

  function pickSignal(s: EmittedSignal) {
    setMarket((s.market as Market) ?? "crypto");
    setInterval(s.interval);
    setSymbol(s.symbol);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <header className="sticky top-0 z-10 border-b border-slate-200/70 bg-white/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm">
              <Gauge size={18} />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight">Universal Signal Cockpit</div>
              <div className="text-[11px] text-slate-500">AI decision-support · not financial advice</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-600">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" /> Live data
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-[11px] font-medium text-indigo-600">
              <Sparkles size={12} /> Multi-agent AI
            </span>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${dbOn ? "border-emerald-100 bg-emerald-50 text-emerald-600" : "border-slate-200 bg-slate-50 text-slate-400"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${dbOn ? "bg-emerald-500" : "bg-slate-300"}`} />
              {dbOn ? "Learning live" : "DB off"}
            </span>
          </div>
        </div>
      </header>

      <main className="rise mx-auto max-w-5xl px-6 py-8">
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
          <button onClick={() => load(symbol, interval, market)} className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <div className="mb-6 flex flex-wrap items-center gap-2">
          {WATCHLISTS[market].map((sym) => (
            <button key={sym} className="chip" data-active={symbol === sym} onClick={() => setSymbol(sym)}>{sym}</button>
          ))}
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="ml-auto w-40 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-400"
            placeholder="Symbol"
          />
        </div>

        {loading && (
          <Card className="card-pad flex items-center gap-2 text-sm text-slate-500">
            <Activity size={15} className="shimmer" /> Loading {symbol} {interval}…
          </Card>
        )}

        {error && (
          <Card className="card-pad text-sm text-rose-700">
            {error}
            <div className="mt-1 text-xs text-rose-500">Is the backend running at {API_BASE}?</div>
          </Card>
        )}

        <div className="mb-6">
          <PerformancePanel refreshKey={historyKey} />
        </div>

        <div className="mb-6">
          <SummaryPanel refreshKey={historyKey} />
        </div>

        <div className="mb-6">
          <ScannerPanel onPick={pickSignal} onScanned={() => setHistoryKey((k) => k + 1)} />
        </div>

        {!loading && !error && signal && (
          <div className="space-y-6">
            <PriceChart symbol={symbol} interval={interval} market={market} onPrice={handlePrice} />
            <SignalCard s={signal} livePrice={livePrice} />

            <Card className="card-pad">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-1.5 text-sm font-semibold tracking-tight">
                    <Sparkles size={15} className="text-indigo-500" /> Deep AI Analysis
                  </div>
                  <div className="mt-0.5 text-xs text-slate-500">
                    Bull and Bear analysts argue the data; a Risk Manager rules on the final conviction.
                  </div>
                </div>
                <button
                  onClick={runDebate}
                  disabled={debating}
                  className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:opacity-90 disabled:opacity-60"
                >
                  <Sparkles size={15} />
                  {debating ? "Agents debating…" : decision ? "Re-run AI debate" : "Run AI debate"}
                </button>
              </div>

              {debating && (
                <div className="mt-4 space-y-1.5 text-xs text-slate-500">
                  <div className="shimmer">Bull analyst building the long case…</div>
                  <div className="shimmer">Bear analyst rebutting…</div>
                  <div className="shimmer">Risk manager weighing the verdict…</div>
                </div>
              )}
              {debateError && <div className="mt-3 text-sm text-rose-600">{debateError}</div>}
            </Card>

            {decision && !debating && <DebatePanel d={decision} />}

            <HistoryPanel refreshKey={historyKey} />
          </div>
        )}
      </main>

      <footer className="mx-auto max-w-5xl px-6 pb-10 pt-2 text-center text-[11px] text-slate-400">
        Deterministic factor engine · LLM reasons over numbers, never invents them · backtest-gated learning
      </footer>
    </div>
  );
}
