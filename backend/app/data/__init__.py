"""Market data fetchers. Binance public endpoints need no API key; others use keys from .env."""

from .binance import (
    fetch_klines,
    fetch_klines_history,
    fetch_klines_range,
    fetch_depth,
    fetch_long_short_ratio,
    fetch_funding_basis,
    fetch_funding_history,
    fetch_oi_trend,
    INTERVAL_SECONDS,
)
from .twelvedata import fetch_klines as fetch_klines_td
from .news import news_sentiment
from .coinmarketcap import crypto_macro_score, fetch_global_metrics
from .fng import fear_greed, fng_score, fng_zscore
from .cryptoquant import onchain_score

__all__ = [
    "fetch_klines",
    "fetch_klines_history",
    "fetch_klines_range",
    "INTERVAL_SECONDS",
    "fetch_depth",
    "fetch_long_short_ratio",
    "fetch_funding_basis",
    "fetch_funding_history",
    "fetch_oi_trend",
    "fetch_klines_td",
    "news_sentiment",
    "crypto_macro_score",
    "fetch_global_metrics",
    "fear_greed",
    "fng_score",
    "fng_zscore",
    "onchain_score",
]
