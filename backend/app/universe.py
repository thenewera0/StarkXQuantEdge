"""The tradable universe — every instrument the system can see, across every asset class.

Breadth exists for one measured reason. The single technique in this project with proven,
structural edge is the 200-day trend filter (`investments.allocation_model`), and a trend-following
allocator's edge scales with the number of GENUINELY UNCORRELATED trends it can choose between.
Twenty crypto pairs are not twenty bets — crypto majors run ~0.8 correlated, so that universe is
closer to one bet sized twenty times (the exact failure that stopped out 18 correlated longs on
2026-07-28). Gold, the yen, natural gas, 30-year Treasuries and corn are the real diversifiers:
they trend on different clocks and different drivers, and several of them trend hardest precisely
when crypto is falling apart.

    crypto       Binance spot, ranked live by 24h quote volume  (no key)
    forex        Yahoo  'EURUSD=X'   — majors, crosses, EM exotics
    commodities  Yahoo  'GC=F'       — metals, energy, grains, softs, livestock
    indices      Yahoo  '^GSPC'      — global equity benchmarks
    rates        Yahoo  'TLT','ZN=F' — the govvy curve, credit, and yield indices

Symbols are canonical inside the system (`EUR/USD`, `XAU/USD`, `SPX`, `US10Y`, `BTCUSDT`) and
translated to each provider's dialect only at the fetch boundary, so nothing downstream cares who
served the bars.

Everything here is free and keyless. No paid tier, no quota to run out mid-scan.
"""

from __future__ import annotations

import threading
import time

import pandas as pd

# --------------------------------------------------------------------------------------
# FOREX — canonical 'EUR/USD' -> Yahoo 'EURUSD=X'
# --------------------------------------------------------------------------------------
_FX_MAJORS = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"]
_FX_CROSSES = [
    "EUR/GBP", "EUR/JPY", "EUR/CHF", "EUR/CAD", "EUR/AUD", "EUR/NZD", "EUR/SEK", "EUR/NOK",
    "GBP/JPY", "GBP/CHF", "GBP/CAD", "GBP/AUD", "GBP/NZD", "GBP/SEK", "GBP/NOK",
    "AUD/JPY", "NZD/JPY", "CAD/JPY", "CHF/JPY", "SGD/JPY", "ZAR/JPY", "NOK/JPY", "SEK/JPY",
    "AUD/CAD", "AUD/CHF", "AUD/NZD", "AUD/SGD", "NZD/CAD", "NZD/CHF", "CAD/CHF", "CHF/NOK",
    "EUR/PLN", "EUR/HUF", "EUR/CZK", "EUR/TRY", "EUR/ZAR", "EUR/SGD", "EUR/HKD", "EUR/MXN",
    "EUR/DKK", "EUR/ILS", "EUR/RON", "GBP/ZAR", "GBP/SGD", "GBP/HKD", "GBP/PLN", "GBP/TRY",
]
_FX_EXOTICS = [
    "USD/SEK", "USD/NOK", "USD/DKK", "USD/PLN", "USD/HUF", "USD/CZK", "USD/TRY", "USD/ZAR",
    "USD/MXN", "USD/SGD", "USD/HKD", "USD/CNY", "USD/INR", "USD/KRW", "USD/THB", "USD/IDR",
    "USD/PHP", "USD/MYR", "USD/BRL", "USD/CLP", "USD/COP", "USD/PEN", "USD/ARS", "USD/ILS",
    "USD/RON", "USD/TWD", "USD/VND", "USD/NGN", "USD/EGP", "USD/KES", "USD/SAR", "USD/AED",
    "USD/QAR", "USD/ISK", "USD/UAH", "USD/PKR", "USD/BDT", "USD/LKR",
    "USD/MAD", "USD/GHS", "USD/TZS", "USD/UGX", "USD/XOF", "USD/JOD", "USD/KWD", "USD/BHD",
]

