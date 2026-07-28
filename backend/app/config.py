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
    conviction_floor: float = 18.0        # |composite| below this = no trade (silence). Lowered so
                                          # more real setups reach the EV gate (which is the real filter).

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
    meta_retrain_days: int = 2       # meta-model re-evaluation cadence (fast; shadow-learning feeds it)

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
    drift_window_days: int = 10        # AND only recent trades count, so drift recovers when idle
    drift_min_trades: int = 20         # need this many resolved trades before trusting the test
    drift_delta: float = 0.1           # tolerated drift magnitude (R) before accumulating
    drift_lambda: float = 3.0          # PH detection threshold (cumulative R of downward deviation)
    drift_ev_floor: float = 0.4        # §4.2: RAISE the EV floor TO this level while drifting (not additive)
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
    # WAS 5 DAYS AND THEREFORE DEAD: at current trade frequency no symbol ever reached 12 resolved
    # trades inside a 5-day window, so this gate could never block anything. Measured over 30 days
    # it has real evidence to act on (e.g. SOL 33% hit / -$26, DOGE 35% / -$25, while ADA runs 81%).
    symbol_perf_window_days: int = 30

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
    scanner_min_confidence: float = 45.0   # don't double-filter: the EV gate already vetted it

    # --- Portfolio allocation across sleeves (app/portfolio.py) -----------------------------
    portfolio_cash_floor: float = 0.25    # always hold dry powder
    portfolio_max_weight: float = 0.40    # no sleeve can be a single point of failure
    portfolio_min_trades: int = 25        # below this a sleeve only gets a starter allocation

    # --- Short qualification (app/shorts.py) ------------------------------------------------
    # Derived from 321 live outcomes: shorts lost in EVERY regime (8-23% hit) while longs won in
    # the same regimes (51-66%) — they were counter-trend shorts in a dip-buying tape. A short now
    # has to prove it is an actual downtrend before it may fire.
    short_gate_enabled: bool = True
    short_min_conviction: float = 52.0    # winning shorts scored 52-69; losers 31-49
    short_min_funding: float = 0.0        # want crowded LONGS to flush, not an already-short crowd

    # --- Flash Bot: fast 5m/15m scalper, its own strategy family + P&L ---------------------
    # Deliberately far more active than the core swing engine: it hunts momentum bursts, breakouts
    # and stretched-VWAP snaps, takes tight risk and exits fast. Still cost-gated (a 5m scalp must
    # clear a REAL round-trip cost) and self-protecting (stands down if its own record goes negative).
    # NOTE on geometry: a TIGHT stop is what kills scalpers — round-trip cost becomes a huge
    # fraction of risk (measured: a 1.0x-ATR stop on 5m put cost at ~69% of risk, unwinnable).
    # Wider stops + higher RR push cost down to a small fraction, which is what makes fast trading
    # economically viable at all.
    flash_enabled: bool = True
    # PAPER MODE (measured, not a guess): a 2,791-trade causal backtest of these triggers net of
    # real costs returned 35.2% win rate, PF 0.65, -0.35%/trade — every kind, interval and direction
    # negative. So flash TRADES CONTINUOUSLY but on paper, building a real record; it is promoted to
    # live capital only if that record proves positive. Same shadow->prove->promote discipline as
    # the meta-model. Flip to False only when the flash P&L is genuinely positive.
    flash_paper_mode: bool = True
    flash_interval_minutes: int = 5        # scan cadence
    flash_stop_atr: float = 2.2            # stop distance = this x ATR (wide enough to beat costs)
    flash_rr: float = 2.0                  # target = flash_rr x stop
    flash_min_ev_r: float = 0.0            # must be positive-EV after cost
    flash_min_atr_pct: float = 0.0012      # skip dead tape (needs range to clear fees)
    flash_vol_expansion: float = 1.15      # volume vs its 20-bar average for a burst
    flash_breakout_bars: int = 15          # N-bar extreme for the breakout trigger
    flash_snap_stretch: float = 0.0035     # VWAP distance that counts as stretched
    flash_max_hold_bars: int = 30          # hard time-stop (a scalp never becomes a swing)
    flash_risk_pct: float = 0.35           # advised risk per flash trade (smaller than core)
    flash_prior_win_rate: float = 0.42     # conservative prior until it has its own record
    flash_perf_window_days: int = 7
    flash_perf_min_sample: int = 20

    # Flash self-learning: the bot narrows to what its OWN outcomes prove, using the same gate
    # pattern that created the core engine's edge (per-kind / per-symbol / per-interval).
    # Thin buckets keep exploring; proven-negative buckets are dropped until they age out.
    flash_learn_enabled: bool = True
    flash_learn_window_days: int = 21
    flash_learn_min_sample: int = 15       # evidence needed before a bucket can be blocked
    # Graduation from paper to real capital — decided purely by its own realized record.
    flash_promote_min_trades: int = 120
    flash_promote_min_hit: float = 0.40

    # Funding-carry arbitrage detector (Blueprint v2 §6.1). Delta-neutral funding harvest, gated on
    # expected funding (AR(1) forecast) minus round-trip cost of both legs. Detection only.
    arb_funding_enabled: bool = True
    arb_horizon_periods: int = 9        # 8h funding periods to hold (~3 days)
    arb_spot_taker: float = 0.001       # spot taker fee per fill
    arb_perp_taker: float = 0.0004      # perp taker fee per fill
    arb_buffer: float = 0.0005          # safety buffer above breakeven
    arb_min_history: int = 20           # min funding-history points to fit AR(1)
    # Widened universe — thinner alts spike harder, so more chances to catch a real funding window.
    arb_symbols: str = ("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,"
                        "LINKUSDT,LTCUSDT,DOTUSDT,TRXUSDT,ATOMUSDT,UNIUSDT,NEARUSDT,APTUSDT,"
                        "ARBUSDT,OPUSDT,FILUSDT,INJUSDT,SUIUSDT,SEIUSDT,TIAUSDT,AAVEUSDT")

    # Solana DEX <-> CEX arbitrage detector (app/solana.py). Detection only.
    solana_arb_enabled: bool = True
    solana_dex_fee: float = 0.0025      # typical Solana AMM pool fee
    solana_cex_fee: float = 0.001       # Binance taker
    solana_network_fee: float = 0.0002  # gas + priority, as a fraction of a typical clip
    solana_buffer: float = 0.0005       # must clear this to count as an opportunity
    # Gross spread that counts as a DISLOCATION — the only regime where flash-loan arb pays.
    # Calm markets measure ~0.1%; stress events (cascades, depegs) blow past 0.5%.
    solana_dislocation_gross: float = 0.005
    solana_flash_fee: float = 0.0        # Balancer V2 / Morpho lend at 0%; Aave V3 would be 0.0005

    # Triangular-arb detector (§6.2): Bellman-Ford negative-cycle over the currency graph.
    arb_triangular_enabled: bool = True
    arb_tri_fee: float = 0.001          # taker fee per conversion (0.075% with BNB discount)
    arb_tri_buffer: float = 0.0005      # net must clear this to count as an opportunity

    # Cross-exchange inventory-arb detector (§6.3): Binance vs Bybit spot, simultaneous (no transfer).
    arb_cross_enabled: bool = True
    arb_cross_fee_binance: float = 0.001
    arb_cross_fee_bybit: float = 0.001
    arb_cross_buffer: float = 0.0005

    @property
    def arb_symbols_list(self) -> list[str]:
        return [s.strip().upper() for s in self.arb_symbols.split(",") if s.strip()]


settings = Settings()
