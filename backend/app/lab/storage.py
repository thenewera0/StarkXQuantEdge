"""StarkX LAB: Persistent Storage Layer (lab_* tables).

Manages tables:
- lab_variants
- lab_signals (UNIQUE constraint on strategy_id, variant_id, symbol, direction, bar_open_time)
- lab_positions
- lab_events
- lab_equity
- lab_trials (research_trials counter)

Strictly uses local SQLite database backend/data/lab.db (or in-memory for testing).
Never requires private database passwords or exchange credentials.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.lab.models import LabEvent, LabPosition, Signal


DB_PATH = Path(__file__).resolve().parents[2] / "data" / "lab.db"


class LabStorage:
    """Encapsulates SQLite persistence for all lab_* tables."""

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            self.db_path = DB_PATH
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._mem_conn = None
        else:
            self.db_path = Path(db_path)
            if str(self.db_path) == ":memory:":
                self._mem_conn = sqlite3.connect(":memory:")
                self._mem_conn.row_factory = sqlite3.Row
            else:
                self._mem_conn = None
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            # 1. lab_variants
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lab_variants (
                    variant_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    tier TEXT NOT NULL DEFAULT 'T0',
                    status TEXT NOT NULL DEFAULT 'active',
                    params_json TEXT NOT NULL,
                    cash_usd REAL NOT NULL DEFAULT 10000.0,
                    equity_usd REAL NOT NULL DEFAULT 10000.0,
                    total_trades INTEGER NOT NULL DEFAULT 0,
                    active_days INTEGER NOT NULL DEFAULT 0,
                    mean_net_r REAL NOT NULL DEFAULT 0.0,
                    ci_low REAL NOT NULL DEFAULT 0.0,
                    ci_high REAL NOT NULL DEFAULT 0.0,
                    profit_factor REAL NOT NULL DEFAULT 1.0,
                    max_dd_pct REAL NOT NULL DEFAULT 0.0,
                    vs_control_r REAL NOT NULL DEFAULT 0.0,
                    vs_control_ci_low REAL NOT NULL DEFAULT 0.0,
                    weight_pct REAL NOT NULL DEFAULT 0.02,
                    taker_mean_r REAL NOT NULL DEFAULT 0.0,
                    maker_mean_r REAL NOT NULL DEFAULT 0.0,
                    paused_at TEXT,
                    pause_reason TEXT,
                    parent_variant_id TEXT,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)

            # 2. lab_signals with UNIQUE constraint per Rule 0.4
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lab_signals (
                    signal_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    bar_open_time TEXT NOT NULL,
                    entry_mode TEXT NOT NULL,
                    stop_atr REAL NOT NULL,
                    target_r REAL,
                    trail_atr REAL,
                    max_hold_bars INTEGER NOT NULL,
                    meta_json TEXT,
                    is_backfill INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(strategy_id, variant_id, symbol, direction, bar_open_time)
                )
            """)

            # 3. lab_positions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lab_positions (
                    position_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_mode TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    size_qty REAL NOT NULL,
                    initial_stop REAL NOT NULL,
                    trailing_stop REAL,
                    target_price REAL,
                    risk_r_usd REAL NOT NULL,
                    max_hold_bars INTEGER NOT NULL,
                    age_bars INTEGER NOT NULL DEFAULT 0,
                    unrealized_r REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'open',
                    exit_price REAL,
                    exit_time TEXT,
                    exit_reason TEXT,
                    realized_r REAL,
                    realized_pnl_usd REAL,
                    fee_paid_usd REAL NOT NULL DEFAULT 0.0,
                    gst_paid_usd REAL NOT NULL DEFAULT 0.0,
                    slippage_usd REAL NOT NULL DEFAULT 0.0,
                    funding_paid_usd REAL NOT NULL DEFAULT 0.0,
                    twin_pnl_usd REAL NOT NULL DEFAULT 0.0,
                    is_backfill INTEGER NOT NULL DEFAULT 0,
                    warm_start INTEGER NOT NULL DEFAULT 0
                )
            """)

            # Migration: Ensure warm_start column exists in existing databases
            cursor = cur.execute("PRAGMA table_info(lab_positions)")
            cols = [r[1] for r in cursor.fetchall()]
            if "warm_start" not in cols:
                cur.execute("ALTER TABLE lab_positions ADD COLUMN warm_start INTEGER NOT NULL DEFAULT 0")

            # 4. lab_events
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lab_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    variant_id TEXT,
                    message TEXT NOT NULL
                )
            """)

            # 5. lab_equity (daily tracking)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lab_equity (
                    variant_id TEXT NOT NULL,
                    t TEXT NOT NULL,
                    variant_val REAL NOT NULL,
                    control_val REAL NOT NULL,
                    cash_val REAL NOT NULL,
                    PRIMARY KEY(variant_id, t)
                )
            """)

            # 6. lab_trials counter (Rule 0.6)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lab_trials (
                    counter_key TEXT PRIMARY KEY,
                    trials_count INTEGER NOT NULL
                )
            """)
            cur.execute("INSERT OR IGNORE INTO lab_trials (counter_key, trials_count) VALUES ('research_trials', 10)")
            conn.commit()

    def record_signal(self, sig: Signal, is_backfill: bool = False) -> bool:
        """Stores signal. Returns False if duplicate exists (idempotency check)."""
        t_str = sig.bar_open_time.isoformat() if hasattr(sig.bar_open_time, "isoformat") else str(sig.bar_open_time)
        now_str = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO lab_signals (
                        signal_id, strategy_id, variant_id, symbol, direction,
                        bar_open_time, entry_mode, stop_atr, target_r, trail_atr,
                        max_hold_bars, meta_json, is_backfill, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sig.signal_id, sig.strategy_id, sig.variant_id, sig.symbol, sig.direction,
                    t_str, sig.entry_mode, sig.stop_atr, sig.target_r, sig.trail_atr,
                    sig.max_hold_bars, json.dumps(sig.meta), 1 if is_backfill else 0, now_str
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # Duplicate signal
            return False

    def record_event(self, kind: str, message: str, variant_id: Optional[str] = None) -> None:
        """Logs an event to lab_events."""
        ts = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO lab_events (ts, kind, variant_id, message) VALUES (?, ?, ?, ?)",
                (ts, kind, variant_id, message)
            )
            conn.commit()

    def save_position(self, pos: LabPosition, is_backfill: bool = False) -> None:
        """Upserts a paper position."""
        t_entry = pos.entry_time.isoformat() if hasattr(pos.entry_time, "isoformat") else str(pos.entry_time)
        t_exit = pos.exit_time.isoformat() if pos.exit_time and hasattr(pos.exit_time, "isoformat") else (str(pos.exit_time) if pos.exit_time else None)

        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO lab_positions (
                    position_id, strategy_id, variant_id, symbol, side, entry_mode,
                    entry_price, entry_time, size_qty, initial_stop, trailing_stop,
                    target_price, risk_r_usd, max_hold_bars, age_bars, unrealized_r,
                    status, exit_price, exit_time, exit_reason, realized_r,
                    realized_pnl_usd, fee_paid_usd, gst_paid_usd, slippage_usd,
                    funding_paid_usd, twin_pnl_usd, is_backfill, warm_start
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pos.position_id, pos.strategy_id, pos.variant_id, pos.symbol, pos.side, pos.entry_mode,
                pos.entry_price, t_entry, pos.size_qty, pos.initial_stop, pos.trailing_stop,
                pos.target_price, pos.risk_r_usd, pos.max_hold_bars, pos.age_bars, pos.unrealized_r,
                pos.status, pos.exit_price, t_exit, pos.exit_reason, pos.realized_r,
                pos.realized_pnl_usd, pos.fee_paid_usd, pos.gst_paid_usd, pos.slippage_usd,
                pos.funding_paid_usd, pos.twin_pnl_usd, 1 if is_backfill else 0,
                1 if getattr(pos, "warm_start", False) else 0
            ))
            conn.commit()

    def get_open_positions(self, variant_id: Optional[str] = None) -> List[Dict]:
        """Queries open paper positions."""
        query = "SELECT * FROM lab_positions WHERE status = 'open'"
        params = []
        if variant_id:
            query += " AND variant_id = ?"
            params.append(variant_id)
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_variant_trades(self, variant_id: str, forward_only: bool = True) -> List[Dict]:
        """Queries closed trades for a variant (excludes backfill and warm start when forward_only=True)."""
        query = "SELECT * FROM lab_positions WHERE variant_id = ? AND status = 'closed'"
        if forward_only:
            query += " AND is_backfill = 0 AND warm_start = 0"
        with self._get_conn() as conn:
            rows = conn.execute(query, [variant_id]).fetchall()
            return [dict(r) for r in rows]

    def get_events(self, limit: int = 50) -> List[Dict]:
        """Queries recent events."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM lab_events ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_variants(self) -> List[Dict]:
        """Queries all variants."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM lab_variants ORDER BY strategy_id, variant_id").fetchall()
            return [dict(r) for r in rows]

    def save_variant(self, row: Dict) -> None:
        """Upserts a variant record."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO lab_variants (
                    variant_id, strategy_id, timeframe, direction, tier, status,
                    params_json, cash_usd, equity_usd, total_trades, active_days,
                    mean_net_r, ci_low, ci_high, profit_factor, max_dd_pct,
                    vs_control_r, vs_control_ci_low, weight_pct, taker_mean_r,
                    maker_mean_r, paused_at, pause_reason, parent_variant_id,
                    created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["variant_id"], row["strategy_id"], row["timeframe"], row["direction"],
                row.get("tier", "T0"), row.get("status", "active"),
                json.dumps(row.get("params", {})), row.get("cash_usd", 10000.0),
                row.get("equity_usd", 10000.0), row.get("total_trades", 0),
                row.get("active_days", 0), row.get("mean_net_r", 0.0),
                row.get("ci_low", 0.0), row.get("ci_high", 0.0),
                row.get("profit_factor", 1.0), row.get("max_dd_pct", 0.0),
                row.get("vs_control_r", 0.0), row.get("vs_control_ci_low", 0.0),
                row.get("weight_pct", 0.02), row.get("taker_mean_r", 0.0),
                row.get("maker_mean_r", 0.0), row.get("paused_at"),
                row.get("pause_reason"), row.get("parent_variant_id"),
                row.get("created_at", now_str), now_str
            ))
            conn.commit()

    def get_trials_count(self) -> int:
        """Rule 0.6: Retrieves research trials count."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT trials_count FROM lab_trials WHERE counter_key = 'research_trials'").fetchone()
            return row["trials_count"] if row else 10

    def increment_trials_count(self) -> int:
        """Rule 0.6: Increments research trials count upon spawn."""
        with self._get_conn() as conn:
            conn.execute("UPDATE lab_trials SET trials_count = trials_count + 1 WHERE counter_key = 'research_trials'")
            conn.commit()
            return self.get_trials_count()

    def save_equity_point(self, variant_id: str, t: str, variant_val: float, control_val: float, cash_val: float) -> None:
        """Stores daily equity point."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO lab_equity (variant_id, t, variant_val, control_val, cash_val)
                VALUES (?, ?, ?, ?, ?)
            """, (variant_id, t, variant_val, control_val, cash_val))
            conn.commit()

    def get_equity_series(self, variant_id: str) -> List[Dict]:
        """Retrieves equity curve points."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT t, variant_val, control_val, cash_val FROM lab_equity WHERE variant_id = ? ORDER BY t ASC",
                (variant_id,)
            ).fetchall()
            return [
                {
                    "t": r["t"],
                    "variant": round(r["variant_val"], 2),
                    "control": round(r["control_val"], 2),
                    "cashAfterTax": round(r["cash_val"], 2),
                }
                for r in rows
            ]
