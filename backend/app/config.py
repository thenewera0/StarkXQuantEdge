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

    # Regime filter (Confluence Engine L1 gate): only trade trend regimes; stand down in
    # range / high_vol / squeeze where the live per-regime P&L is negative.
    regime_filter_enabled: bool = True
    # Data-driven upgrade: only trade regimes with PROVEN positive expectancy from live outcomes.
    # Thin regimes (< min_sample) fall back to the trend-only default; proven-losing regimes are
    # dropped automatically. This is the self-improving loss-cutting gate.
    regime_perf_gate_enabled: bool = True
    regime_perf_min_sample: int = 12

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
