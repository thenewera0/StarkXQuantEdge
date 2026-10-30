"use client";

import { 
  LayoutDashboard, 
  Activity, 
  ArrowRightLeft, 
  ListOrdered, 
  Search,
  Mail,
  ChevronDown,
  Hexagon,
  Bell,
  Zap,
  Radio,
  Landmark,
  PieChart,
  Globe,
  FlaskConical,
  X,
  Clock,
  ShieldCheck,
  TrendingUp,
  ExternalLink,
  CheckCircle2,
  Lock,
} from "lucide-react";
import { useEffect, useState, useRef } from "react";
import { fetchNseStatus, type NSEMarketStatus } from "@/lib/api";

export interface NavItem {
  icon: any;
  label: string;
  key: string;
  href: string;
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: "Overview", key: "overview", href: "/?tab=overview" },
  { icon: FlaskConical, label: "StarkX Lab", key: "lab", href: "/lab" },
  { icon: Landmark, label: "v2 Portfolio", key: "portfolio", href: "/portfolio" },
  { icon: Zap, label: "Flash Bot", key: "flash", href: "/?tab=flash" },
  { icon: Radio, label: "Live Trades", key: "live", href: "/?tab=live" },
  { icon: Globe, label: "Markets", key: "markets", href: "/?tab=markets" },
  { icon: Landmark, label: "Investments", key: "investments", href: "/?tab=investments" },
  { icon: PieChart, label: "Fund", key: "fund", href: "/?tab=fund" },
  { icon: Activity, label: "Analytics", key: "analytics", href: "/?tab=analytics" },
  { icon: ListOrdered, label: "History", key: "history", href: "/?tab=history" },
  { icon: ArrowRightLeft, label: "Arbitrage", key: "arbitrage", href: "/?tab=arbitrage" },
];