# --------------------------------------------------------------------------------------
# COMMODITIES — canonical -> (Yahoo future, display name, sub-group)
# --------------------------------------------------------------------------------------
_COMMODITIES: dict[str, tuple[str, str, str]] = {
    # precious + industrial metals
    "XAU/USD": ("GC=F", "Gold", "metals"),
    "XAG/USD": ("SI=F", "Silver", "metals"),
    "XPT/USD": ("PL=F", "Platinum", "metals"),
    "XPD/USD": ("PA=F", "Palladium", "metals"),
    "COPPER":  ("HG=F", "Copper", "metals"),
    "GOLD/MICRO": ("MGC=F", "Micro Gold", "metals"),
    "SILVER/MICRO": ("SIL=F", "Micro Silver", "metals"),
    # energy
    "WTI":     ("CL=F", "WTI Crude Oil", "energy"),
    "BRENT":   ("BZ=F", "Brent Crude Oil", "energy"),
    "NATGAS":  ("NG=F", "Natural Gas", "energy"),
    "HEATOIL": ("HO=F", "Heating Oil", "energy"),
    "GASOLINE": ("RB=F", "RBOB Gasoline", "energy"),
    # grains
    "CORN":    ("ZC=F", "Corn", "grains"),
    "WHEAT":   ("ZW=F", "Chicago Wheat", "grains"),
    "WHEAT/KC": ("KE=F", "Kansas City Wheat", "grains"),
    "SOYBEAN": ("ZS=F", "Soybeans", "grains"),
    "SOYMEAL": ("ZM=F", "Soybean Meal", "grains"),
    "SOYOIL":  ("ZL=F", "Soybean Oil", "grains"),
    "OATS":    ("ZO=F", "Oats", "grains"),
    "RICE":    ("ZR=F", "Rough Rice", "grains"),
    # softs
    "SUGAR":   ("SB=F", "Sugar No.11", "softs"),
    "COFFEE":  ("KC=F", "Coffee C", "softs"),
    "COCOA":   ("CC=F", "Cocoa", "softs"),
    "COTTON":  ("CT=F", "Cotton No.2", "softs"),
    "OJ":      ("OJ=F", "Orange Juice", "softs"),
    "LUMBER":  ("LBR=F", "Lumber", "softs"),
    # livestock
    "CATTLE":  ("LE=F", "Live Cattle", "livestock"),
    "FEEDER":  ("GF=F", "Feeder Cattle", "livestock"),
    "HOGS":    ("HE=F", "Lean Hogs", "livestock"),
}

# --------------------------------------------------------------------------------------
# EQUITY INDICES — canonical -> (Yahoo, name, region)
# --------------------------------------------------------------------------------------
_INDICES: dict[str, tuple[str, str, str]] = {
    "SPX":    ("^GSPC", "S&P 500", "US"),
    "NDX":    ("^NDX", "Nasdaq 100", "US"),
    "COMP":   ("^IXIC", "Nasdaq Composite", "US"),
    "DJI":    ("^DJI", "Dow Jones 30", "US"),
    "RUT":    ("^RUT", "Russell 2000", "US"),
    "VIX":    ("^VIX", "CBOE Volatility Index", "US"),
    "NYA":    ("^NYA", "NYSE Composite", "US"),
    "FTSE":   ("^FTSE", "FTSE 100", "Europe"),
    "DAX":    ("^GDAXI", "DAX 40", "Europe"),
    "CAC":    ("^FCHI", "CAC 40", "Europe"),
    "STOXX50": ("^STOXX50E", "Euro Stoxx 50", "Europe"),
    "AEX":    ("^AEX", "AEX Amsterdam", "Europe"),
    "IBEX":   ("^IBEX", "IBEX 35", "Europe"),
    "SMI":    ("^SSMI", "Swiss Market Index", "Europe"),
    "FTSEMIB": ("FTSEMIB.MI", "FTSE MIB", "Europe"),
    "N225":   ("^N225", "Nikkei 225", "Asia"),
    "HSI":    ("^HSI", "Hang Seng", "Asia"),
    "SENSEX": ("^BSESN", "BSE Sensex", "Asia"),
    "NIFTY":  ("^NSEI", "Nifty 50", "Asia"),
    "KOSPI":  ("^KS11", "KOSPI", "Asia"),
    "TWII":   ("^TWII", "Taiwan Weighted", "Asia"),
    "STI":    ("^STI", "Straits Times", "Asia"),
    "JKSE":   ("^JKSE", "Jakarta Composite", "Asia"),
    "AXJO":   ("^AXJO", "ASX 200", "Pacific"),
    "NZ50":   ("^NZ50", "NZX 50", "Pacific"),
    "TSX":    ("^GSPTSE", "S&P/TSX Composite", "Americas"),
    "BVSP":   ("^BVSP", "Bovespa", "Americas"),
    "MXX":    ("^MXX", "IPC Mexico", "Americas"),
}

