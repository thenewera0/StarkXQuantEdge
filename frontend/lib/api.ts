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
  strategy_family?: string;
  agreement?: number;
  win_prob?: number | null;
  meta_p?: number | null;
  htf_trend?: number | null;
  ev_r?: number | null;
  position_sizing?: {
    tier: string;
    risk_pct: number;
    risk_usd: number;
    notional_usd: number;
    kelly_f: number;
    ruin_f: number;
    bound_by: string;
    tradeable: boolean;
  } | null;
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
  price_action?: PriceActionData;
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

export type SRZone = {
  price: number;
  kind: "support" | "resistance";
  touches: number;
  strength: number;
  distance_pct: number;
  room_to_run_atr: number;
};

export type CandlePattern = {
  pattern: string;
  name: string;
  time?: number;
  direction: "bullish" | "bearish" | "neutral";
  bar_offset: number;
  strength: number;
  price: number;
  desc: string;
};

export type LiquiditySweep = {
  type: string;
  direction: "bullish" | "bearish";
  level_swept: number;
  sweep_high?: number;
  sweep_low?: number;
  close: number;
  desc: string;
  strength: number;
};

export type MarketStructure = {
  trend: string;
  score: number;
  swing_highs_count?: number;
  swing_lows_count?: number;
};

export type PriceActionChartMarker = {
  time: number;
  position: "aboveBar" | "belowBar";
  color: string;
  shape: "arrowUp" | "arrowDown" | "circle" | "square";
  text: string;
};

export type CandleAnatomy = {
  range: number;
  body: number;
  body_ratio: number;
  upper_wick: number;
  upper_wick_ratio: number;
  lower_wick: number;
  lower_wick_ratio: number;
  is_bullish: boolean;
  rejection: "bullish_rejection" | "bearish_rejection" | "none";
};

export type PriceActionData = {
  score: number;
  bias: "bullish" | "bearish" | "neutral";
  patterns: CandlePattern[];
  nearest_support: number | null;
  nearest_resistance: number | null;
  dist_support_pct: number | null;
  dist_resistance_pct: number | null;
  room_to_run_atr: number | null;
  room_to_run_short_atr: number | null;
  atr: number;
  support_zones: SRZone[];
  resistance_zones: SRZone[];
  liquidity_sweep: LiquiditySweep | null;
  market_structure: MarketStructure;
  last_candle: CandleAnatomy;
  chart_markers?: PriceActionChartMarker[];
};

export type Candles = {
  symbol: string;
  interval: string;
  candles: Candle[];
  ema50: LinePoint[];
  ema200: LinePoint[];
  ut_stop: LinePoint[];
  price_action?: PriceActionData;
};

export async function fetchPriceAction(
  symbol: string,
  interval: string,
  market = "crypto"
): Promise<PriceActionData> {
  const params = new URLSearchParams({ symbol, interval, market, limit: "300" });
  const url = `${API_BASE}/price-action?${params.toString()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Backend ${res.status}: ${detail || res.statusText}`);
  }
  return res.json();
}

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
  strategy?: string;
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

