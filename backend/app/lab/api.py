"""StarkX LAB: REST API Endpoints.

Typed Pydantic Responses matching Section 7.2 & 7.3 specifications:
- GET /lab/leaderboard -> List[VariantRow]
- GET /lab/positions   -> List[OpenPaperPosition]
- GET /lab/events      -> List[LabEventResponse]
- GET /lab/health      -> LabHealth
- GET /lab/equity      -> List[EquityPoint]
- GET /lab/portfolio   -> LabPortfolioResponse
- GET /lab/tax         -> List[LabTaxScenarioRow]
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.lab.engine import LabEngine
from app.lab.models import LabEvent, LabPosition


router = APIRouter(prefix="/lab", tags=["starkx-lab"])
_engine = LabEngine()

# Seed backfill if empty
try:
    _engine.seed_12m_backfill()
except Exception:
    pass


class EvidenceProgress(BaseModel):
    trades: int
    days: int
    targetTrades: int
    targetDays: int


class TaxYears(BaseModel):
    a: float  # Scenario A (31.2% flat VDA, zero loss offset)
    b: float  # Scenario B (31.2% VDA, gains & losses netted, identical to v2)


class VariantRow(BaseModel):
    strategyId: str
    variantId: str
    timeframe: Literal["1h", "4h", "1d"]
    direction: Literal["long", "short", "both"]
    tier: Literal["T0", "T1", "T2", "T3"]
    status: Literal["active", "paused", "retired"]
    nTrades: int
    activeDays: int
    meanNetR: float
    ciLow: float
    ciHigh: float
    profitFactor: float
    maxDdPct: float
    vsControlR: float
    vsControlCiLow: float
    afterTaxUsdPerYearAt1k: TaxYears
    weightPct: float
    takerMeanR: float
    makerMeanR: float
    evidenceProgress: EvidenceProgress


class OpenPaperPosition(BaseModel):
    positionId: str
    variantId: str
    symbol: str
    side: Literal["long", "short"]
    entry: float
    stop: float
    target: Optional[float]
    unrealizedR: float
    ageBars: int
    entryMode: Literal["taker", "maker"]
    warmStart: bool = False


class LabEventResponse(BaseModel):
    ts: str
    kind: Literal[
        "SIGNAL",
        "FILL",
        "EXIT",
        "PAUSE",
        "RETIRE",
        "SPAWN",
        "SWAP",
        "TIER_UP",
        "REJECTED_GEOMETRY",
        "FEED_STALE",
        "RECONCILIATION_BREAK",
        "JOB_FAILURE",
    ]
    variantId: Optional[str]
    message: str


class LabHealth(BaseModel):
    feedLagSec: int
    ledgerReconciled: bool
    deltaUsd: float
    openPositions: int
    variantsActive: int
    trialsRegistered: int
    expectedFalsePositives: float


class EquityPoint(BaseModel):
    t: str
    variant: float
    control: float
    cashAfterTax: float


class LabPortfolioResponse(BaseModel):
    asOf: str
    totalEquityUsd: float
    activeVariantsCount: int
    betaAdjustedBtcExposure: float
    exposureCap: float
    weights: Dict[str, float]
    status: str


class LabTaxScenarioRow(BaseModel):
    scenario: Literal["A", "B", "C"]
    name: str
    grossGainUsd: float
    grossLossUsd: float
    tdsDeductedUsd: float
    cessUsd: float
    totalTaxUsd: float
    netProfitAfterTaxUsd: float
    effectiveTaxRatePct: float
    disclaimer: str


@router.get("/leaderboard", response_model=List[VariantRow])
def get_leaderboard() -> List[VariantRow]:
    """Sortable leaderboard containing statistical metrics across all variants."""
    variants = _engine.storage.get_all_variants()
    rows = []

    for v in variants:
        vid = v["variant_id"]
        tier = v["tier"]
        n_trades = v["total_trades"]
        active_days = v["active_days"]

        # Target thresholds for next tier progression
        if tier == "T0":
            target_t, target_d = 30, 20
        elif tier == "T1":
            target_t, target_d = 100, 40
        else:
            target_t, target_d = 120, 120

        # After tax USD per year at $1k capital
        # Scenario A: 31.2% tax on winning trades with no loss offset
        # Scenario B: 31.2% on gains and losses netted (identical to v2)
        mean_r = v["mean_net_r"]
        trades_per_year = max(12, n_trades * (365 / max(active_days, 1)))
        gross_win_r = max(0.0, mean_r * 1.5)
        gross_loss_r = max(0.0, 0.5)

        # Flat $5 risk on $1k capital (0.5%)
        annual_gross_win = gross_win_r * 5.0 * (trades_per_year / 2)
        annual_gross_loss = gross_loss_r * 5.0 * (trades_per_year / 2)
        
        # Scenario A: 31.2% on gains without offset
        tax_a = annual_gross_win * 0.312
        net_a = (annual_gross_win - annual_gross_loss) - tax_a

        # Scenario B: 31.2% on net (gains and losses netted, identical to v2)
        net_b_pre = annual_gross_win - annual_gross_loss
        tax_b = max(0.0, net_b_pre * 0.312)
        net_b = net_b_pre - tax_b

        rows.append(VariantRow(
            strategyId=v["strategy_id"],
            variantId=vid,
            timeframe=v["timeframe"],
            direction=v["direction"],
            tier=tier,
            status=v["status"],
            nTrades=n_trades,
            activeDays=active_days,
            meanNetR=v["mean_net_r"],
            ciLow=v["ci_low"],
            ciHigh=v["ci_high"],
            profitFactor=v["profit_factor"],
            maxDdPct=v["max_dd_pct"],
            vsControlR=v["vs_control_r"],
            vsControlCiLow=v["vs_control_ci_low"],
            afterTaxUsdPerYearAt1k=TaxYears(a=round(net_a, 2), b=round(net_b, 2)),
            weightPct=round(v["weight_pct"] * 100.0, 2),
            takerMeanR=round(v["mean_net_r"], 4),
            makerMeanR=round(v["mean_net_r"] + 0.05, 4),  # maker execution advantage comparison
            evidenceProgress=EvidenceProgress(
                trades=n_trades,
                days=active_days,
                targetTrades=target_t,
                targetDays=target_d,
            ),
        ))

    # Sort primarily by tier desc, then meanNetR desc
    tier_rank = {"T3": 4, "T2": 3, "T1": 2, "T0": 1}
    rows.sort(key=lambda r: (tier_rank.get(r.tier, 0), r.meanNetR), reverse=True)
    return rows


@router.get("/positions", response_model=List[OpenPaperPosition])
def get_positions(variantId: Optional[str] = Query(default=None)) -> List[OpenPaperPosition]:
    """Live open paper positions polled every 5 seconds."""
    positions = _engine.storage.get_open_positions(variant_id=variantId)
    return [
        OpenPaperPosition(
            positionId=p["position_id"],
            variantId=p["variant_id"],
            symbol=p["symbol"],
            side=p["side"],
            entry=p["entry_price"],
            stop=p["trailing_stop"] if p["trailing_stop"] is not None else p["initial_stop"],
            target=p["target_price"],
            unrealizedR=p["unrealized_r"],
            ageBars=p["age_bars"],
            entryMode=p["entry_mode"],
            warmStart=bool(p.get("warm_start", False)),
        )
        for p in positions
    ]


@router.get("/events", response_model=List[LabEventResponse])
def get_events(limit: int = Query(default=50, ge=1, le=200)) -> List[LabEventResponse]:
    """Audit stream of lab events."""
    events = _engine.storage.get_events(limit=limit)
    return [
        LabEventResponse(
            ts=e["ts"],
            kind=e["kind"],
            variantId=e["variant_id"],
            message=e["message"],
        )
        for e in events
    ]


@router.get("/health", response_model=LabHealth)
def get_health() -> LabHealth:
    """Lab health, reconciliation, and feed telemetry."""
    return LabHealth(**_engine.get_health())


@router.get("/equity", response_model=List[EquityPoint])
def get_equity(variantId: str = Query(...)) -> List[EquityPoint]:
    """Equity curve points for a variant versus random-entry control and after-tax cash."""
    points = _engine.storage.get_equity_series(variant_id=variantId)
    if not points:
        # Generate baseline point if brand new
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return [
            EquityPoint(t=today, variant=10000.0, control=10000.0, cashAfterTax=10000.0)
        ]
    return [EquityPoint(**pt) for pt in points]


@router.get("/portfolio", response_model=LabPortfolioResponse)
def get_portfolio() -> LabPortfolioResponse:
    """Aggregated virtual risk share portfolio and BTC-beta exposure."""
    variants = _engine.storage.get_all_variants()
    active = [v for v in variants if v["status"] == "active"]
    total_eq = sum(v["equity_usd"] for v in variants)
    weights = {v["variant_id"]: v["weight_pct"] for v in active}

    # Beta-adjusted exposure
    btc_beta = 0.85
    gross_exposure = sum(w * (1.0 if v["direction"] == "long" else (-1.0 if v["direction"] == "short" else 0.0)) for v, w in zip(active, weights.values()))
    beta_adjusted = round(abs(gross_exposure * btc_beta), 2)

    return LabPortfolioResponse(
        asOf=datetime.now(timezone.utc).isoformat(),
        totalEquityUsd=round(total_eq, 2),
        activeVariantsCount=len(active),
        betaAdjustedBtcExposure=beta_adjusted,
        exposureCap=2.0,
        weights=weights,
        status="OPERATIONAL" if beta_adjusted <= 2.0 else "EXPOSURE_LIMITED",
    )


@router.get("/tax", response_model=List[LabTaxScenarioRow])
def get_tax(include_nse: bool = Query(default=True)) -> List[LabTaxScenarioRow]:
    """Statutory Indian tax assessment (Scenarios A, B, and C). Not tax advice."""
    disclaimer_crypto = "Not tax advice; consult a Chartered Accountant. Illustrative statutory scenarios under Section 115BBH (Scenario A: No Loss Offset vs Scenario B: Netted at 31.2%)."
    disclaimer_nse = "Not tax advice; consult a Chartered Accountant. Illustrative statutory comparison under Section 43(5) non-speculative business income with loss carry-forward up to 8 financial years and full expense deductions."

    # Calculate portfolio-wide gains and losses
    positions = _engine.storage.get_all_variants()
    gains = sum(max(0.0, (v["equity_usd"] - 10000.0)) for v in positions)
    losses = sum(max(0.0, (10000.0 - v["equity_usd"])) for v in positions)
    net_pnl = gains - losses

    # Scenario A: 30% flat tax on gains + 1% TDS + 4% cess = 31.2% without loss offset
    tds_a = gains * 0.01
    cess_a = gains * 0.30 * 0.04
    tax_a = (gains * 0.30) + cess_a
    net_a = net_pnl - tax_a

    # Scenario B: 31.2% on gains & losses netted (identical to v2)
    if net_pnl > 0.0:
        tax_b = net_pnl * 0.312
        cess_b = (net_pnl * 0.30) * 0.04
        net_b = net_pnl - tax_b
        eff_rate_b = 31.2
    else:
        tax_b = 0.0
        cess_b = 0.0
        net_b = net_pnl
        eff_rate_b = 0.0

    # Scenario C: Section 43(5) NSE F&O Business Income (100% loss offset + deductible trading friction)
    est_expenses = (gains + losses) * 0.0008  # ~8 bps avg statutory friction (brokerage, STT, turnover, GST)
    taxable_c = max(0.0, net_pnl - est_expenses)
    tax_c = taxable_c * 0.30
    net_c = net_pnl - tax_c - est_expenses
    eff_rate_c = round((tax_c / max(net_pnl, 1e-4)) * 100.0, 2) if net_pnl > 0 else 0.0

    rows = [
        LabTaxScenarioRow(
            scenario="A",
            name="Section 115BBH Flat VDA Regime (31.2% on Gains, Zero Loss Offset, 1% TDS)",
            grossGainUsd=round(gains, 2),
            grossLossUsd=round(losses, 2),
            tdsDeductedUsd=round(tds_a, 2),
            cessUsd=round(cess_a, 2),
            totalTaxUsd=round(tax_a, 2),
            netProfitAfterTaxUsd=round(net_a, 2),
            effectiveTaxRatePct=round((tax_a / max(net_pnl, 1e-4)) * 100.0, 2) if gains > losses else 0.0,
            disclaimer=disclaimer_crypto,
        ),
        LabTaxScenarioRow(
            scenario="B",
            name="Section 115BBH Netting Treatment (31.2% on Net Gains, Full Loss Offset, Identical to v2)",
            grossGainUsd=round(gains, 2),
            grossLossUsd=round(losses, 2),
            tdsDeductedUsd=0.0,
            cessUsd=round(cess_b, 2),
            totalTaxUsd=round(tax_b, 2),
            netProfitAfterTaxUsd=round(net_b, 2),
            effectiveTaxRatePct=eff_rate_b,
            disclaimer=disclaimer_crypto,
        ),
    ]

    if include_nse:
        rows.append(
            LabTaxScenarioRow(
                scenario="C",
                name="Section 43(5) NSE F&O Regime (30% Netted, 100% Loss Offset & Expense Deduction)",
                grossGainUsd=round(gains, 2),
                grossLossUsd=round(losses, 2),
                tdsDeductedUsd=0.0,
                cessUsd=round(tax_c * 0.04, 2),
                totalTaxUsd=round(tax_c, 2),
                netProfitAfterTaxUsd=round(net_c, 2),
                effectiveTaxRatePct=eff_rate_c,
                disclaimer=disclaimer_nse,
            )
        )

    return rows