# --------------------------------------------------------------------------------------
# RATES & CREDIT — the govvy curve plus credit spreads. Trend-followers' best crisis hedge.
# --------------------------------------------------------------------------------------
_RATES: dict[str, tuple[str, str, str]] = {
    "US30Y":  ("ZB=F", "30-Year T-Bond future", "govt"),
    "US10Y":  ("ZN=F", "10-Year T-Note future", "govt"),
    "US5Y":   ("ZF=F", "5-Year T-Note future", "govt"),
    "US2Y":   ("ZT=F", "2-Year T-Note future", "govt"),
    "UST20+": ("TLT", "20+ Year Treasury ETF", "govt"),
    "UST7-10": ("IEF", "7-10 Year Treasury ETF", "govt"),
    "UST1-3": ("SHY", "1-3 Year Treasury ETF", "govt"),
    "TBILL":  ("BIL", "1-3 Month T-Bill ETF", "govt"),
    "AGG":    ("AGG", "US Aggregate Bond ETF", "broad"),
    "IG":     ("LQD", "Investment Grade Credit ETF", "credit"),
    "HY":     ("HYG", "High Yield Credit ETF", "credit"),
    "EMDEBT": ("EMB", "EM Sovereign Debt ETF", "credit"),
    "TIPS":   ("TIP", "Inflation-Protected ETF", "inflation"),
    "MUNI":   ("MUB", "Municipal Bond ETF", "credit"),
    "US10Y/YLD": ("^TNX", "US 10-Year yield", "yield"),
    "US5Y/YLD":  ("^FVX", "US 5-Year yield", "yield"),
    "US30Y/YLD": ("^TYX", "US 30-Year yield", "yield"),
    "US13W/YLD": ("^IRX", "US 13-Week yield", "yield"),
}


