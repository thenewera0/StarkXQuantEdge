"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchUniverse, type Instrument, type UniverseCounts } from "@/lib/api";
import { Card } from "./ui";
import { Globe, RefreshCw, Search, Info, Ban } from "lucide-react";

const CATS = ["all", "crypto", "forex", "commodities", "indices", "rates"] as const;

const CAT_LABEL: Record<string, string> = {
  crypto: "Crypto",
  forex: "Forex",
  commodities: "Commodities",
  indices: "Indices",
  rates: "Rates & Credit",
};

function volLabel(v?: number) {
  if (!v) return null;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${(v / 1e3).toFixed(0)}K`;
}

export function UniversePanel() {
  const [items, setItems] = useState<Instrument[]>([]);
  const [counts, setCounts] = useState<UniverseCounts | null>(null);
  const [cat, setCat] = useState<string>("all");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetchUniverse();
      setItems(r.instruments);
      setCounts(r.counts);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load universe");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return items.filter(
      (i) =>
        (cat === "all" || i.category === cat) &&
        (!needle ||
          i.symbol.toLowerCase().includes(needle) ||
          i.name.toLowerCase().includes(needle))
    );
  }, [items, cat, q]);

  const blocked = shown.filter((i) => !i.allocatable).length;

  return (
    <Card className="card-pad">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--accent-bright)] to-[var(--accent)]">
            <Globe size={16} className="text-white" />
          </span>
          <div>
            <h3 className="text-[13.5px] font-semibold text-[var(--ink)]">Tradable Universe</h3>
            <p className="text-[11px] text-[var(--ink-muted)]">
              {counts ? `${counts.total} instruments · ${counts.allocatable} allocatable` : "—"} · all free, keyless data
            </p>
          </div>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1 text-xs text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-[var(--loss)]">{error}</div>}

      {/* Per-class totals */}
      {counts && (
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
          {Object.entries(counts.by_category).map(([k, v]) => (
            <button
              key={k}
              onClick={() => setCat(cat === k ? "all" : k)}
              className={`rounded-xl border px-3 py-2.5 text-left transition-colors ${
                cat === k
                  ? "border-[var(--accent)]/40 bg-[var(--accent-dim)]"
                  : "surface-raised hover:bg-[var(--surface-hover)]"
              }`}
            >
              <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
                {CAT_LABEL[k] ?? k}
              </div>
              <div className="mt-0.5 text-xl font-bold tabular-nums text-[var(--ink)]">{v.total}</div>
              {v.allocatable < v.total && (
                <div className="text-[10px] tabular-nums text-[var(--warn)]">{v.allocatable} allocatable</div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[180px] flex-1">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-muted)]" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search gold, EUR/USD, BTC…"
            className="w-full rounded-lg border border-[var(--line)] bg-[var(--surface-raised)] py-1.5 pl-8 pr-3 text-[12px] text-[var(--ink)] placeholder:text-[var(--ink-muted)] focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {CATS.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`rounded-lg px-2.5 py-1.5 text-[11px] font-medium capitalize transition-colors ${
                cat === c
                  ? "bg-[var(--accent)] text-white"
                  : "surface-raised text-[var(--ink-secondary)] hover:text-[var(--ink)]"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {blocked > 0 && (
        <div className="mb-3 flex items-start gap-2 rounded-xl border border-[var(--warn)]/25 bg-[var(--warn-dim)] p-2.5">
          <Info size={14} className="mt-0.5 shrink-0 text-[var(--warn)]" />
          <p className="text-[11px] leading-relaxed text-[var(--ink-secondary)]">
            {blocked} of these are <b>visible but not allocatable</b>. A yield index is not something you can
            own, and outside the G10 an FX trend is usually just the interest differential in disguise. They
            stay on screen for regime and correlation work, and are barred from the allocation model.
          </p>
        </div>
      )}

      <div className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
        {shown.length} shown
      </div>
      <div className="max-h-[520px] space-y-1 overflow-y-auto pr-1">
        {shown.map((i) => (
          <div
            key={`${i.category}-${i.symbol}`}
            className={`flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-3 py-2 ${
              i.allocatable ? "surface-raised" : "border border-[var(--line)] opacity-70"
            }`}
          >
            <span className="min-w-[92px] font-semibold text-[var(--ink)]">{i.symbol}</span>
            <span className="min-w-[130px] flex-1 truncate text-[11.5px] text-[var(--ink-secondary)]">
              {i.name}
            </span>
            <span className="rounded bg-[var(--surface-hover)] px-1.5 py-0.5 text-[10px] capitalize text-[var(--ink-muted)]">
              {i.group}
            </span>
            {i.change_pct != null && (
              <span
                className={`w-[62px] text-right text-[11px] tabular-nums ${
                  i.change_pct >= 0 ? "text-[var(--profit)]" : "text-[var(--loss)]"
                }`}
              >
                {i.change_pct >= 0 ? "+" : ""}
                {i.change_pct.toFixed(2)}%
              </span>
            )}
            {volLabel(i.quote_volume) && (
              <span className="w-[54px] text-right text-[10.5px] tabular-nums text-[var(--ink-muted)]">
                {volLabel(i.quote_volume)}
              </span>
            )}
            {!i.allocatable && (
              <span
                title={i.note}
                className="ml-auto flex items-center gap-1 text-[10.5px] text-[var(--warn)]"
              >
                <Ban size={11} /> context only
              </span>
            )}
          </div>
        ))}
        {!shown.length && !loading && (
          <p className="py-6 text-center text-[12px] text-[var(--ink-muted)]">Nothing matches that filter.</p>
        )}
      </div>
    </Card>
  );
}
