export type Categories = {
  trend: number | null;
  momentum: number | null;
  volatility: number | null;
  structure: number | null;
  flow: number | null;
  sentiment: number | null;
  macro: number | null;
  consensus: number | null;
};

export type Levels = {
  direction: "long" | "short" | "flat";
  entry: number | null;
  stop: number | null;
  target: number | null;
  reward_risk: number;
};

export type Explanation = {
  rationale: string;
  source: "openrouter" | "fallback";
  model: string | null;
};

export type NewsMeta = {
  score: number | null;
  headlines: number;
  query: string | null;
};

export type MacroMeta = {
  score: number | null;
  btc_dominance: number | null;
  market_cap_change_24h: number | null;
};

export type Derivatives = {
  funding_rate?: number | null;
  basis?: number | null;
  oi_change?: number | null;
  long_short_ratio?: number | null;
} | null;

export type FearGreed = { value: number | null; classification: string | null; delta: number | null } | null;
export type Onchain = { score: number | null; available?: boolean; reason?: string } | null;

export type Signal = {
  symbol: string;
  market: string;
  interval: string;
  regime?: string | null;
  as_of: string;
  label: string;
  composite: number;
  confidence: number;
  tier?: string;
  agreement?: number;
  actionable?: boolean;
  silence_reason?: string | null;
  categories: Categories;
  price: number | null;
  atr: number | null;
  levels: Levels;
  targets?: (number | null)[] | null;
  reward_risk?: number | null;
  size_pct?: number | null;
  invalidation?: string | null;
  psychology?: string;
  psychology_modifier?: number;
  crowd_veto?: boolean;
  derivatives?: Derivatives;
  fear_greed?: FearGreed;
  news?: NewsMeta | null;
  macro?: MacroMeta | null;
  onchain?: Onchain;
  disclaimer: string;
  explanation?: Explanation;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

// Full signal WITH the LLM-written rationale (1 LLM call). Use on initial load / symbol change only.
export async function fetchSignal(symbol: string, interval: string, market: string): Promise<Signal> {
  const params = new URLSearchParams({ symbol, interval, market });
  const url = `${API_BASE}/explain?${params.toString()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Backend ${res.status}: ${detail || res.statusText}`);
  }
  return res.json();
}

// Deterministic signal WITHOUT the LLM (no rationale) — for cheap live auto-refresh polling.
export async function fetchSignalLite(symbol: string, interval: string, market: string): Promise<Signal> {
  const params = new URLSearchParams({ symbol, interval, market });
  const res = await fetch(`${API_BASE}/signal?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type Candle = { time: number; open: number; high: number; low: number; close: number };
export type LinePoint = { time: number; value: number };
export type Candles = {
  symbol: string;
  interval: string;
  candles: Candle[];
  ema50: LinePoint[];
  ema200: LinePoint[];
  ut_stop: LinePoint[];
};

export type Debate = {
  bull: string;
  bear: string;
  agreement: "agree" | "caution" | "disagree";
  conviction: number;
  key_risks: string[];
  verdict: string;
  source: "openrouter" | "fallback";
};

export type FinalDecision = {
  label: string;
  agreement: "agree" | "caution" | "disagree";
  conviction: number;
  final_confidence: number;
};

export type Decision = Signal & {
  debate: Debate;
  final: FinalDecision;
};

export async function fetchDecision(symbol: string, interval: string, market: string): Promise<Decision> {
  const params = new URLSearchParams({ symbol, interval, market });
  const url = `${API_BASE}/decision?${params.toString()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Backend ${res.status}: ${detail || res.statusText}`);
  }
  return res.json();
}

export type RecentSignal = {
  id: number;
  symbol: string;
  market: string | null;
  interval: string;
  as_of: string;
  label: string;
  composite: number;
  confidence: number;
  final_confidence: number | null;
  agreement: string | null;
  result: string | null;
  pnl: number | null;
};

export type Stats = {
  enabled: boolean;
  resolved?: number;
  wins?: number;
  hit_rate?: number | null;
  avg_pnl?: number | null;
};

export type EmittedSignal = {
  id: number | null;
  symbol: string;
  market: string;
  interval: string;
  label: string;
  confidence: number;
  regime: string | null;
  entry: number | null;
  stop: number | null;
  target: number | null;
};

export type ScanResult = {
  scanned: number;
  errors: number;
  emitted: number;
  min_confidence: number;
  signals: EmittedSignal[];
};

export async function runScan(): Promise<ScanResult> {
  const res = await fetch(`${API_BASE}/scan`, { method: "POST", cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export async function fetchRecent(limit = 15): Promise<RecentSignal[]> {
  const res = await fetch(`${API_BASE}/signals/recent?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return (await res.json()).signals;
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type PnlTrade = {
  symbol: string;
  interval: string;
  direction: string;
  result?: string;
  entry?: number;
  price?: number;
  pnl_pct: number;
  pnl_usd: number;
  bars_held?: number;
  resolved_at?: string;
};

export type SymbolPnl = { symbol: string; trades: number; wins: number; pnl_usd: number };
export type RegimePnl = { regime: string; trades: number; wins: number; pnl_usd: number; hit_rate: number | null };
export type EquityPoint = { i: number; cum_pnl_usd: number; time: string | null };

export type Performance = {
  enabled: boolean;
  trade_size_usd?: number;
  combined?: {
    realized_pnl_usd: number;
    open_pnl_usd: number;
    total_pnl_usd: number;
    closed_trades: number;
    open_trades: number;
    wins: number;
    losses: number;
    hit_rate: number | null;
    total_return_pct: number | null;
  };
  per_symbol?: SymbolPnl[];
  per_regime?: RegimePnl[];
  equity_curve?: EquityPoint[];
  trades?: PnlTrade[];
  open_positions?: PnlTrade[];
};

export async function fetchPerformance(tradeSize = 1000): Promise<Performance> {
  const res = await fetch(`${API_BASE}/performance?trade_size=${tradeSize}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type WindowStats = {
  trades: number;
  wins: number;
  losses: number;
  hit_rate: number | null;
  realized_pnl_usd: number;
  best_usd: number;
  worst_usd: number;
};

export type RegimePerf = { trades: number; pnl_usd: number; hit_rate: number | null; tradeable: boolean };

export type Summary = {
  enabled: boolean;
  trade_size_usd?: number;
  week?: WindowStats;
  month?: WindowStats;
  all_time?: WindowStats;
  learning?: {
    tradeable_regimes: string[];
    excluded_regimes: string[];
    regime_performance: Record<string, RegimePerf>;
    champion_weight_profiles: number;
  };
};

export async function fetchSummary(tradeSize = 1000): Promise<Summary> {
  const res = await fetch(`${API_BASE}/summary?trade_size=${tradeSize}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export async function fetchCandles(symbol: string, interval: string, market: string): Promise<Candles> {
  const params = new URLSearchParams({ symbol, interval, market, limit: "300" });
  const url = `${API_BASE}/candles?${params.toString()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Backend ${res.status}: ${detail || res.statusText}`);
  }
  return res.json();
}