# --------------------------------------------------------------------------------------
# ALLOCATABLE vs CONTEXT-ONLY — the distinction that keeps backtests honest.
#
# Not every price series is a thing you can own, and a momentum ranker cannot tell the
# difference on its own. Measured here on 2026-08-02: running the allocation model over the
# raw universe produced +310% with rates "returning" +227%. Both were fake.
#
#   YIELD INDICES (^TNX, ^IRX, ...) are not instruments. ^IRX went 0.068 -> 3.68 as the Fed
#   hiked, which a momentum ranker reads as +5,314% and buys with both hands. You cannot buy
#   a yield. Bond FUTURES and bond ETFs are the tradable expression, and they move the OTHER
#   WAY — which is precisely why leaving the yield in poisoned the result.
#
#   HIGH-CARRY FX is the same illusion in a different costume. The model's favourite holdings
#   were USD/ARS (+1,531%), USD/TRY, GBP/TRY, USD/NGN, USD/EGP — currencies that only ever
#   devalue. The spot move is real, but an FX position also pays the interest differential,
#   and for these that differential IS the move: Argentina's policy rate ran north of 100%,
#   Turkey's near 50%. Long USD/ARS earns the ramp and pays it straight back out in carry,
#   before capital controls make the quoted rate unreachable anyway. Spot-only FX momentum is
#   only honest where the rate differential is small enough not to swamp the trend, i.e. G10.
#
#   VIX is not investable either — spot VIX has no holder; VXX and friends bleed roll yield.
#
# Everything below stays VISIBLE for analytics, regime and correlation work. It is barred from
# the allocation model only, with the reason attached so the exclusion is auditable.
# --------------------------------------------------------------------------------------
_G10 = {"USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "SEK", "NOK"}
_NOT_ALLOCATABLE = {
    "US10Y/YLD": "a yield index, not an instrument — buy the bond future/ETF instead",
    "US5Y/YLD": "a yield index, not an instrument — buy the bond future/ETF instead",
    "US30Y/YLD": "a yield index, not an instrument — buy the bond future/ETF instead",
    "US13W/YLD": "a yield index, not an instrument — buy the bond future/ETF instead",
    "VIX": "spot VIX has no holder; VIX ETPs bleed roll yield and do not track it",
}


def _fx_allocatable(sym: str) -> tuple[bool, str]:
    """G10 crosses only. Outside G10 the carry swamps the trend (see the note above)."""
    base, _, quote = sym.partition("/")
    if base in _G10 and quote in _G10:
        return True, ""
    return False, ("spot momentum here is a carry illusion — the interest differential offsets "
                   "the devaluation, and capital controls often bar the quoted rate")


def _fx_yahoo(sym: str) -> str:
    """'EUR/USD' -> 'EURUSD=X'."""
    return sym.replace("/", "") + "=X"


# Canonical -> provider routing, built once at import.
_CATALOG: dict[str, dict] = {}

for _grp, _list in (("major", _FX_MAJORS), ("cross", _FX_CROSSES), ("exotic", _FX_EXOTICS)):
    for _s in _list:
        _alloc, _why = _fx_allocatable(_s)
        _CATALOG[_s] = {"symbol": _s, "category": "forex", "group": _grp,
                        "name": _s, "provider": "yahoo", "provider_symbol": _fx_yahoo(_s),
                        "allocatable": _alloc, "note": _why}
for _src, _cat in ((_COMMODITIES, "commodities"), (_INDICES, "indices"), (_RATES, "rates")):
    for _s, (_y, _n, _g) in _src.items():
        _why = _NOT_ALLOCATABLE.get(_s, "")
        _CATALOG[_s] = {"symbol": _s, "category": _cat, "group": _g,
                        "name": _n, "provider": "yahoo", "provider_symbol": _y,
                        "allocatable": not _why, "note": _why}

# --------------------------------------------------------------------------------------
# CRYPTO — resolved live from Binance so the list follows real liquidity instead of a
# hand-written snapshot that rots. Cached for a day; falls back to a static core if the
# venue is unreachable (Binance geo-blocks some cloud IPs).
# --------------------------------------------------------------------------------------
_CRYPTO_CORE = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
    "LINKUSDT", "LTCUSDT", "DOTUSDT", "TRXUSDT", "ATOMUSDT", "UNIUSDT", "NEARUSDT", "APTUSDT",
    "ARBUSDT", "OPUSDT", "FILUSDT", "INJUSDT", "SUIUSDT", "SEIUSDT", "TIAUSDT", "AAVEUSDT",
    "ETCUSDT", "XLMUSDT", "RUNEUSDT", "GRTUSDT",
]
# Stablecoins and wrapped/duplicate tickers: a "pair" that is pegged 1:1 has no trend to follow
# and would pollute a momentum ranking with meaningless ~0% readings.
_CRYPTO_EXCLUDE_BASES = {
    "USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "USD1", "EUR", "GBP", "AEUR", "TRY", "BRL",
    "ARS", "JPY", "PLN", "RON", "ZAR", "COP", "MXN", "CZK", "UAH", "IDRT", "NGN", "VAI", "USDS",
    "WBTC", "WBETH", "BETH", "USDE", "SUSDE", "XUSD", "BFUSD", "USTC", "PAXG", "XAUT",
}
# Liquidity floors are per-HOLDING-PERIOD, because the same spread is a different problem at
# different horizons. A 15-minute flash trade pays the round trip against a ~0.3% move; a
# six-month allocation pays it once against a 30% move. So the fast consumers demand deep books
# and the slow ones can afford breadth. Binance lists ~620 non-stable USDT pairs; these floors
# admit 144 / 46 / 26 of them respectively.
MIN_VOLUME_HOLD = 1_000_000.0    # allocation model — months; cost amortises away
MIN_VOLUME_SCAN = 5_000_000.0    # core scanner — 1h/4h swings
MIN_VOLUME_FLASH = 10_000_000.0  # flash bot — 15m; needs depth or the spread IS the trade
_CRYPTO_MIN_VOLUME = MIN_VOLUME_HOLD
_crypto_cache: tuple[float, list[dict]] | None = None
_crypto_lock = threading.Lock()


