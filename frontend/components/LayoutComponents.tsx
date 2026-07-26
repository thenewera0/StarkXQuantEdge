"use client";

import { 
  LayoutDashboard, 
  Briefcase, 
  LineChart, 
  PieChart, 
  Activity, 
  ArrowRightLeft, 
  FileText, 
  ListOrdered, 
  Bell, 
  Calendar, 
  Folder, 
  Settings,
  Search,
  Mail,
  ChevronDown,
  Hexagon
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/" },
  { icon: Briefcase, label: "Portfolio", href: "/portfolio" },
  { icon: LineChart, label: "Investments", href: "/investments" },
  { icon: PieChart, label: "Funds", href: "/funds" },
  { icon: Activity, label: "Analytics", href: "/analytics" },
  { icon: ArrowRightLeft, label: "Transactions", href: "/transactions" },
  { icon: FileText, label: "Reports", href: "/reports" },
  { icon: ListOrdered, label: "Watchlist", href: "/watchlist" },
  { icon: Bell, label: "Alerts", href: "/alerts" },
  { icon: Calendar, label: "Calendar", href: "/calendar" },
  { icon: Folder, label: "Documents", href: "/documents" },
  { icon: Settings, label: "Settings", href: "/settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  
  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-white/5 bg-[#05070c]/80 backdrop-blur-xl">
      <div className="flex h-20 items-center px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#0066ff] to-[#00d4ff] text-white shadow-[0_0_20px_rgba(0,102,255,0.4)]">
            <Hexagon size={22} fill="currentColor" />
          </div>
          <span className="text-xl font-bold tracking-tight text-white">StarkX Edge</span>
        </div>
      </div>
      
      <div className="mt-4 px-4 overflow-y-auto h-[calc(100vh-280px)]">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
            const Icon = item.icon;
            
            return (
              <li key={item.label}>
                <Link 
                  href={item.href}
                  className={`group flex items-center gap-4 rounded-xl px-4 py-3 text-sm font-medium transition-all ${
                    isActive 
                      ? "bg-gradient-to-r from-[rgba(0,102,255,0.15)] to-transparent text-white border-l-2 border-[#00d4ff]" 
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                  }`}
                >
                  <Icon size={18} className={isActive ? "text-[#00d4ff]" : "text-slate-500 group-hover:text-slate-300"} />
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
      
      <div className="absolute bottom-6 left-4 right-4">
        <div className="rounded-xl border border-[rgba(0,102,255,0.3)] bg-[rgba(0,102,255,0.1)] p-4 relative overflow-hidden">
          <div className="absolute -right-4 -top-4 h-16 w-16 rounded-full bg-[#00d4ff] opacity-20 blur-xl" />
          <div className="relative z-10">
            <h4 className="flex items-center gap-1.5 text-sm font-bold text-white">
              <Hexagon size={14} className="text-[#00d4ff]" fill="currentColor" />
              StarkX Pro
            </h4>
            <p className="mt-1.5 text-[11px] text-slate-300 leading-relaxed">
              Unlock advanced analytics and exclusive investment opportunities.
            </p>
            <button className="mt-3 w-full rounded-lg bg-gradient-to-r from-[#0066ff] to-[#00d4ff] px-4 py-2 text-xs font-semibold text-white shadow-[0_0_15px_rgba(0,102,255,0.3)] transition-opacity hover:opacity-90">
              Upgrade Now
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function Header() {
  return (
    <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-white/5 bg-[#090b14]/60 px-8 backdrop-blur-md">
      <div className="relative w-96">
        <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input 
          type="text" 
          placeholder="Search anything..." 
          className="w-full rounded-xl border border-white/10 bg-white/5 py-2.5 pl-10 pr-12 text-sm text-white placeholder:text-slate-500 outline-none focus:border-[rgba(0,102,255,0.5)] focus:bg-white/10 transition-all"
        />
        <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-1 rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
          <span className="text-[12px]">⌘</span>K
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <button className="relative flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
          <Bell size={18} />
          <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[#00d4ff] shadow-[0_0_5px_#00d4ff]" />
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