export async function fetchRecent(limit = 15, strategy = "all"): Promise<RecentSignal[]> {
  const res = await fetch(`${API_BASE}/signals/recent?limit=${limit}&strategy=${strategy}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return (await res.json()).signals;
}

export async function fetchStats(strategy = "core"): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats?strategy=${strategy}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type PnlTrade = {
  id?: number;
  symbol: string;
  interval: string;
  regime?: string;
  direction: string;
  result?: string;
  entry?: number;
  price?: number;
  strategy?: string;
  pnl_pct: number;
  pnl_usd: number;
  bars_held?: number;
  resolved_at?: string;
};

export type TradeDetail = {
  id: number;
  symbol: string;
  market: string;
  interval: string;
  as_of: string;
  created_at: string;
  label: string;
  regime: string | null;
  strategy?: string;
  tier: string | null;
  composite: number | null;
  confidence: number | null;
  agreement: number | null;
  conviction: number | null;
  final_confidence: number | null;
  price: number | null;
  atr: number | null;
  direction: string;
  entry: number | null;
  stop: number | null;
  targets: (number | null)[];
  reward_risk: number | null;
  size_pct: number | null;
  invalidation: string | null;
  psychology: string | null;
  rationale: string | null;
  factors: Record<string, number | null>;
  outcome: {
    result: string;
    pnl_frac: number | null;
    mfe: number | null;
    mae: number | null;
    bars_held: number | null;
    resolved_at: string | null;
  } | null;
};

export async function fetchTrade(id: number): Promise<TradeDetail> {
  const res = await fetch(`${API_BASE}/trade?id=${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type TradeCounts = {
  all: number;
  wins: number;
  losses: number;
  gross_profit_usd?: number;
  gross_loss_usd?: number;
  net_pnl_usd?: number;
  profit_factor?: number | null;
  avg_win_usd?: number;
  avg_loss_usd?: number;
  win_rate?: number;
};

export type TradeHistory = {
  trades: PnlTrade[];
  counts: TradeCounts;
  performance?: TradeCounts;
  limit: number;
  offset: number;
};

export async function fetchTrades(
  result: "all" | "wins" | "losses" = "all",
  limit = 50,
  offset = 0,
  strategy = "core"
): Promise<TradeHistory> {
  const params = new URLSearchParams({ result, limit: String(limit), offset: String(offset), strategy });
  const res = await fetch(`${API_BASE}/trades?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export async function fetchFlashTrades(
  limit = 50,
  offset = 0,
  result: "all" | "wins" | "losses" = "all"
): Promise<TradeHistory> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset), result });
  const res = await fetch(`${API_BASE}/flash/trades?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

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
  ledger_status?: LedgerStatus;
  per_symbol?: SymbolPnl[];
  per_regime?: RegimePnl[];
  equity_curve?: EquityPoint[];
  trades?: PnlTrade[];
  open_positions?: PnlTrade[];
};

export interface LedgerStatus {
  reconciled: boolean;
  deltaUsd: number;
  nSized: number;
  nShadowExcluded: number;
  asOf: string;
}

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

export type RiskState = {
  drifting: boolean;
  circuit_halted: boolean;
  size_mult: number;
  day_r: number;
  ph_stat?: number;
  recent_mean_r?: number | null;
  recent_trades?: number;
  day_trades?: number;
};

export type Summary = {
  enabled: boolean;
  trade_size_usd?: number;
  week?: WindowStats;
  month?: WindowStats;
  all_time?: WindowStats;
  risk_state?: RiskState;
  allocator?: {
    weights: Record<string, number>;
    stats: Record<string, { n: number; r_mean: number }>;
  };
  learning?: {
    tradeable_regimes: string[];
    excluded_regimes: string[];
    regime_performance: Record<string, RegimePerf>;
    tradeable_directions?: string[];
    direction_performance?: Record<string, RegimePerf>;
    paused_symbols?: string[];
    symbol_gate?: Record<string, RegimePerf>;
    champion_weight_profiles: number;
  };
};

export async function fetchSummary(tradeSize = 1000): Promise<Summary> {
  const res = await fetch(`${API_BASE}/summary?trade_size=${tradeSize}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type FundingCarry = {
  type: string;
  symbol: string;
  current_funding: number;
  half_life_periods: number | null;
  horizon_periods: number;
  expected_collection: number;
  cost: number;
  ev: number;
  annualized_yield: number;
  positive: boolean;
  legs: string;
};

export type FundingScan = {
  enabled: boolean;
  scanned?: number;
  positive?: number;
  opportunities?: FundingCarry[];
};

export async function scanFundingCarry(): Promise<FundingScan> {
  const res = await fetch(`${API_BASE}/arb/funding-scan`, { method: "POST", cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type TriangularScan = {
  enabled: boolean;
  pairs?: number;
  currencies?: number;
  opportunity?: { path: string; net: number; positive: boolean; legs: number } | null;
};

export async function scanTriangular(): Promise<TriangularScan> {
  const res = await fetch(`${API_BASE}/arb/triangular-scan`, { method: "POST", cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type CrossScan = {
  enabled: boolean;
  scanned?: number;
  positive?: number;
  opportunities?: { symbol: string; direction: string; net: number; positive: boolean }[];
};

export async function scanCross(): Promise<CrossScan> {
  const res = await fetch(`${API_BASE}/arb/cross-scan`, { method: "POST", cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export type ArbAlert = { ts: string; type: string; symbol: string; ev: number; annualized_yield: number | null };

export async function fetchArbAlerts(hours = 12): Promise<ArbAlert[]> {
  const res = await fetch(`${API_BASE}/arb/alerts?hours=${hours}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return (await res.json()).alerts ?? [];
}

// ---- Live running trades (core + flash) --------------------------------
export type LiveTrade = {
  id: number; symbol: string; interval: string; market: string;
  strategy: string; paper: boolean; direction: string; regime: string | null;
  entry: number; stop: number | null; target: number | null;
  price: number | null; priced: boolean;
  pnl_pct: number | null; pnl_usd: number | null; progress_pct: number | null;
  r_multiple: number | null; opened_at: string; win_prob: number | null; ev_r: number | null;
};
export type LiveTrades = {
  enabled: boolean;
  count?: number;            // REAL open positions only
  open_pnl_usd?: number;     // floating P&L of those same real positions
  paper_count?: number; paper_pnl_usd?: number;
  unpriced?: number;         // open but no live quote — shown, never dropped
  core_open?: number; flash_open?: number; trades?: LiveTrade[];
};
export async function fetchLiveTrades(tradeSize = 1000, strategy = "core"): Promise<LiveTrades> {
  const res = await fetch(`${API_BASE}/live/trades?trade_size=${tradeSize}&strategy=${strategy}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

export async function closeTrade(signalId: number): Promise<{ ok: boolean; message: string; result?: string; pnl_pct?: number; pnl_usd?: number }> {
  const res = await fetch(`${API_BASE}/trades/${signalId}/close`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Failed to close trade: ${detail || res.statusText}`);
  }
  return res.json();
}


// ---- Flash Bot ----------------------------------------------------------
export type FlashTrigger = {
  blocked_by?: string;
  symbol: string; interval: string; direction: string; kind: string; strength: number;
  entry: number; stop: number; target: number; atr_pct: number;
  cost_r: number; win_prob: number; ev_r: number; tradeable: boolean;
  price_action?: {
    score: number;
    bias: string;
    patterns: string[];
    nearest_support: number | null;
    nearest_resistance: number | null;
    room_to_run_atr: number | null;
    rejection_wick: string;
    liquidity_sweep: any;
  };
};
export type FlashBucket = { trades: number; wins: number; hit_rate: number | null; pnl: number };
export type FlashLearning = {
  window_days: number; min_sample: number;
  stats: { kind: Record<string, FlashBucket>; symbol: Record<string, FlashBucket>; interval: Record<string, FlashBucket> };
  kinds: { allowed: string[]; blocked: string[] };
  symbols: { allowed: string[]; blocked: string[] };
  intervals: { allowed: string[]; blocked: string[] };
};
export type FlashPromotion = {
  paper: boolean; trades: number; needed: number; pnl_frac: number;
  hit_rate: number | null; ready_to_promote: boolean; blocker: string | null;
};
export type FlashScan = {
  enabled: boolean; active?: boolean; scanned?: number; emitted?: number; gated_by_learning?: number;
  win_rate?: number; triggers?: FlashTrigger[];
  stats?: { trades: number; wins: number; hit_rate: number | null; pnl_frac: number };
  learning?: FlashLearning | null; promotion?: FlashPromotion;
};
export async function scanFlash(): Promise<FlashScan> {
  const res = await fetch(`${API_BASE}/flash/scan`, { method: "POST", cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}
export type FlashStatus = {
  enabled: boolean; active: boolean; win_rate: number;
  stats: { trades: number; wins: number; hit_rate: number | null; pnl_frac: number };
  window_days: number; symbols: number; intervals: string[];
};
export async function fetchFlashStatus(): Promise<FlashStatus> {
  const res = await fetch(`${API_BASE}/flash/status`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

// ---- P&L by strategy family --------------------------------------------
export type StrategyStats = {
  trades: number;
  wins: number;
  losses: number;
  hit_rate: number | null;
  realized_pnl_usd: number;
  gross_profit_usd?: number;
  gross_loss_usd?: number;
  profit_factor?: number | null;
  avg_win_usd?: number;
  avg_loss_usd?: number;
  paper?: boolean;
};
export type ByStrategy = {
  enabled: boolean; trade_size_usd?: number;
  strategies?: Record<string, StrategyStats>;
  combined?: StrategyStats & { note?: string };
};
export async function fetchByStrategy(tradeSize = 1000): Promise<ByStrategy> {
  const res = await fetch(`${API_BASE}/performance/by-strategy?trade_size=${tradeSize}`, { cache: "no-store" });
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

// ---- Long-term investments ---------------------------------------------
export type InvestAsset = {
  symbol: string; score: number; tier: string; price: number;
  momentum_12_1: number; ann_return: number; ann_vol: number; sharpe: number;
  drawdown_from_high: number; max_drawdown: number; above_ma200: boolean;
  stability: number; notes: string[];
};
export type InvestScreen = {
  screened: number; tiers: Record<string, number>; assets: InvestAsset[]; horizon: string;
};
export async function fetchInvestments(): Promise<InvestScreen> {
  const res = await fetch(`${API_BASE}/investments/screen`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

// ---- Portfolio allocation ----------------------------------------------
export type Sleeve = {
  name: string; weight: number; allocation_usd: number; trades: number;
  expectancy_pct: number; total_return_pct: number; vol_r: number;
  paper: boolean; reason: string;
};
export type Allocation = {
  equity_usd: number; window_days: number; method: string; deployed_pct: number;
  sleeves: Sleeve[];
  cash: { weight: number; allocation_usd: number; reason: string };
};
export async function fetchAllocation(equity = 1000): Promise<Allocation> {
  const res = await fetch(`${API_BASE}/portfolio/allocation?equity=${equity}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

// ---- Solana DEX <-> CEX arbitrage -------------------------------------
export type SolanaOpp = {
  token: string; dex_price: number; cex_bid: number; cex_ask: number;
  gross_spread: number; cost: number; net: number; direction: string; positive: boolean;
};
export type SolanaScan = {
  enabled: boolean; scanned?: number; positive?: number;
  opportunities?: SolanaOpp[];
  cost_model?: { dex_fee: number; cex_fee: number; network: number; round_trip: number };
  note?: string;
};
export async function scanSolana(): Promise<SolanaScan> {
  const res = await fetch(`${API_BASE}/arb/solana-scan`, { method: "POST", cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

// ---- Proven allocation model (mom252d top5 +MA200 +abs) ----------------
export type ModelHolding = {
  symbol: string; name: string; category: string; price: number; momentum_252d: number;
  above_ma200: boolean; pct_vs_ma200: number; ann_vol: number; weight?: number; reason?: string;
};
export type AllocationModel = {
  model: string; rules: string[];
  holdings: ModelHolding[]; rejected: ModelHolding[];
  cash_weight: number; invested_pct: number; screened: number; stance: string;
  by_category: Record<string, number>;
  backtest: {
    window_days: number; assets: number;
    strategy_total: number; benchmark_total: number;
    strategy_maxdd: number; benchmark_maxdd: number;
    strategy_calmar: number; benchmark_calmar: number; note: string;
  };
};
export async function fetchAllocationModel(): Promise<AllocationModel> {
  const res = await fetch(`${API_BASE}/investments/model`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

// ---- Universe: every instrument the system can see -------------------------
export type Instrument = {
  symbol: string; name: string; category: string; group: string;
  provider: string; provider_symbol: string;
  allocatable: boolean; note: string;
  quote_volume?: number; price?: number; change_pct?: number;
};
export type UniverseCounts = {
  by_category: Record<string, { total: number; allocatable: number }>;
  total: number; allocatable: number;
};
export type UniverseResponse = { counts: UniverseCounts; instruments: Instrument[] };

export async function fetchUniverse(category?: string): Promise<UniverseResponse> {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  const res = await fetch(`${API_BASE}/universe${qs}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

// ---- Live risk state: exposure ceiling + drawdown throttle -----------------
export type RiskExposure = {
  equity_usd: number; high_water_usd: number;
  open_positions: number; open_by_market: Record<string, number>;
  max_concurrent: number; class_cap: number;
  open_notional_usd: number; gross_used: number; gross_ceiling: number;
  throttle: number; budget_usd: number; remaining_usd: number; can_open: boolean;
};
export async function fetchRiskExposure(): Promise<RiskExposure> {
  const res = await fetch(`${API_BASE}/risk/exposure`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}

// ---- Rebalancing engine: the measured edge that forecasts nothing ---------
export type RebalHolding = {
  symbol: string; name: string; category: string; price: number;
  target_weight: number; current_weight: number; class_weight: number;
  drift_pct: number; action: "trim" | "add" | "hold"; ann_vol: number;
};
export type RebalanceModel = {
  model: string; rules: string[]; stance: string; screened: number;
  holdings: RebalHolding[]; by_category: Record<string, number>;
  rebalance: { band_pct: number; trim: string[]; add: string[]; note: string };
  backtest: {
    window_days: number; baskets_tested: number;
    median_total: number; worst_total: number; best_total: number;
    median_maxdd: number; worst_maxdd: number; median_sharpe: number;
    beat_benchmark: string; benchmark_total: number; benchmark_maxdd: number;
    no_rebalance_total: number; note: string;
  };
};
export async function fetchRebalanceModel(): Promise<RebalanceModel> {
  const res = await fetch(`${API_BASE}/investments/rebalance`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend ${res.status}`);
  return res.json();
}
