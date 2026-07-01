"""FastAPI app — Phase 0 foundations + Phase 1b reasoning.

Endpoints:
  GET  /health                       -> liveness
  GET  /signal/{symbol}              -> deterministic factor score + trade levels
  GET  /signal/{symbol}/explain      -> same, plus an LLM-written (or fallback) rationale
  POST /webhook/tradingview          -> token-verified stub for Pine alerts (Phase 3)
"""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__, db, learning, performance, persistence, resolver, scanner
from .config import settings
from .llm import build_rationale, run_debate
from .signal_service import compute_signal, get_candles

logger = logging.getLogger("cockpit.resolver")
_scheduler = BackgroundScheduler(daemon=True)


def _resolver_job() -> None:
    try:
        summary = resolver.resolve_open_signals()
        if summary.get("resolved"):
            logger.info("resolver: %s", summary)
    except Exception:  # noqa: BLE001 - a scheduled job must never crash the loop
        logger.exception("resolver job failed")


def _scanner_job() -> None:
    try:
        summary = scanner.scan_once()
        if summary.get("emitted"):
            logger.info("scanner emitted %s signal(s)", summary["emitted"])
    except Exception:  # noqa: BLE001
        logger.exception("scanner job failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the auto-outcome resolver only when persistence is on.
    if settings.resolver_enabled and db.enabled():
        _scheduler.add_job(
            _resolver_job, "interval", minutes=settings.resolver_interval_minutes,
            id="resolver", replace_existing=True, max_instances=1,
        )
        # Weekly champion/challenger retrain (no-ops safely until enough outcomes exist).
        _scheduler.add_job(
            lambda: learning.train_and_gate(), "interval", weeks=1,
            id="retrain", replace_existing=True, max_instances=1,
        )
        # Autonomous scanner: find + give signals across popular pairs.
        if settings.scanner_enabled:
            _scheduler.add_job(
                _scanner_job, "interval", minutes=settings.scanner_interval_minutes,
                id="scanner", replace_existing=True, max_instances=1,
            )
        learning.refresh()
        _scheduler.start()
        logger.info(
            "scheduler up: resolver %smin, scanner %smin, weekly retrain",
            settings.resolver_interval_minutes, settings.scanner_interval_minutes,
        )
    try:
        yield
    finally:
        if _scheduler.running:
            _scheduler.shutdown(wait=False)


app = FastAPI(title="Universal Signal Cockpit", version=__version__, lifespan=lifespan)

# Allow the Next.js cockpit to call the API. Set CORS_ORIGINS to your Vercel URL in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "env": settings.app_env}


# symbol is a query param (not a path param) because forex symbols contain '/'
# (e.g. EUR/USD), which servers decode in the path and mis-route.


@app.get("/signal")
def signal(
    symbol: str = Query(..., min_length=1),
    interval: str = Query("1h"),
    market: str = Query("crypto"),
    limit: int = Query(500, ge=210, le=1000),
    with_flow: bool = Query(True),
) -> dict:
    return compute_signal(symbol, interval, market=market, limit=limit, with_flow=with_flow)


@app.get("/explain")
def signal_explain(
    symbol: str = Query(..., min_length=1),
    interval: str = Query("1h"),
    market: str = Query("crypto"),
    limit: int = Query(500, ge=210, le=1000),
    with_flow: bool = Query(True),
) -> dict:
    sig = compute_signal(symbol, interval, market=market, limit=limit, with_flow=with_flow)
    sig["explanation"] = build_rationale(sig)
    return sig


@app.get("/decision")
def decision(
    symbol: str = Query(..., min_length=1),
    interval: str = Query("4h"),
    market: str = Query("crypto"),
    limit: int = Query(500, ge=210, le=1000),
) -> dict:
    """Full pipeline: deterministic signal -> Bull/Bear/Risk-Manager debate -> final conviction.

    The headline label stays the deterministic one (numbers are the anchor). The debate sets the
    final conviction and flags whether the AI agrees with the model.
    """
    sig = compute_signal(symbol, interval, market=market, limit=limit)
    sig["explanation"] = build_rationale(sig)
    debate = run_debate(sig)

    # Blend: deterministic confidence and the risk manager's conviction, nudged down on disagreement.
    penalty = {"agree": 1.0, "caution": 0.85, "disagree": 0.6}.get(debate["agreement"], 0.85)
    final_conf = round(min(100.0, (0.5 * sig["confidence"] + 0.5 * debate["conviction"]) * penalty), 1)
    sig["debate"] = debate
    sig["final"] = {
        "label": sig["label"],
        "agreement": debate["agreement"],
        "conviction": debate["conviction"],
        "final_confidence": final_conf,
    }
    # Best-effort persistence: returns an id when the DB is configured, else None.
    sig["signal_id"] = persistence.log_decision(sig)
    return sig


@app.get("/candles")
def candles(
    symbol: str = Query(..., min_length=1),
    interval: str = Query("4h"),
    market: str = Query("crypto"),
    limit: int = Query(300, ge=60, le=1000),
) -> dict:
    return get_candles(symbol, interval, market=market, limit=limit)


@app.get("/db/status")
def db_status() -> dict:
    """Whether persistence is configured and reachable."""
    return {"enabled": db.enabled(), "reachable": db.ping()}


@app.get("/signals/recent")
def signals_recent(limit: int = Query(20, ge=1, le=200)) -> dict:
    return {"signals": persistence.recent_signals(limit)}


@app.get("/stats")
def stats() -> dict:
    """Learning-loop scoreboard: hit-rate + avg P&L over resolved outcomes."""
    return persistence.accuracy_stats()


@app.get("/performance")
def performance_report(trade_size: float = Query(1000.0, ge=1.0, le=1_000_000.0)) -> dict:
    """Fixed-notional paper-trading P&L: per-asset + combined, realized + floating."""
    return performance.performance(trade_size=trade_size)


@app.post("/resolve")
def resolve_now(max_signals: int = Query(50, ge=1, le=500)) -> dict:
    """Manually trigger the auto-outcome resolver (also runs on a schedule)."""
    return resolver.resolve_open_signals(max_signals=max_signals)


@app.post("/scan")
def scan_now(min_confidence: float | None = Query(None, ge=0, le=100)) -> dict:
    """Autonomously sweep popular pairs and log actionable signals (also runs on a schedule)."""
    return scanner.scan_once(min_confidence=min_confidence)


@app.get("/learning/status")
def learning_status() -> dict:
    """Champion weight profiles + resolved-outcome counts per regime."""
    return learning.learning_status()


@app.post("/learning/train")
def learning_train() -> dict:
    """Train challenger weights per regime and promote any that beat the champion (gated)."""
    return learning.train_and_gate()


class OutcomeIn(BaseModel):
    signal_id: int
    result: str  # 'target' | 'stop' | 'timeout' | 'manual'
    pnl: float | None = None
    mfe: float | None = None
    mae: float | None = None
    bars_held: int | None = None


@app.post("/outcome")
def record_outcome(payload: OutcomeIn) -> dict:
    """Label a stored signal with what actually happened — fuel for the learning loop."""
    if not db.enabled():
        raise HTTPException(status_code=409, detail="persistence not configured")
    ok = persistence.record_outcome(
        payload.signal_id, payload.result,
        pnl=payload.pnl, mfe=payload.mfe, mae=payload.mae, bars_held=payload.bars_held,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="failed to record outcome")
    return {"recorded": True, "signal_id": payload.signal_id}


class TradingViewAlert(BaseModel):
    token: str
    ticker: str
    action: str
    price: float | None = None
    timeframe: str | None = None


@app.post("/webhook/tradingview")
def tradingview_webhook(payload: TradingViewAlert, x_signature: str | None = Header(default=None)) -> dict:
    """Stub: verify the shared secret, acknowledge. Full pipeline wired in Phase 3."""
    if not hmac.compare_digest(payload.token, settings.tradingview_webhook_secret):
        raise HTTPException(status_code=401, detail="invalid webhook token")
    return {
        "received": True,
        "ticker": payload.ticker.upper(),
        "action": payload.action,
        "note": "stub - factor engine + rationale wiring lands in Phase 3",
    }
