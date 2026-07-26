"use client";

import { useEffect, useState, useRef } from "react";
import { 
  fetchPerformance, 
  fetchSummary, 
  fetchRecent, 
  fetchStats,
  type Performance, 
  type Summary, 
  type RecentSignal,
  type Stats
} from "@/lib/api";
import { ArrowUpRight, ArrowDownRight, Sparkles, Box, TrendingUp, TrendingDown, Target, Activity, ArrowRightLeft } from "lucide-react";

// Inline simple card component since we are bypassing the local UI kit for now
function Card({ children, className = "" }: { children: React.ReactNode, className?: string }) {
  return (
    <div className={`card ${className}`}>
      {children}
    </div>
  );
}

export function MetricCards() {
  const [perf, setPerf] = useState<Performance | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  
  useEffect(() => {
    fetchPerformance(1000).then(setPerf).catch(() => {});
    fetchSummary(1000).then(setSummary).catch(() => {});
    fetchStats().then(setStats).catch(() => {});
  }, []);

  const totalRealizedPnl = perf?.combined?.realized_pnl_usd || 0;
  const totalPnl = perf?.combined?.total_pnl_usd || 0;
  const activeSignals = perf?.combined?.open_trades || 0;
  
  const hitRate = stats?.hit_rate ? (stats.hit_rate * 100).toFixed(1) : "0.0";
  const riskLabel = summary?.risk_state?.drifting ? "High Risk" : "Moderate";

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
      {/* Total Assets */}
      <Card className="relative overflow-hidden p-6 hover:-translate-y-1 transition-transform cursor-pointer group">
        <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-[#0066ff] opacity-10 blur-2xl group-hover:opacity-20 transition-opacity" />
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#0066ff]/20 to-[#00d4ff]/20 border border-[#00d4ff]/20 text-[#00d4ff]">
            <Box size={20} fill="currentColor" className="opacity-80" />
          </div>
          <span className="text-sm font-medium text-slate-400">Total Realized PnL</span>
        </div>
        <div className="text-3xl font-bold tracking-tight text-white mb-2">{new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(totalRealizedPnl)}</div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-emerald-400 font-medium bg-emerald-400/10 px-1.5 py-0.5 rounded">Realized</span>
          <span className="text-slate-500">all time</span>
        </div>
      </Card>

      {/* Total Returns */}
      <Card className="relative overflow-hidden p-6 hover:-translate-y-1 transition-transform cursor-pointer group">
        <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-[#0066ff] opacity-10 blur-2xl group-hover:opacity-20 transition-opacity" />
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#0066ff]/20 to-[#00d4ff]/20 border border-[#00d4ff]/20 text-[#00d4ff]">
            <TrendingUp size={20} className="opacity-80" />
          </div>
          <span className="text-sm font-medium text-slate-400">Total PnL (incl. Open)</span>
        </div>
        <div className="text-3xl font-bold tracking-tight text-white mb-2">{new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(totalPnl)}</div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-slate-500">Live performance</span>
        </div>
      </Card>

      {/* Active Investments */}
      <Card className="relative overflow-hidden p-6 hover:-translate-y-1 transition-transform cursor-pointer group">
        <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-[#0066ff] opacity-10 blur-2xl group-hover:opacity-20 transition-opacity" />
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#0066ff]/20 to-[#00d4ff]/20 border border-[#00d4ff]/20 text-[#00d4ff]">
            <Target size={20} className="opacity-80" />
          </div>
          <span className="text-sm font-medium text-slate-400">Active Signals</span>
        </div>
        <div className="text-3xl font-bold tracking-tight text-white mb-2">{activeSignals}</div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-slate-500">Open trades</span>
        </div>
      </Card>

      {/* Risk Score */}
      <Card className="relative overflow-hidden p-6 hover:-translate-y-1 transition-transform cursor-pointer group flex flex-col justify-between">
        <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-[#0066ff] opacity-10 blur-2xl group-hover:opacity-20 transition-opacity" />
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity size={14} className="text-amber-400" />
            <span className="text-sm font-medium text-slate-400">Risk Score</span>
          </div>
        </div>
        
        <div className="flex items-end justify-between">
          <div>
            <div className="text-2xl font-bold tracking-tight text-white mb-1">{riskLabel}</div>
            <div className="text-xs text-slate-500">System Win Rate: <span className="text-slate-300">{hitRate}%</span></div>
          </div>
          
          <div className="relative h-14 w-14 rounded-full border-4 border-white/5 flex items-center justify-center">
             <div className="absolute inset-0 rounded-full border-4 border-[#0066ff] border-t-transparent border-r-transparent rotate-45 opacity-80" />
             <div className="absolute inset-0 rounded-full border-4 border-[#00d4ff] border-b-transparent border-l-transparent -rotate-45 blur-[2px] opacity-60" />
          </div>
        </div>
      </Card>
    </div>
  );
}

export function PortfolioOverview() {
  const [perf, setPerf] = useState<Performance | null>(null);
  
  useEffect(() => {
    fetchPerformance(1000).then(setPerf).catch(() => {});
  }, []);

  const overviewTotal = perf?.combined?.total_pnl_usd || 0;

  return (
    <Card className="col-span-full relative overflow-hidden p-0 h-[420px] flex flex-col group">
      <div className="absolute inset-0 bg-gradient-to-b from-[#0066ff]/5 to-transparent pointer-events-none" />
      
      <div className="p-8 pb-0 relative z-10">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-xl font-medium text-white mb-6">Portfolio Overview</h3>
            <div className="text-sm text-slate-400 mb-1">Total PnL</div>
            <div className="text-4xl font-bold tracking-tight text-white mb-2 text-glow">
              {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(overviewTotal)}
            </div>
            <div className="flex items-center gap-1.5 text-sm">
              <span className="text-slate-500">All-time trading history</span>
            </div>
          </div>
          <button className="flex items-center gap-2 rounded-xl border border-[rgba(0,102,255,0.3)] bg-[rgba(0,102,255,0.1)] px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-[rgba(0,102,255,0.2)]">
            Portfolio Analysis <ArrowUpRight size={16} />
          </button>
        </div>
      </div>
      
      {/* Massive glowing SVG Area Chart */}
      <div className="flex-1 w-full relative mt-4">
         <div className="absolute inset-0 flex items-end">
           <svg width="100%" height="100%" viewBox="0 0 1000 200" preserveAspectRatio="none">
              <defs>
                <linearGradient id="glow" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#0066ff" stopOpacity="0.01" />
                </linearGradient>
                <filter id="neon" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="8" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <path 
                d="M 0 200 L 0 150 Q 50 120 100 130 T 200 110 T 300 140 T 400 80 T 500 120 T 600 60 T 700 90 T 800 30 T 900 60 T 1000 10 L 1000 200 Z" 
                fill="url(#glow)"
              />
              <path 
                d="M 0 150 Q 50 120 100 130 T 200 110 T 300 140 T 400 80 T 500 120 T 600 60 T 700 90 T 800 30 T 900 60 T 1000 10" 
                fill="none" 
                stroke="#00d4ff" 
                strokeWidth="3"
                filter="url(#neon)"
              />
              
              {/* Nodes */}
              <circle cx="800" cy="30" r="4" fill="#fff" stroke="#00d4ff" strokeWidth="2" filter="url(#neon)" />
              <circle cx="1000" cy="10" r="4" fill="#fff" stroke="#00d4ff" strokeWidth="2" filter="url(#neon)" />
           </svg>
         </div>
         
         {/* Custom Floating Label */}
         <div className="absolute right-12 top-6 rounded-lg border border-[rgba(0,212,255,0.3)] bg-[#090b14]/80 px-3 py-1.5 text-sm font-semibold text-[#00d4ff] backdrop-blur-md shadow-[0_0_10px_rgba(0,212,255,0.2)]">
            {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(overviewTotal)}
         </div>
      </div>
    </Card>
  );
}

export function AssetAllocation() {
  const [perf, setPerf] = useState<Performance | null>(null);
  useEffect(() => { fetchPerformance(1000).then(setPerf).catch(() => {}); }, []);

  const totalTrades = perf?.combined?.closed_trades || 1;
  const cryptoTrades = perf?.per_symbol?.filter(s => !s.symbol.includes("/")).reduce((sum, s) => sum + s.trades, 0) || 0;
  const forexTrades = perf?.per_symbol?.filter(s => s.symbol.includes("/")).reduce((sum, s) => sum + s.trades, 0) || 0;
  
  const cryptoPct = Math.round((cryptoTrades / totalTrades) * 100) || 0;
  const forexPct = Math.round((forexTrades / totalTrades) * 100) || 0;
  const otherPct = 100 - cryptoPct - forexPct;

  return (
    <Card className="p-6 h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-sm font-semibold text-white">Asset Allocation</h3>
      </div>
      
      <div className="flex-1 flex items-center justify-between">
        {/* CSS Donut Chart */}
        <div className="relative h-40 w-40 flex-shrink-0">
          <div 
            className="absolute inset-0 rounded-full"
            style={{
              background: `conic-gradient(
                #0066ff 0% ${cryptoPct}%, 
                #00d4ff ${cryptoPct}% ${cryptoPct + forexPct}%, 
                #1e293b ${cryptoPct + forexPct}% 100%
              )`
            }}
          />
          <div className="absolute inset-4 rounded-full bg-[rgba(16,20,35,1)] flex flex-col items-center justify-center backdrop-blur-3xl shadow-[inset_0_0_10px_rgba(0,0,0,0.5)]">
            <span className="text-xl font-bold text-white">{cryptoTrades + forexTrades}</span>
            <span className="text-[10px] text-slate-400">Total Trades</span>
          </div>
        </div>
        
        <div className="ml-6 flex-1 space-y-4">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-slate-300"><div className="w-2 h-2 rounded-full bg-[#0066ff]"/> Crypto</div>
            <div className="font-semibold text-white">{cryptoPct}%</div>
          </div>
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-slate-300"><div className="w-2 h-2 rounded-full bg-[#00d4ff]"/> Forex</div>
            <div className="font-semibold text-white">{forexPct}%</div>
          </div>
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-slate-300"><div className="w-2 h-2 rounded-full bg-slate-700"/> Other</div>
            <div className="font-semibold text-white">{otherPct}%</div>
          </div>
        </div>
      </div>
      
      <button className="mt-4 text-xs text-[#00d4ff] hover:text-white transition-colors text-left font-medium">View Details &rarr;</button>
    </Card>
  );
}

export function TopPerformers() {
  const [perf, setPerf] = useState<Performance | null>(null);
  useEffect(() => { fetchPerformance(1000).then(setPerf).catch(() => {}); }, []);

  const symbols = perf?.per_symbol?.sort((a, b) => b.pnl_usd - a.pnl_usd).slice(0, 4) || [];

  return (
    <Card className="p-6 h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-sm font-semibold text-white">Top Performing Assets</h3>
        <button className="text-xs text-[#00d4ff] hover:text-white">View All</button>
      </div>
      
      <div className="flex-1 space-y-4">
        {symbols.length > 0 ? symbols.map((sym, i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10 text-xs font-bold text-[#00d4ff]">
                {sym.symbol.slice(0, 3)}
              </div>
              <div>
                <div className="text-sm font-medium text-white">{sym.symbol}</div>
                <div className="text-xs text-slate-500">{sym.wins} wins / {sym.trades} trades</div>
              </div>
            </div>
            <div className="text-sm font-semibold text-emerald-400">
              +{((sym.wins / (sym.trades || 1)) * 100).toFixed(1)}%
            </div>
          </div>
        )) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-500">No data available</div>
        )}
      </div>
    </Card>
  );
}

export function RecentTransactions() {
  const [recent, setRecent] = useState<RecentSignal[]>([]);
  useEffect(() => { fetchRecent(4).then(setRecent).catch(() => {}); }, []);

  return (
    <Card className="p-6 h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-sm font-semibold text-white">Recent Signals</h3>
        <button className="text-xs text-[#00d4ff] hover:text-white">View All</button>
      </div>
      
      <div className="flex-1 space-y-4">
        {recent.map((s, i) => {
          const isBuy = s.label.includes("Buy");
          const isFlat = !isBuy && !s.label.includes("Sell");
          
          return (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`flex h-8 w-8 items-center justify-center rounded-full border ${
                  isBuy ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" : 
                  isFlat ? "bg-slate-500/10 border-slate-500/20 text-slate-400" : 
                  "bg-rose-500/10 border-rose-500/20 text-rose-400"
                }`}>
                  {isBuy ? <ArrowDownRight size={14} /> : <ArrowUpRight size={14} />}
                </div>
                <div>
                  <div className="text-sm font-medium text-white">{s.symbol}</div>
                  <div className="text-xs text-slate-500">{s.label} ({s.interval})</div>
                </div>
              </div>
              <div className="text-right">
                <div className={`text-sm font-semibold ${s.pnl && s.pnl > 0 ? "text-emerald-400" : s.pnl && s.pnl < 0 ? "text-rose-400" : "text-white"}`}>
                  {s.pnl ? `${s.pnl > 0 ? "+" : ""}${(s.pnl * 100).toFixed(2)}%` : s.result ? s.result : "Open"}
                </div>
                <div className="text-[10px] text-slate-500">{new Date(s.as_of).toLocaleDateString()}</div>
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  );
}

export function AIInsightsWidget() {
  return (
    <Card className="relative overflow-hidden p-6 h-full flex flex-col group border-[rgba(0,102,255,0.3)]">
      {/* Orb background */}
      <div className="absolute right-0 bottom-0 h-64 w-64 translate-x-1/4 translate-y-1/4 rounded-full bg-gradient-to-br from-[#0066ff] to-[#00d4ff] opacity-20 blur-3xl group-hover:opacity-30 transition-opacity mix-blend-screen" />
      <div className="absolute right-0 bottom-0 h-32 w-32 translate-x-1/8 translate-y-1/8 rounded-full bg-[#00d4ff] opacity-20 blur-2xl group-hover:opacity-40 transition-opacity mix-blend-screen" />
      
      <div className="relative z-10 flex-1">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <Sparkles size={18} className="text-[#00d4ff]" /> AI Insights
        </h3>
        
        <p className="text-sm font-medium text-white mb-2">Market conditions are volatile! 🚀</p>
        <p className="text-xs text-slate-300 leading-relaxed max-w-[85%]">
          Multi-agent debate indicates high conviction in trend-following setups on Crypto majors. 
          Consider raising allocations in BTC and SOL based on positive expected value projections.
        </p>
      </div>
      
      <button className="relative z-10 mt-6 flex items-center gap-2 w-max rounded-lg border border-[rgba(0,212,255,0.3)] bg-[rgba(0,212,255,0.1)] px-4 py-2 text-xs font-semibold text-[#00d4ff] transition-all hover:bg-[rgba(0,212,255,0.2)] hover:text-white">
        View Full Debate <ArrowRightLeft size={14} />
      </button>
    </Card>
  );
}
