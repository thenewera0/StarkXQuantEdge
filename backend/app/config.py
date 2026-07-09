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


settings = Settings()
