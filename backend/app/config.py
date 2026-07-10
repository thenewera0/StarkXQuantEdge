"""Environment-backed settings. Nothing here is required for the Phase 1a backtest core."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    # Comma-separated allowed origins for CORS (add your Vercel URL in production).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Webhook (Phase 0 stub)
    tradingview_webhook_secret: str = "changeme-shared-secret"

    # LLM reasoning (OpenRouter). Strong model = bull/bear/risk debate (quality matters);
    # cheap model = the per-signal rationale (simple narration, ~5-10x cheaper).
    openrouter_api_key: str = ""
    openrouter_model_strong: str = "openrouter/auto"
    openrouter_model_cheap: str = "openai/gpt-4o-mini"

    # Forex / US markets / global indicators
    twelvedata_api_key: str = ""
    alphavantage_api_key: str = ""

    # News
    newsapi_key: str = ""

    # Crypto reference / macro (deferred wiring)
    coinmarketcap_api_key: str = ""
    coinapi_key: str = ""
    freecryptoapi_key: str = ""

    # On-chain (CryptoQuant) — best-effort; on-chain family neutral if endpoints not accessible
    cryptoquant_api_key: str = ""

    # Risk geometry (Confluence Engine L5)
    risk_per_trade_pct: float = 0.75      # account % risked per trade
    min_reward_risk: float = 1.5          # hard RR gate; below this, no actionable signal
    conviction_floor: float = 25.0        # |composite| below this = no trade (silence)

    # EV gate (Blueprint v2 §2.6): a setup trades only if its calibrated expected value clears a
    # threshold AFTER modelled costs. EV = p*R - (1-p) - cost_in_R, where p is the isotonic-
    # calibrated P(win) and R the reward:risk. min_ev_r=0.0 = "don't take negative-EV bets"
    # (tighter per-tier thresholds arrive with the capital engine in P2).
    ev_gate_enabled: bool = True
    min_ev_r: float = 0.0

    # Meta-labeling model (Blueprint v2 §5). Runs in SHADOW by default: its P(win) is computed and
    # logged on every signal, but only feeds the EV gate once the model is PROMOTED (beats the
    # primary calibrated prob out-of-sample AND has enough samples). Flip enables gating on it.
    meta_gate_enabled: bool = True   # allow a PROMOTED model to drive EV; shadow-only until promoted

    # Self-calibration monitor (Blueprint v2 §4.6): shrink size when the calibrated probabilities
    # stop matching outcomes (rolling Brier worse than the base rate). "Knows when it doesn't know."
    calibration_monitor_enabled: bool = True
    calibration_min_trades: int = 20
    calibration_size_floor: float = 0.4

    # Drift detection -> automatic de-risk (Blueprint v2 §4.2). Page-Hinkley on the per-trade R
    # sequence; on a downward expectancy shift, raise the EV floor and cut size until the bad run
    # ages out of the trailing window (auto-recovery).
    drift_enabled: bool = True
    drift_window_trades: int = 80      # trailing window the PH test runs over
    drift_min_trades: int = 20         # need this many resolved trades before trusting the test
    drift_delta: float = 0.1           # tolerated drift magnitude (R) before accumulating
    drift_lambda: float = 3.0          # PH detection threshold (cumulative R of downward deviation)
    drift_ev_add: float = 0.4          # add this to min_ev_r while drifting (0.0 -> 0.4R)
    drift_size_mult: float = 0.5       # cut advised size while drifting

    # Global circuit breaker (§4 safety rails): halt new signals for the cooldown window if realized
    # R over the last N hours falls below the floor. Rolls off automatically.
    circuit_breaker_enabled: bool = True
    circuit_breaker_r: float = -3.0
    circuit_window_hours: int = 24
    circuit_min_trades: int = 5        # don't trip on a tiny sample

    # Range-fade family (Blueprint v2 §2.2 / §3.3). In a range regime the engine fades extremes
    # (targets the mean), so it uses a looser RR floor (fades win often but small) and only fires
    # when the measured Ornstein-Uhlenbeck reversion half-life is short enough that the range is
    # genuinely mean-reverting (not drifting/breaking out).
    min_reward_risk_range: float = 1.0
    range_max_halflife_bars: float = 24.0

    # Regime filter (Confluence Engine L1 gate): only trade trend regimes; stand down in
    # range / high_vol / squeeze where the live per-regime P&L is negative.
    regime_filter_enabled: bool = True
    # Data-driven upgrade: only trade regimes with PROVEN positive expectancy from live outcomes.
    # Thin regimes (< min_sample) fall back to the trend-only default; proven-losing regimes are
    # dropped automatically. This is the self-improving loss-cutting gate.
    regime_perf_gate_enabled: bool = True
    regime_perf_min_sample: int = 12
    regime_perf_window_days: int = 4   # short rolling window -> reacts to the current market fast

    # Per-direction performance gate: stop trading a direction (long/short) with proven negative
    # expectancy over a SHORT rolling window; re-enables automatically as the losing trades age out
    # of the window (auto re-exploration) or it turns profitable again.
    direction_perf_gate_enabled: bool = True
    direction_perf_min_sample: int = 10
    direction_perf_window_days: int = 2

    # Per-symbol performance gate: pause any symbol with proven negative expectancy (e.g. forex
    # pairs that lack derivatives/on-chain data and lose). Re-tests as losing trades age out.
    symbol_perf_gate_enabled: bool = True
    symbol_perf_min_sample: int = 12
    symbol_perf_window_days: int = 5

    # Performance / P&L (fixed notional per trade for the paper track record)
    standard_trade_size_usd: float = 1000.0

    # Capital-adaptive sizing (Blueprint v2 §7). The operator's actual equity drives the tier,
    # Kelly+ruin sizing, and the per-tier EV threshold. The paper track still uses the fixed
    # notional above for comparability; this only sets the RECOMMENDED size shown per signal.
    account_equity_usd: float = 1000.0
    min_notional_usd: float = 5.0
    tier_ev_gate_enabled: bool = True   # use the tier's EV threshold as the EV floor

    # Multiplicative-weights (Hedge) strategy allocator (Blueprint v2 §4.3): shift capital toward
    # whichever strategy family (trend / range-fade) is currently paying, with a floor so none dies.
    allocator_enabled: bool = True
    allocator_window_days: int = 14
    allocator_halflife_days: float = 7.0
    allocator_eta: float = 1.5          # Hedge learning rate on decayed mean R
    allocator_min_trades: int = 8       # a family needs this many trades before it can tilt
    allocator_floor: float = 0.05       # min weight per family (never fully starve one)
    allocator_max_mult: float = 1.8     # cap on a family's size multiplier

    # Supabase / Postgres (Phase 3 persistence)
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_service_role_key: str = ""
    # Direct Postgres connection string used for server-side writes + migrations.
    database_url: str = ""

    # Auto-outcome resolver (Phase 3 learning loop)
    resolver_enabled: bool = True
    resolver_interval_minutes: int = 15
    resolver_max_hold_bars: int = 48

    # Autonomous signal scanner
    scanner_enabled: bool = True
    scanner_interval_minutes: int = 30
    scanner_min_confidence: float = 55.0

    # Funding-carry arbitrage detector (Blueprint v2 §6.1). Delta-neutral funding harvest, gated on
    # expected funding (AR(1) forecast) minus round-trip cost of both legs. Detection only.
    arb_funding_enabled: bool = True
    arb_horizon_periods: int = 9        # 8h funding periods to hold (~3 days)
    arb_spot_taker: float = 0.001       # spot taker fee per fill
    arb_perp_taker: float = 0.0004      # perp taker fee per fill
    arb_buffer: float = 0.0005          # safety buffer above breakeven
    arb_min_history: int = 20           # min funding-history points to fit AR(1)
    arb_symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT"

    @property
    def arb_symbols_list(self) -> list[str]:
        return [s.strip().upper() for s in self.arb_symbols.split(",") if s.strip()]


settings = Settings()
