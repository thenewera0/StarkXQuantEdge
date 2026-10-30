"""Zero-Cost Live NSE Data & Option Chain Adapter.

Provides keyless, free access to National Stock Exchange of India (NSE) live market data:
1. Index Option Chain (Nifty 50, BankNifty) via direct NSE India public JSON endpoints.
2. Automatic session cookie lifecycle management (refreshes nsit/nseappid every 4 minutes).
3. Option Greeks & institutional metrics: PCR OI, PCR Change OI, ATM Straddle IV, Max Pain, Call Wall, Put Floor.
4. Robust fallback to cached snapshots and synthetic volatility surface estimation via Yahoo Finance (^INDIAVIX, ^NSEI)
   when outside IST market hours or if NSE rate-limits.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_NSE_BASE = "https://www.nseindia.com"
_OPTION_CHAIN_INDEX_URL = f"{_NSE_BASE}/api/option-chain-indices"
_OPTION_CHAIN_EQUITY_URL = f"{_NSE_BASE}/api/option-chain-equities"
_OPTION_CHAIN_REFERER = f"{_NSE_BASE}/option-chain"

_DESKTOP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": _NSE_BASE,
    "Connection": "keep-alive",
}

_API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": _OPTION_CHAIN_REFERER,
    "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

# Cache for option chains: symbol -> (timestamp, data_dict)
_CACHE_TTL_SECONDS = 60.0  # 1 minute fresh cache
_chain_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()


class NSEFreeAdapter:
    """Asynchronous and synchronous fault-tolerant client for NSE India public endpoints."""

    def __init__(self, cookie_refresh_interval: int = 240):
        self._cookie_refresh_interval = cookie_refresh_interval
        self._last_cookie_refresh = 0.0
        self._cookies: Dict[str, str] = {}
        self._session_lock = threading.Lock()

    def _refresh_cookies_sync(self) -> None:
        """Hit the HTML option chain page to warm up session cookies."""
        now = time.time()
        if now - self._last_cookie_refresh < self._cookie_refresh_interval and self._cookies:
            return

        with self._session_lock:
            if now - self._last_cookie_refresh < self._cookie_refresh_interval and self._cookies:
                return
            try:
                with httpx.Client(headers=_DESKTOP_HEADERS, follow_redirects=True, timeout=12.0) as client:
                    r1 = client.get(_NSE_BASE)
                    cookies_dict = dict(r1.cookies)
                    # Next hit option chain page to get specific routing cookies
                    r2 = client.get(_OPTION_CHAIN_REFERER, cookies=cookies_dict)
                    cookies_dict.update(dict(r2.cookies))
                    self._cookies = cookies_dict
                    self._last_cookie_refresh = time.time()
                    logger.debug("NSE session cookies warmed: %s keys", list(self._cookies.keys()))
            except Exception as e:
                logger.warning("NSE cookie refresh encountered warning: %s", e)
                # Keep existing cookies if any

    async def _refresh_cookies_async(self) -> None:
        """Async variant of cookie refresh."""
        now = time.time()
        if now - self._last_cookie_refresh < self._cookie_refresh_interval and self._cookies:
            return

        with self._session_lock:
            if now - self._last_cookie_refresh < self._cookie_refresh_interval and self._cookies:
                return

        try:
            async with httpx.AsyncClient(headers=_DESKTOP_HEADERS, follow_redirects=True, timeout=12.0) as client:
                r1 = await client.get(_NSE_BASE)
                cookies_dict = dict(r1.cookies)
                r2 = await client.get(_OPTION_CHAIN_REFERER, cookies=cookies_dict)
                cookies_dict.update(dict(r2.cookies))
                with self._session_lock:
                    self._cookies = cookies_dict
                    self._last_cookie_refresh = time.time()
        except Exception as e:
            logger.warning("NSE async cookie refresh warning: %s", e)

    def _calculate_metrics(self, payload: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Extract quantitative institutional metrics from NSE option chain payload."""
        records = (payload.get("records") or {})
        data = records.get("data") or []
        underlying_val = float(records.get("underlyingValue") or 0.0)
        timestamp_str = records.get("timestamp") or datetime.now(timezone.utc).isoformat()
        expiry_dates = records.get("expiryDates") or []
        nearest_expiry = expiry_dates[0] if expiry_dates else None

        if not data or underlying_val <= 0:
            raise ValueError(f"Empty option chain records for {symbol}")

        total_call_oi = 0
        total_put_oi = 0
        total_call_change_oi = 0
        total_put_change_oi = 0

        call_wall_strike = 0.0
        max_call_oi = -1
        put_floor_strike = 0.0
        max_put_oi = -1

        strikes_data: List[Dict[str, Any]] = []
        atm_strike = None
        min_atm_diff = float("inf")

        for row in data:
            strike = float(row.get("strikePrice") or 0.0)
            row_expiry = row.get("expiryDate")
            # If multi-expiry payload, prioritize nearest expiry
            if nearest_expiry and row_expiry and row_expiry != nearest_expiry:
                continue

            ce = row.get("CE") or {}
            pe = row.get("PE") or {}

            ce_oi = int(ce.get("openInterest") or 0)
            pe_oi = int(pe.get("openInterest") or 0)
            ce_chg = int(ce.get("changeinOpenInterest") or 0)
            pe_chg = int(pe.get("changeinOpenInterest") or 0)
            ce_iv = float(ce.get("impliedVolatility") or 0.0)
            pe_iv = float(pe.get("impliedVolatility") or 0.0)

            total_call_oi += ce_oi
            total_put_oi += pe_oi
            total_call_change_oi += ce_chg
            total_put_change_oi += pe_chg

            if ce_oi > max_call_oi:
                max_call_oi = ce_oi
                call_wall_strike = strike
            if pe_oi > max_put_oi:
                max_put_oi = pe_oi
                put_floor_strike = strike

            diff = abs(strike - underlying_val)
            if diff < min_atm_diff:
                min_atm_diff = diff
                atm_strike = strike

            strikes_data.append({
                "strike": strike,
                "ce_oi": ce_oi,
                "pe_oi": pe_oi,
                "ce_iv": ce_iv,
                "pe_iv": pe_iv,
                "ce_ltp": float(ce.get("lastPrice") or 0.0),
                "pe_ltp": float(pe.get("lastPrice") or 0.0),
            })

        # Calculate Max Pain (strike that minimizes total option writer payout)
        max_pain_strike = underlying_val
        min_total_loss = float("inf")
        if strikes_data:
            candidate_strikes = [s["strike"] for s in strikes_data]
            for K in candidate_strikes:
                total_loss = 0.0
                for s in strikes_data:
                    # CE in the money if K > strike
                    if K > s["strike"]:
                        total_loss += (K - s["strike"]) * s["ce_oi"]
                    # PE in the money if K < strike
                    elif K < s["strike"]:
                        total_loss += (s["strike"] - K) * s["pe_oi"]
                if total_loss < min_total_loss:
                    min_total_loss = total_loss
                    max_pain_strike = K

        # ATM Straddle IV
        atm_straddle_iv = 14.5
        if atm_strike is not None:
            atm_row = next((s for s in strikes_data if s["strike"] == atm_strike), None)
            if atm_row:
                ivs = [iv for iv in (atm_row["ce_iv"], atm_row["pe_iv"]) if iv > 0]
                if ivs:
                    atm_straddle_iv = round(sum(ivs) / len(ivs), 2)

        pcr_oi = round(total_put_oi / max(total_call_oi, 1), 4)
        pcr_change_oi = round(total_put_change_oi / max(total_call_change_oi, 1), 4)

        return {
            "symbol": symbol.upper(),
            "underlying_value": underlying_val,
            "timestamp": timestamp_str,
            "nearest_expiry": nearest_expiry,
            "pcr_oi": pcr_oi,
            "pcr_change_oi": pcr_change_oi,
            "atm_strike": atm_strike or underlying_val,
            "atm_straddle_iv": atm_straddle_iv,
            "max_pain_strike": max_pain_strike,
            "call_wall_strike": call_wall_strike,
            "put_floor_strike": put_floor_strike,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "is_synthetic": False,
        }

    def _synthetic_fallback(self, symbol: str) -> Dict[str, Any]:
        """Construct synthetic volatility & strike matrix from Yahoo Finance when NSE is closed/rate-limited."""
        from .yahoo import quote as yahoo_quote

        sym_upper = symbol.upper()
        yahoo_sym = "^NSEI" if "NIFTY" in sym_upper and "BANK" not in sym_upper else "^NSEBANK"
        q_idx = yahoo_quote(yahoo_sym)
        q_vix = yahoo_quote("^INDIAVIX")

        spot = float(q_idx["price"]) if q_idx else (24500.0 if "BANK" not in sym_upper else 51500.0)
        vix = float(q_vix["price"]) if q_vix else 13.8

        round_base = 50.0 if "BANK" not in sym_upper else 100.0
        atm = round(spot / round_base) * round_base
        max_pain = atm
        call_wall = atm + round_base * 4
        put_floor = atm - round_base * 4

        return {
            "symbol": sym_upper,
            "underlying_value": spot,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nearest_expiry": "SYNTHETIC_WEEKLY",
            "pcr_oi": 1.05,
            "pcr_change_oi": 1.12,
            "atm_strike": atm,
            "atm_straddle_iv": round(vix, 2),
            "max_pain_strike": max_pain,
            "call_wall_strike": call_wall,
            "put_floor_strike": put_floor,
            "total_call_oi": 1250000,
            "total_put_oi": 1312500,
            "is_synthetic": True,
        }

    def fetch_index_option_chain(self, symbol: str = "NIFTY") -> Dict[str, Any]:
        """Synchronously fetch and parse index option chain with automatic caching & fallback."""
        sym_clean = symbol.upper()
        now = time.time()

        with _cache_lock:
            cached = _chain_cache.get(sym_clean)
            if cached and (now - cached[0] < _CACHE_TTL_SECONDS):
                return cached[1].copy()

        self._refresh_cookies_sync()

        url = f"{_OPTION_CHAIN_INDEX_URL}?symbol={sym_clean}"
        try:
            with httpx.Client(headers=_API_HEADERS, cookies=self._cookies, timeout=10.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    metrics = self._calculate_metrics(data, sym_clean)
                    with _cache_lock:
                        _chain_cache[sym_clean] = (now, metrics)
                    return metrics
                else:
                    logger.info("NSE API returned status %d for %s; using synthetic fallback", resp.status_code, sym_clean)
        except Exception as e:
            logger.info("NSE fetch error for %s: %s; falling back to synthetic", sym_clean, e)

        fallback = self._synthetic_fallback(sym_clean)
        with _cache_lock:
            _chain_cache[sym_clean] = (now, fallback)
        return fallback

    async def fetch_index_option_chain_async(self, symbol: str = "NIFTY") -> Dict[str, Any]:
        """Asynchronous variant of fetch_index_option_chain."""
        sym_clean = symbol.upper()
        now = time.time()

        with _cache_lock:
            cached = _chain_cache.get(sym_clean)
            if cached and (now - cached[0] < _CACHE_TTL_SECONDS):
                return cached[1].copy()

        await self._refresh_cookies_async()

        url = f"{_OPTION_CHAIN_INDEX_URL}?symbol={sym_clean}"
        try:
            async with httpx.AsyncClient(headers=_API_HEADERS, cookies=self._cookies, timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    metrics = self._calculate_metrics(data, sym_clean)
                    with _cache_lock:
                        _chain_cache[sym_clean] = (now, metrics)
                    return metrics
        except Exception as e:
            logger.info("NSE async fetch error for %s: %s; falling back", sym_clean, e)

        fallback = self._synthetic_fallback(sym_clean)
        with _cache_lock:
            _chain_cache[sym_clean] = (now, fallback)
        return fallback


# Singleton adapter instance
_default_adapter = NSEFreeAdapter()


def get_nse_adapter() -> NSEFreeAdapter:
    """Return singleton NSEFreeAdapter instance."""
    return _default_adapter


def fetch_index_option_chain(symbol: str = "NIFTY") -> Dict[str, Any]:
    """Top-level helper to fetch option chain metrics for NIFTY or BANKNIFTY."""
    return _default_adapter.fetch_index_option_chain(symbol)


async def fetch_index_option_chain_async(symbol: str = "NIFTY") -> Dict[str, Any]:
    """Top-level async helper to fetch option chain metrics for NIFTY or BANKNIFTY."""
    return await _default_adapter.fetch_index_option_chain_async(symbol)
