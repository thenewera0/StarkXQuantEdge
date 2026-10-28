"""StarkX QuantEdge v2: Database Models & Idempotent Schema.

Rule 0.1: Tables prefixed with v2_.
Rule 0.3: Order ids are idempotent: id = sha256(sleeve, asset, bar_open_time, side), UNIQUE-constrained.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional
import psycopg

from .config import settings_v2
from app import db


def compute_order_id(sleeve: str, asset: str, bar_open_time: datetime | str, side: str) -> str:
    """Computes deterministic SHA-256 order ID enforcing idempotency across daily bars.
    
    id = sha256(sleeve, asset, bar_open_time, side)
    """
    if isinstance(bar_open_time, datetime):
        time_str = bar_open_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        time_str = str(bar_open_time)
        
    raw = f"{sleeve.lower()}_{asset.upper()}_{time_str}_{side.upper()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS v2_orders (
    id VARCHAR(64) PRIMARY KEY,
    sleeve VARCHAR(16) NOT NULL,
    asset VARCHAR(32) NOT NULL,
    bar_open_time TIMESTAMPTZ NOT NULL,
    side VARCHAR(8) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'NEW',
    target_weight NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    order_qty NUMERIC(18, 8) NOT NULL DEFAULT 0.0,
    limit_price NUMERIC(18, 8) NOT NULL DEFAULT 0.0,
    filled_qty NUMERIC(18, 8) NOT NULL DEFAULT 0.0,
    avg_fill_price NUMERIC(18, 8) NOT NULL DEFAULT 0.0,
    fee_paid_usd NUMERIC(14, 4) NOT NULL DEFAULT 0.0,
    gst_paid_usd NUMERIC(14, 4) NOT NULL DEFAULT 0.0,
    slippage_bps NUMERIC(10, 4) NOT NULL DEFAULT 0.0,
    est_tax_cost_usd NUMERIC(14, 4) NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_v2_orders_idempotent UNIQUE (sleeve, asset, bar_open_time, side)
);

CREATE TABLE IF NOT EXISTS v2_positions (
    asset VARCHAR(32) PRIMARY KEY,
    quantity NUMERIC(18, 8) NOT NULL DEFAULT 0.0,
    current_weight NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    target_weight NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    cost_basis_usd NUMERIC(18, 4) NOT NULL DEFAULT 0.0,
    mark_price NUMERIC(18, 8) NOT NULL DEFAULT 0.0,
    unrealized_pnl_usd NUMERIC(18, 4) NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS v2_tax_lots (
    lot_id VARCHAR(64) PRIMARY KEY,
    asset VARCHAR(32) NOT NULL,
    buy_date DATE NOT NULL,
    quantity_initial NUMERIC(18, 8) NOT NULL,
    quantity_remaining NUMERIC(18, 8) NOT NULL,
    cost_basis_per_unit NUMERIC(18, 8) NOT NULL,
    fee_paid_usd NUMERIC(14, 4) NOT NULL DEFAULT 0.0,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS v2_tax_disposals (
    disposal_id VARCHAR(64) PRIMARY KEY,
    lot_id VARCHAR(64) NOT NULL,
    asset VARCHAR(32) NOT NULL,
    disposal_date DATE NOT NULL,
    financial_year VARCHAR(16) NOT NULL,
    quantity NUMERIC(18, 8) NOT NULL,
    proceeds_usd NUMERIC(18, 4) NOT NULL,
    cost_basis_usd NUMERIC(18, 4) NOT NULL,
    gain_usd NUMERIC(18, 4) NOT NULL,
    scenario_a_tax_usd NUMERIC(18, 4) NOT NULL,
    scenario_b_tax_usd NUMERIC(18, 4) NOT NULL,
    tds_usd NUMERIC(18, 4) NOT NULL,
    self_deducted BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS v2_portfolio_snapshots (
    as_of TIMESTAMPTZ PRIMARY KEY,
    equity_usd NUMERIC(18, 4) NOT NULL,
    cash_usd NUMERIC(18, 4) NOT NULL,
    cash_pct NUMERIC(10, 6) NOT NULL,
    gross_exposure_pct NUMERIC(10, 6) NOT NULL,
    vol_target_pct NUMERIC(10, 6) NOT NULL DEFAULT 0.15,
    realized_vol_pct NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    drawdown_pct NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    governor VARCHAR(16) NOT NULL DEFAULT 'NORMAL',
    ledger_reconciled BOOLEAN NOT NULL DEFAULT TRUE,
    delta_usd NUMERIC(10, 4) NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def init_v2_tables() -> bool:
    """Creates all v2_ prefixed tables if persistence is enabled."""
    if not db.enabled():
        return False
    try:
        with db.get_conn() as conn, conn.cursor() as cur:
            cur.execute(CREATE_TABLES_SQL)
            conn.commit()
            return True
    except Exception as e:
        print(f"Warning: Failed to init v2 tables: {e}")
        return False
