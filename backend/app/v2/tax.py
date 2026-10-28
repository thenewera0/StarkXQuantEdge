"""StarkX QuantEdge v2: Tax & Statutory Compliance Engine.

Rules and Statutory Citations:
- Rule 0.5: Honest labelling: show "net of costs, after-tax scenario A/B, versus cash and buy-and-hold" next to every return.
- Rule 0.6: Every tax figure is a labelled scenario and carries the banner "Not tax advice; consult a CA".
- Section 6: FIFO lot ledger per asset; every disposal (to cash, to stablecoin, or crypto-to-crypto)
  is a transfer event.
  - Scenario A: 31.2% flat tax on each positive disposal gain, NO loss offset.
  - Scenario B: 31.2% tax with gains and losses netted per Financial Year (Apr 1 - Mar 31).
  - TDS ledger: 1% Section 194S transfer value withholding as a cash-flow credit, self-deducted flag.
  - GST: 18% on platform fees.
  - CA CSV export formatting.
  - Order-level estimated tax cost preview.
"""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.v2.config import settings_v2


MANDATORY_TAX_DISCLAIMER = "Not tax advice; consult a CA"


def get_financial_year(dt: datetime | date | str) -> str:
    """Returns the Indian Financial Year string (e.g., 'FY2025-26') for a date.
    
    Indian FY runs from April 1 to March 31.
    """
    if isinstance(dt, str):
        # Parse ISO or date string
        dt = pd.to_datetime(dt).date()
    elif isinstance(dt, datetime):
        dt = dt.date()

    year = dt.year
    if dt.month >= 4:
        next_yr_short = str(year + 1)[-2:]
        return f"FY{year}-{next_yr_short}"
    else:
        prev_yr = year - 1
        curr_yr_short = str(year)[-2:]
        return f"FY{prev_yr}-{curr_yr_short}"


@dataclass
class TaxLot:
    lot_id: str
    asset: str
    acquired_at: str  # ISO timestamp
    quantity: float
    remaining_quantity: float
    unit_cost_usd: float
    total_cost_usd: float
    fee_paid_usd: float = 0.0
    gst_paid_usd: float = 0.0


@dataclass
class DisposalEvent:
    disposal_id: str
    lot_id: str
    disposal_date: str
    financial_year: str
    asset: str
    quantity: float
    unit_cost_usd: float
    unit_proceeds_usd: float
    total_cost_usd: float
    total_proceeds_usd: float
    gross_gain_usd: float  # total_proceeds - total_cost
    scenario_a_taxable_usd: float  # max(0, gross_gain_usd)
    scenario_a_tax_usd: float  # 31.2% on positive gain only
    scenario_b_taxable_usd: float  # gross_gain_usd (netted across FY)
    tds_withheld_usd: float  # 1% of total_proceeds_usd
    self_deducted: bool = True
    fee_usd: float = 0.0
    gst_fee_usd: float = 0.0
    counter_asset: Optional[str] = "USD"


@dataclass
class FinancialYearSummary:
    financial_year: str
    disposal_count: int
    gross_proceeds_usd: float
    total_cost_basis_usd: float
    net_realized_pnl_usd: float
    scenario_a_tax_usd: float
    scenario_b_tax_usd: float
    tds_credits_usd: float
    total_gst_fees_usd: float
    after_tax_pnl_scenario_a_usd: float
    after_tax_pnl_scenario_b_usd: float
    disclaimer: str = MANDATORY_TAX_DISCLAIMER


