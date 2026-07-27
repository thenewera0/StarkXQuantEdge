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
  PieChart
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

const navItems = [
  { icon: LayoutDashboard, label: "Overview", href: "#overview" },
  { icon: Zap, label: "Flash Bot", href: "#flash" },
  { icon: Radio, label: "Live Trades", href: "#live" },
  { icon: Landmark, label: "Investments", href: "#invest" },
  { icon: PieChart, label: "Fund", href: "#fund" },
  { icon: Activity, label: "Analytics", href: "#analytics" },
  { icon: ListOrdered, label: "History", href: "#history" },
  { icon: ArrowRightLeft, label: "Arbitrage", href: "#arb" },
];

export function Sidebar() {
  // Views are hash-routed, so track the hash (pathname never changes on a single page).
  const [hash, setHash] = useState("#overview");
  useEffect(() => {
    const read = () => setHash(window.location.hash || "#overview");
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-[var(--line)] bg-[var(--bg-sidebar)]">
      <div className="flex h-20 items-center px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--accent-bright)] text-white ">
            <Hexagon size={22} fill="currentColor" />
          </div>
          <span className="text-xl font-bold tracking-tight text-white">StarkX Edge</span>
        </div>
      </div>
      
      <div className="mt-4 px-4 overflow-y-auto h-[calc(100vh-100px)]">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = hash === item.href;
            const Icon = item.icon;
            
            return (
              <li key={item.label}>
                <Link 
                  href={item.href}
                  className={`group flex items-center gap-4 rounded-xl px-4 py-3 text-sm font-medium transition-all ${
                    isActive 
                      ? "bg-gradient-to-r from-[var(--accent-dim)] to-transparent text-white border-l-2 border-[var(--accent-bright)]" 
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                  }`}
                >
                  <Icon size={18} className={isActive ? "text-[var(--accent-bright)]" : "text-[var(--ink-muted)] group-hover:text-slate-300"} />
                  {item.label}
                  {item.label === "Dashboard" && isActive && (
                    <div className="ml-auto flex h-4 w-4 items-center justify-center rounded-full bg-[rgba(0,212,255,0.1)]">
                      <div className="h-1.5 w-1.5 rounded-full bg-[#00d4ff] animate-pulse" />
                    </div>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}

export function Header() {
  return (
    <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-[var(--line)] bg-[#090b14]/60 px-8 backdrop-blur-md">
      <div className="relative w-96">
        <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input 
          type="text" 
          placeholder="Search anything..." 
          className="w-full rounded-xl border border-white/10 bg-white/5 py-2.5 pl-10 pr-12 text-sm text-white placeholder:text-[var(--ink-muted)] outline-none focus:border-[rgba(0,102,255,0.5)] focus:bg-white/10 transition-all"
        />
        <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-1 rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
          <span className="text-[12px]">⌘</span>K
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <button className="relative flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
          <Bell size={18} />
          <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[var(--accent-bright)]" />
        </button>
        <button className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
          <Mail size={18} />
        </button>
        
        <div className="ml-2 h-6 w-[1px] bg-white/10" />
        
        <button className="flex items-center gap-3 pl-2 text-left">
          <img src="https://ui-avatars.com/api/?name=Admin&background=0066ff&color=fff" alt="User" className="h-9 w-9 rounded-full border border-white/10" />
          <div className="hidden sm:block">
            <div className="text-sm font-semibold text-white">StarkX Admin</div>
            <div className="text-xs text-slate-400">Quant Ops</div>
          </div>
          <ChevronDown size={14} className="text-slate-400" />
        </button>
      </div>
    </header>
  );
}