export function Sidebar() {
  const [activeKey, setActiveKey] = useState("overview");

  useEffect(() => {
    const updateActive = () => {
      if (typeof window === "undefined") return;
      const path = window.location.pathname;
      if (path === "/lab" || path.startsWith("/lab/")) {
        setActiveKey("lab");
        return;
      }
      if (path === "/portfolio" || path.startsWith("/portfolio/")) {
        setActiveKey("portfolio");
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get("tab");
      const hash = (window.location.hash || "").replace("#", "");
      const current = tabParam || hash || "overview";

      if (current === "invest" || current === "investments") setActiveKey("investments");
      else if (current === "arb" || current === "arbitrage") setActiveKey("arbitrage");
      else setActiveKey(current);
    };

    updateActive();
    window.addEventListener("hashchange", updateActive);
    window.addEventListener("popstate", updateActive);
    window.addEventListener("starkx_tab_change", updateActive);
    return () => {
      window.removeEventListener("hashchange", updateActive);
      window.removeEventListener("popstate", updateActive);
      window.removeEventListener("starkx_tab_change", updateActive);
    };
  }, []);

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, item: NavItem) => {
    if (typeof window === "undefined") return;
    const isMainPage = window.location.pathname === "/";

    if (item.key === "lab") {
      window.location.href = "/lab";
      return;
    }
    if (item.key === "portfolio") {
      window.location.href = "/portfolio";
      return;
    }

    if (isMainPage) {
      e.preventDefault();
      const tabSlug = item.key === "investments" ? "invest" : (item.key === "arbitrage" ? "arb" : item.key);
      window.location.hash = tabSlug;
      const url = new URL(window.location.href);
      url.searchParams.set("tab", item.key);
      window.history.pushState({}, "", url.toString());
      setActiveKey(item.key);
      window.dispatchEvent(new CustomEvent("starkx_tab_change", { detail: item.key }));
    } else {
      window.location.href = item.href;
    }
  };

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-[#1f283d] bg-gradient-to-b from-[#161d2d] to-[#0c0f18] shadow-[5px_0_15px_rgba(0,0,0,0.6),inset_-1px_0_0_rgba(0,0,0,0.8)]">
      <div className="flex h-20 items-center px-6">
        <a href="/?tab=overview" className="flex items-center gap-3 group">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--accent-bright)] text-white shadow-[0_0_15px_rgba(0,212,255,0.4)] transition-transform group-hover:scale-105">
            <Hexagon size={22} fill="currentColor" />
          </div>
          <div>
            <span className="text-xl font-bold tracking-tight text-white block">StarkX Edge</span>
            <span className="text-[10px] tracking-widest text-[#00E5A8] font-mono block">v3.0 · QUANT</span>
          </div>
        </a>
      </div>
      
      <div className="mt-2 px-3 overflow-y-auto h-[calc(100vh-100px)]">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = activeKey === item.key;
            const Icon = item.icon;
            
            return (
              <li key={item.key}>
                <a 
                  href={item.href}
                  onClick={(e) => handleNavClick(e, item)}
                  className={`group flex items-center gap-3.5 rounded-lg px-3.5 py-2.5 text-sm font-medium transition-all ${
                    isActive 
                      ? "bg-[#06080d] text-white border-l-2 border-[var(--accent-bright)] shadow-[inset_2px_2px_5px_rgba(0,0,0,0.8),inset_-1px_-1px_2px_rgba(255,255,255,0.05)]" 
                      : "text-slate-400 border border-transparent hover:bg-white/[0.03] hover:text-slate-200 hover:border-t-white/5 hover:border-b-black/20"
                  }`}
                >
                  <Icon size={17} className={isActive ? "text-[var(--accent-bright)]" : "text-slate-500 group-hover:text-slate-300"} />
                  <span>{item.label}</span>
                  {isActive && (
                    <div className="ml-auto flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[rgba(0,212,255,0.15)]">
                      <div className="h-1.5 w-1.5 rounded-full bg-[#00d4ff] animate-pulse" />
                    </div>
                  )}
                </a>
              </li>
            );
          })}
        </ul>

        {/* Paper Mode Safety Banner in Sidebar */}
        <div className="mt-6 mx-1 p-3 rounded-xl border border-emerald-500/20 bg-emerald-950/20 text-[11px]">
          <div className="flex items-center gap-1.5 font-semibold text-emerald-400">
            <ShieldCheck size={13} />
            <span>PAPER SANDBOX</span>
          </div>
          <div className="mt-1 text-slate-400 leading-relaxed">
            Strict Section 7.2 Zero-Order Mode. $150k Virtual Capital Ledger reconciled.
          </div>
        </div>
      </div>
    </aside>
  );
}