class TaxLedger:
    """FIFO Lot Ledger and Statutory Tax Assessment Engine."""

    def __init__(self, tax_rules_path: Optional[str] = None):
        self.rules = self._load_rules(tax_rules_path)
        self.effective_tax_rate = self.rules.get("rates", {}).get("effective_vda_tax_rate", settings_v2.tax_rate)
        self.tds_rate = self.rules.get("rates", {}).get("tds_rate", settings_v2.tds_rate)
        self.gst_rate = self.rules.get("rates", {}).get("gst_rate", settings_v2.gst_rate)
        
        # Open lots keyed by asset -> list of TaxLot (sorted by acquired_at ascending)
        self.open_lots: Dict[str, List[TaxLot]] = {}
        # Completed disposals
        self.disposals: List[DisposalEvent] = []

    def _load_rules(self, path: Optional[str]) -> dict:
        candidates = [
            path,
            "config/tax_rules.json",
            "backend/config/tax_rules.json",
            "../config/tax_rules.json",
        ]
        for c in candidates:
            if c and os.path.exists(c):
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
        return {
            "version": "1.0",
            "effective_date": "2026-10-28",
            "rates": {
                "effective_vda_tax_rate": settings_v2.tax_rate,
                "tds_rate": settings_v2.tds_rate,
                "gst_rate": settings_v2.gst_rate,
            },
        }

    def record_acquisition(
        self,
        asset: str,
        acquired_at: str | datetime,
        quantity: float,
        unit_price_usd: float,
        fee_paid_usd: float = 0.0,
        gst_paid_usd: float = 0.0,
    ) -> TaxLot:
        """Records an acquisition lot into the FIFO inventory."""
        if quantity <= 0:
            raise ValueError(f"Acquisition quantity must be positive, got {quantity}")

        iso_time = acquired_at.isoformat() if isinstance(acquired_at, datetime) else str(acquired_at)
        lot_id = f"lot_{uuid.uuid4().hex[:12]}"
        total_cost = quantity * unit_price_usd

        lot = TaxLot(
            lot_id=lot_id,
            asset=asset,
            acquired_at=iso_time,
            quantity=quantity,
            remaining_quantity=quantity,
            unit_cost_usd=unit_price_usd,
            total_cost_usd=total_cost,
            fee_paid_usd=fee_paid_usd,
            gst_paid_usd=gst_paid_usd,
        )

        if asset not in self.open_lots:
            self.open_lots[asset] = []
        self.open_lots[asset].append(lot)
        return lot

    def record_disposal(
        self,
        asset: str,
        disposal_date: str | datetime,
        quantity: float,
        unit_proceeds_usd: float,
        fee_usd: float = 0.0,
        gst_fee_usd: float = 0.0,
        counter_asset: str = "USD",
        self_deducted_tds: bool = True,
    ) -> List[DisposalEvent]:
        """Disposes inventory in strict FIFO order, calculating tax scenarios A & B."""
        if quantity <= 0:
            raise ValueError(f"Disposal quantity must be positive, got {quantity}")

        if asset not in self.open_lots or not self.open_lots[asset]:
            raise ValueError(f"No tax lots available to dispose for asset {asset}")

        iso_date = disposal_date.isoformat() if isinstance(disposal_date, datetime) else str(disposal_date)
        fy = get_financial_year(iso_date)

        rem_to_dispose = quantity
        events: List[DisposalEvent] = []

        lots = self.open_lots[asset]
        # Sort by acquisition time ascending (FIFO)
        lots.sort(key=lambda l: l.acquired_at)

        for lot in list(lots):
            if rem_to_dispose <= 1e-9:
                break

            matched_qty = min(rem_to_dispose, lot.remaining_quantity)
            lot_cost_share = matched_qty * lot.unit_cost_usd
            proceeds_share = matched_qty * unit_proceeds_usd
            gross_gain = proceeds_share - lot_cost_share

            # Scenario A: positive gains only (no loss deduction)
            scen_a_taxable = max(0.0, gross_gain)
            scen_a_tax = scen_a_taxable * self.effective_tax_rate

            # Scenario B: gains netted (base is signed gross_gain)
            scen_b_taxable = gross_gain

            # Section 194S TDS: 1% of total transfer proceeds
            tds_val = proceeds_share * self.tds_rate

            # Pro-rate fees
            lot_fee_share = fee_usd * (matched_qty / quantity)
            lot_gst_share = gst_fee_usd * (matched_qty / quantity)

            event = DisposalEvent(
                disposal_id=f"disp_{uuid.uuid4().hex[:12]}",
                lot_id=lot.lot_id,
                disposal_date=iso_date,
                financial_year=fy,
                asset=asset,
                quantity=matched_qty,
                unit_cost_usd=lot.unit_cost_usd,
                unit_proceeds_usd=unit_proceeds_usd,
                total_cost_usd=lot_cost_share,
                total_proceeds_usd=proceeds_share,
                gross_gain_usd=gross_gain,
                scenario_a_taxable_usd=scen_a_taxable,
                scenario_a_tax_usd=scen_a_tax,
                scenario_b_taxable_usd=scen_b_taxable,
                tds_withheld_usd=tds_val,
                self_deducted=self_deducted_tds,
                fee_usd=lot_fee_share,
                gst_fee_usd=lot_gst_share,
                counter_asset=counter_asset,
            )
            events.append(event)
            self.disposals.append(event)

            lot.remaining_quantity -= matched_qty
            rem_to_dispose -= matched_qty

            if lot.remaining_quantity <= 1e-9:
                lots.remove(lot)

        if rem_to_dispose > 1e-6:
            raise ValueError(
                f"Insufficient lot inventory for asset {asset}: requested {quantity}, "
                f"shortfall {rem_to_dispose}"
            )

        return events

    def estimate_rebalance_tax_cost(
        self,
        asset: str,
        quantity_to_sell: float,
        estimated_unit_price: float,
    ) -> Tuple[float, str]:
        """Simulates FIFO disposal to estimate tax cost of a proposed rebalance order."""
        if quantity_to_sell <= 0 or asset not in self.open_lots:
            return 0.0, "estimated tax cost of this rebalance: $0.00"

        rem = quantity_to_sell
        simulated_gain_a = 0.0

        for lot in sorted(self.open_lots[asset], key=lambda l: l.acquired_at):
            if rem <= 1e-9:
                break
            matched = min(rem, lot.remaining_quantity)
            proceeds = matched * estimated_unit_price
            cost = matched * lot.unit_cost_usd
            gain = proceeds - cost
            if gain > 0:
                simulated_gain_a += gain
            rem -= matched

        est_tax_cost = simulated_gain_a * self.effective_tax_rate
        log_msg = (
            f"estimated tax cost of this rebalance: ${est_tax_cost:.2f} "
            f"(Scenario A @ 31.2% on positive gains, {MANDATORY_TAX_DISCLAIMER})"
        )
        return est_tax_cost, log_msg

    def get_financial_year_summaries(self) -> List[FinancialYearSummary]:
        """Aggregates all disposals into Financial Year summaries."""
        if not self.disposals:
            return []

        df = pd.DataFrame([asdict(d) for d in self.disposals])
        summaries: List[FinancialYearSummary] = []

        for fy, group in df.groupby("financial_year"):
            gross_proceeds = float(group["total_proceeds_usd"].sum())
            total_cost = float(group["total_cost_usd"].sum())
            net_pnl = float(group["gross_gain_usd"].sum())
            tds_total = float(group["tds_withheld_usd"].sum())
            gst_total = float(group["gst_fee_usd"].sum())

            # Scenario A: 31.2% on sum of positive gains
            scen_a_tax = float(group["scenario_a_tax_usd"].sum())
            after_tax_pnl_a = net_pnl - scen_a_tax - gst_total

            # Scenario B: 31.2% on netted gain (if net > 0)
            scen_b_taxable = max(0.0, net_pnl)
            scen_b_tax = scen_b_taxable * self.effective_tax_rate
            after_tax_pnl_b = net_pnl - scen_b_tax - gst_total

            summaries.append(
                FinancialYearSummary(
                    financial_year=str(fy),
                    disposal_count=len(group),
                    gross_proceeds_usd=gross_proceeds,
                    total_cost_basis_usd=total_cost,
                    net_realized_pnl_usd=net_pnl,
                    scenario_a_tax_usd=scen_a_tax,
                    scenario_b_tax_usd=scen_b_tax,
                    tds_credits_usd=tds_total,
                    total_gst_fees_usd=gst_total,
                    after_tax_pnl_scenario_a_usd=after_tax_pnl_a,
                    after_tax_pnl_scenario_b_usd=after_tax_pnl_b,
                )
            )

        summaries.sort(key=lambda s: s.financial_year)
        return summaries

    def export_ca_csv(self) -> str:
        """Generates standard CSV export formatted specifically for Chartered Accountant audit."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header with statutory disclaimer
        writer.writerow(["# StarkX QuantEdge v2 - FIFO Lot Disposal & Tax Schedule"])
        writer.writerow([f"# Disclaimer: {MANDATORY_TAX_DISCLAIMER}"])
        writer.writerow([
            "Disposal ID",
            "Financial Year",
            "Disposal Date",
            "Asset",
            "Quantity",
            "Unit Cost (USD)",
            "Unit Proceeds (USD)",
            "Cost Basis (USD)",
            "Proceeds (USD)",
            "Realized Gain/Loss (USD)",
            "Scenario A Tax (USD)",
            "Scenario B Tax (USD)",
            "194S TDS Deducted (USD)",
            "Self Deducted Flag",
            "Fee Paid (USD)",
            "GST on Fee (USD)",
            "Counterparty Asset",
        ])

        for d in self.disposals:
            writer.writerow([
                d.disposal_id,
                d.financial_year,
                d.disposal_date,
                d.asset,
                f"{d.quantity:.6f}",
                f"{d.unit_cost_usd:.4f}",
                f"{d.unit_proceeds_usd:.4f}",
                f"{d.total_cost_usd:.2f}",
                f"{d.total_proceeds_usd:.2f}",
                f"{d.gross_gain_usd:.2f}",
                f"{d.scenario_a_tax_usd:.2f}",
                f"{(d.scenario_b_taxable_usd * self.effective_tax_rate if d.scenario_b_taxable_usd > 0 else 0.0):.2f}",
                f"{d.tds_withheld_usd:.2f}",
                "YES" if d.self_deducted else "NO",
                f"{d.fee_usd:.4f}",
                f"{d.gst_fee_usd:.4f}",
                d.counter_asset or "USD",
            ])

        return output.getvalue()