def crypto_universe(limit: int = 150, min_volume: float = _CRYPTO_MIN_VOLUME) -> list[dict]:
    """Live Binance USDT spot pairs ranked by 24h quote volume, liquidity-filtered.

    Volume is the filter that matters: the cost model charges spread + fees per round trip, and on
    a thin pair that cost is a large fraction of the move being traded. Ranking by dollar volume
    keeps the universe wide without letting in pairs where the edge cannot survive the friction.
    """
    global _crypto_cache
    now = time.time()
    with _crypto_lock:
        if _crypto_cache and now - _crypto_cache[0] < 86400:
            cached = _crypto_cache[1]
            return [c for c in cached if c["quote_volume"] >= min_volume][:limit]

    rows: list[dict] = []
    try:
        import httpx
        resp = httpx.get("https://api.binance.com/api/v3/ticker/24hr", timeout=45.0)
        resp.raise_for_status()
        for t in resp.json():
            sym = t.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            base = sym[:-4]
            if base in _CRYPTO_EXCLUDE_BASES or base.endswith(("UP", "DOWN", "BULL", "BEAR")):
                continue
            try:
                qv = float(t.get("quoteVolume") or 0.0)
                last = float(t.get("lastPrice") or 0.0)
                chg = float(t.get("priceChangePercent") or 0.0)
            except (TypeError, ValueError):
                continue
            if qv <= 0 or last <= 0:
                continue
            rows.append({"symbol": sym, "category": "crypto", "group": "spot", "name": base,
                         "provider": "binance", "provider_symbol": sym, "allocatable": True,
                         "note": "", "quote_volume": qv, "price": last, "change_pct": chg})
    except Exception:
        rows = []

    if not rows:   # venue unreachable — keep the system usable on the proven core
        rows = [{"symbol": s, "category": "crypto", "group": "spot", "name": s[:-4],
                 "provider": "binance", "provider_symbol": s, "allocatable": True, "note": "",
                 "quote_volume": 0.0, "price": 0.0, "change_pct": 0.0} for s in _CRYPTO_CORE]

    rows.sort(key=lambda r: r["quote_volume"], reverse=True)
    with _crypto_lock:
        _crypto_cache = (now, rows)
    return [r for r in rows if r["quote_volume"] >= min_volume][:limit]


def catalog(categories: list[str] | None = None, crypto_limit: int = 150,
            allocatable_only: bool = False, min_volume: float | None = None) -> list[dict]:
    """Every instrument the system can see.

    `allocatable_only` drops the series that are visible but not ownable — yield indices, spot
    VIX, and non-G10 FX where carry eats the trend. Anything that ranks instruments by return
    MUST pass True here, or it will happily "buy" a yield.
    """
    wanted = set(categories) if categories else None
    out = [dict(v) for v in _CATALOG.values() if wanted is None or v["category"] in wanted]
    if wanted is None or "crypto" in wanted:
        out = crypto_universe(crypto_limit, min_volume if min_volume is not None
                              else _CRYPTO_MIN_VOLUME) + out
    if allocatable_only:
        out = [c for c in out if c.get("allocatable", True)]
    return out


def resolve(symbol: str) -> dict | None:
    """Canonical symbol -> routing entry. Crypto resolves by convention, not by table."""
    hit = _CATALOG.get(symbol) or _CATALOG.get(symbol.upper())
    if hit:
        return dict(hit)
    up = symbol.upper()
    if up.endswith("USDT"):     # any Binance pair, listed or not
        return {"symbol": up, "category": "crypto", "group": "spot", "name": up[:-4],
                "provider": "binance", "provider_symbol": up, "allocatable": True, "note": ""}
    return None


def fetch(symbol: str, interval: str = "1d", limit: int = 500) -> pd.DataFrame:
    """Fetch OHLCV for ANY catalog symbol, routed to whichever provider serves it.

    This is the single entry point that makes the rest of the engine asset-class agnostic: the
    same indicator stack, the same cost model and the same allocator run on gold, the yen and
    Bitcoin without knowing which is which.
    """
    entry = resolve(symbol)
    if entry is None:
        raise ValueError(f"Unknown symbol '{symbol}' — not in the universe")
    if entry["provider"] == "binance":
        from .data.binance import fetch_klines_history as _binance
        return _binance(entry["provider_symbol"], interval, limit)
    from .data.yahoo import fetch_klines as _yahoo
    return _yahoo(entry["provider_symbol"], interval, limit)


def counts(crypto_limit: int = 150) -> dict:
    """Per-category instrument counts, plus how many of each are actually allocatable."""
    out: dict[str, dict] = {}
    for item in catalog(crypto_limit=crypto_limit):
        cat = out.setdefault(item["category"], {"total": 0, "allocatable": 0})
        cat["total"] += 1
        cat["allocatable"] += 1 if item.get("allocatable", True) else 0
    return {"by_category": out,
            "total": sum(c["total"] for c in out.values()),
            "allocatable": sum(c["allocatable"] for c in out.values())}