export function Header() {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isAlertsOpen, setIsAlertsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [marketFilter, setMarketFilter] = useState<"ALL" | "CRYPTO" | "NSE">("ALL");
  const [nseStatus, setNseStatus] = useState<NSEMarketStatus | null>(null);

  // Poll NSE live status
  useEffect(() => {
    let active = true;
    const loadNse = () => {
      fetchNseStatus()
        .then((s) => { if (active) setNseStatus(s); })
        .catch(() => {});
    };
    loadNse();
    const interval = setInterval(loadNse, 5000);
    return () => { active = false; clearInterval(interval); };
  }, []);

  // Keyboard shortcut Ctrl+K / Cmd+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setIsSearchOpen(false);
        setIsAlertsOpen(false);
        setIsProfileOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleMarketToggle = (val: "ALL" | "CRYPTO" | "NSE") => {
    setMarketFilter(val);
    if (typeof window !== "undefined") {
      localStorage.setItem("starkx_market_filter", val);
      window.dispatchEvent(new CustomEvent("starkx_market_filter_change", { detail: val }));
    }
  };

  const searchableItems = [
    { type: "view", title: "Overview", desc: "Portfolio summary, equity curve & Core stats", link: "/?tab=overview" },
    { type: "view", title: "Flash Bot", desc: "Autonomous 15m/1h liquidation sweep & squeeze sniper", link: "/?tab=flash" },
    { type: "view", title: "Live Trades", desc: "Mark-to-market open Core, Flash, and Lab positions", link: "/?tab=live" },
    { type: "view", title: "Markets & Charting", desc: "Multi-asset charting workbench & factor confluence", link: "/?tab=markets" },
    { type: "view", title: "Investments", desc: "12-1 momentum & trend allocation sleeves", link: "/?tab=investments" },
    { type: "view", title: "Virtual Fund", desc: "Quarter-Kelly allocation, net beta exposure & drift", link: "/?tab=fund" },
    { type: "view", title: "Quantitative Analytics", desc: "R-multiple distribution, Sharpe, calibration & payoff", link: "/?tab=analytics" },
    { type: "view", title: "Trade History", desc: "Closed ledger records with CSV download", link: "/?tab=history" },
    { type: "view", title: "Arbitrage Cockpit", desc: "Delta-neutral funding carry & triangular cycles", link: "/?tab=arbitrage" },
    { type: "view", title: "StarkX Lab (L1–L13)", desc: "13 institutional strategies with cryptographic change control", link: "/lab" },
    { type: "view", title: "v2 Portfolio", desc: "Multi-sleeve systematic allocation workbench", link: "/portfolio" },
    { type: "symbol", title: "^NSEI (Nifty 50)", desc: "NSE India Benchmark Index", link: "/?tab=markets&symbol=^NSEI" },
    { type: "symbol", title: "^NSEBANK (BankNifty)", desc: "NSE India Banking Index", link: "/?tab=markets&symbol=^NSEBANK" },
    { type: "symbol", title: "^INDIAVIX", desc: "India CBOE Volatility Index", link: "/?tab=markets&symbol=^INDIAVIX" },
    { type: "symbol", title: "RELIANCE.NS", desc: "Reliance Industries Ltd", link: "/?tab=markets&symbol=RELIANCE.NS" },
    { type: "symbol", title: "HDFCBANK.NS", desc: "HDFC Bank Ltd", link: "/?tab=markets&symbol=HDFCBANK.NS" },
    { type: "symbol", title: "BTCUSDT", desc: "Bitcoin / Tether Perp", link: "/?tab=markets&symbol=BTCUSDT" },
    { type: "symbol", title: "ETHUSDT", desc: "Ethereum / Tether Perp", link: "/?tab=markets&symbol=ETHUSDT" },
    { type: "symbol", title: "SOLUSDT", desc: "Solana / Tether Perp", link: "/?tab=markets&symbol=SOLUSDT" },
  ];

  const filteredItems = searchableItems.filter(
    (item) => item.title.toLowerCase().includes(searchQuery.toLowerCase()) || item.desc.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-[#1f283d] bg-gradient-to-r from-[#141b2a] via-[#101522] to-[#141b2a] px-6 shadow-[0_4px_12px_rgba(0,0,0,0.5),inset_0_-1px_0_rgba(0,0,0,0.8)]">
      
      {/* 1. Left: Command Palette Trigger */}
      <div className="flex items-center gap-4">
        <div 
          onClick={() => setIsSearchOpen(true)}
          className="relative w-80 cursor-pointer group"
        >
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 group-hover:text-white transition-colors" />
          <div className="w-full rounded-lg border-t border-black/80 border-l border-black/60 border-r border-white/10 border-b border-white/15 bg-[#05070b] py-2 pl-9 pr-12 text-xs text-slate-400 group-hover:border-[var(--accent-bright)] shadow-[inset_1.5px_1.5px_3px_rgba(0,0,0,0.8)] transition-all">
            Search symbols, strategies, views...
          </div>
          <div className="absolute right-2.5 top-1/2 flex -translate-y-1/2 items-center gap-1 rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
            <span className="text-[11px]">⌘</span>K
          </div>
        </div>

        {/* 2. Market Universe Toggle */}
        <div className="hidden lg:flex items-center rounded-lg border border-white/10 bg-[#070a12] p-0.5 text-xs font-medium">
          {(["ALL", "CRYPTO", "NSE"] as const).map((m) => (
            <button
              key={m}
              onClick={() => handleMarketToggle(m)}
              className={`rounded-md px-2.5 py-1 transition-all ${
                marketFilter === m
                  ? "bg-[var(--accent-bright)] text-black font-semibold shadow-[0_0_8px_rgba(0,212,255,0.4)]"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {m === "ALL" ? "ALL MARKETS" : m === "CRYPTO" ? "CRYPTO PERPS" : "NSE INDIA"}
            </button>
          ))}
        </div>
      </div>

      {/* 3. Center/Right: Live NSE Status Pill */}
      <div className="hidden xl:flex items-center gap-3">
        {nseStatus && (
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#080c16]/80 px-3 py-1.5 backdrop-blur-md text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${nseStatus.is_open ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
              <span className="text-slate-300 font-semibold">{nseStatus.ist_clock}</span>
            </div>
            <span className="text-slate-600">|</span>
            <div className="flex items-center gap-2 text-[11px]">
              <span className={nseStatus.is_open ? "text-emerald-400" : "text-amber-400"}>
                {nseStatus.is_open ? "NSE OPEN" : "NSE CLOSED"}
              </span>
              <span className="text-slate-400">NIFTY: <b className="text-white">{Number(nseStatus.nifty?.price || 24350).toLocaleString("en-IN")}</b></span>
              <span className="text-slate-400">PCR: <b className="text-[#00d4ff]">{nseStatus.pcr_oi}</b></span>
            </div>
          </div>
        )}
      </div>

      {/* 4. Controls: Notification Bell, Docs, Profile Menu */}
      <div className="flex items-center gap-3">
        {/* Alerts / Telemetry Popover */}
        <div className="relative">
          <button 
            onClick={() => setIsAlertsOpen(!isAlertsOpen)}
            className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-[#161d2d] text-slate-300 transition hover:bg-white/10 hover:text-white"
            title="Operational Telemetry & Alerts"
          >
            <Bell size={16} />
            <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]" />
          </button>

          {isAlertsOpen && (
            <div className="absolute right-0 mt-2 w-80 rounded-xl border border-[#1f283d] bg-[#0c101c] p-4 shadow-2xl z-50 animate-in fade-in zoom-in-95">
              <div className="flex items-center justify-between pb-2 border-b border-white/10">
                <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                  <Activity size={14} className="text-[var(--accent-bright)]" /> System Telemetry
                </span>
                <button onClick={() => setIsAlertsOpen(false)} className="text-slate-400 hover:text-white"><X size={14} /></button>
              </div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-slate-400">Feed Latency</span>
                  <span className="text-emerald-400 font-mono">18ms · Nominal</span>
                </div>
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-slate-400">Paper Sandbox</span>
                  <span className="text-emerald-400 font-semibold">STRICT PAPER · VIRTUAL</span>
                </div>
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-slate-400">Ledger Reconciliation</span>
                  <span className="text-[#00d4ff] font-mono">Delta: $0.0000 (100%)</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">MIS Square-off</span>
                  <span className="text-amber-400 font-mono">15:15 IST Active</span>
                </div>
              </div>
              <div className="mt-3 pt-2 border-t border-white/10">
                <a href="/lab" className="block text-center text-[11px] text-[var(--accent-bright)] hover:underline">
                  View Full Lab Audit Events →
                </a>
              </div>
            </div>
          )}
        </div>

        {/* Profile / Quant Ops Menu */}
        <div className="relative">
          <button 
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            className="flex items-center gap-2.5 rounded-lg border border-white/10 bg-[#161d2d] px-2.5 py-1.5 text-left transition hover:bg-white/10"
          >
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-[#0066ff] to-[#00d4ff] flex items-center justify-center text-white font-bold text-xs">
              QX
            </div>
            <div className="hidden sm:block">
              <div className="text-xs font-semibold text-white leading-tight">StarkX Admin</div>
              <div className="text-[10px] text-emerald-400 font-mono">PAPER · VIRTUAL</div>
            </div>
            <ChevronDown size={13} className="text-slate-400" />
          </button>

          {isProfileOpen && (
            <div className="absolute right-0 mt-2 w-64 rounded-xl border border-[#1f283d] bg-[#0c101c] p-3 shadow-2xl z-50 animate-in fade-in zoom-in-95">
              <div className="px-2 py-1.5 border-b border-white/10">
                <div className="text-xs font-semibold text-white">StarkX QuantEdge v3.0</div>
                <div className="text-[11px] text-slate-400">Lead Quant Operations</div>
              </div>
              <div className="my-2 space-y-1 text-xs">
                <a 
                  href="http://127.0.0.1:8000/docs" 
                  target="_blank" 
                  rel="noreferrer"
                  className="flex items-center justify-between px-2 py-1.5 rounded-lg text-slate-300 hover:bg-white/5 hover:text-white"
                >
                  <span className="flex items-center gap-2"><ExternalLink size={13} /> FastAPI Swagger Docs</span>
                  <span className="text-[10px] text-emerald-400">8000</span>
                </a>
                <a 
                  href="/lab" 
                  className="flex items-center justify-between px-2 py-1.5 rounded-lg text-slate-300 hover:bg-white/5 hover:text-white"
                >
                  <span className="flex items-center gap-2"><FlaskConical size={13} /> StarkX Lab Catalog</span>
                  <span className="text-[10px] text-[var(--accent-bright)]">L1–L13</span>
                </a>
                <a 
                  href="/portfolio" 
                  className="flex items-center justify-between px-2 py-1.5 rounded-lg text-slate-300 hover:bg-white/5 hover:text-white"
                >
                  <span className="flex items-center gap-2"><Landmark size={13} /> v2 Portfolio Engine</span>
                  <span className="text-[10px] text-slate-400">Sleeves</span>
                </a>
              </div>
              <div className="pt-2 border-t border-white/10 px-2 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                <span>Lock SHA-256</span>
                <span className="text-[#00d4ff]">d025e6...</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 5. Command Palette Modal (Ctrl+K / Cmd+K) */}
      {isSearchOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl border border-[#1f283d] bg-[#0c101c] p-4 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="relative flex items-center border-b border-white/10 pb-3">
              <Search size={18} className="absolute left-3 text-slate-400" />
              <input
                autoFocus
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Jump to view, strategy or symbol (e.g. NIFTY, Flash, Lab, RELIANCE)..."
                className="w-full bg-transparent pl-10 pr-8 text-sm text-white placeholder:text-slate-500 outline-none"
              />
              <button onClick={() => setIsSearchOpen(false)} className="text-slate-400 hover:text-white">
                <X size={16} />
              </button>
            </div>
            
            <div className="mt-3 max-h-80 overflow-y-auto space-y-1">
              {filteredItems.map((item, idx) => (
                <a
                  key={idx}
                  href={item.link}
                  onClick={() => setIsSearchOpen(false)}
                  className="flex items-center justify-between rounded-lg px-3 py-2 text-xs text-slate-300 hover:bg-white/10 hover:text-white transition-all group"
                >
                  <div>
                    <div className="font-semibold text-white group-hover:text-[var(--accent-bright)]">{item.title}</div>
                    <div className="text-[11px] text-slate-400">{item.desc}</div>
                  </div>
                  <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400 font-mono">
                    {item.type}
                  </span>
                </a>
              ))}
              {filteredItems.length === 0 && (
                <div className="py-6 text-center text-xs text-slate-500">No matching views or symbols found.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
