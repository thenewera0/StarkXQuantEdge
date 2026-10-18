"""Automated Regression & Invariant Tests for StarkX QuantEdge Audit Fixes.

Covers:
1. P0-2 Resolver Lookahead Excursion Elimination:
   Ensures limit orders that do not touch the limit price within limit_expiry_bars
   are strictly marked 'unfilled' even if future prices gain >= 5%.
2. P1-1 Meta-Model Gating Freeze:
   Ensures meta_gate_enabled is False by default so in-sample PAVA distortion does not inflate live EV.
3. Candle Timing & Future Timestamp Validation:
   Ensures validate_ohlcv filters out unclosed in-progress candles whose timestamps are in the future.
4. Capital-Adaptive Sizing & Ruin Boundary Invariants:
   Verifies Quarter-Kelly, Gambler's Ruin, and Gross Exposure clamp math.
"""

from __future__ import annotations

import unittest
import numpy as np
import pandas as pd

from app.config import settings
from app.data.validate import validate_ohlcv
from app.resolver import _resolve_one
from app.sizing import (
    quarter_kelly,
    ruin_prob,
    ruin_fraction,
    tier_for_equity,
    position_size,
    exposure_budget,
)


class TestResolverDefectElimination(unittest.TestCase):
    """Verifies that resolver.py does NOT retroactively fill expired limit orders."""

    def test_unfilled_limit_with_huge_future_excursion_remains_unfilled(self):
        """A limit order not touched in bars 0..3 must expire as 'unfilled',
        even if bar 5 surges +20% (preventing mfe_early lookahead leakage).
        """
        times = pd.date_range("2026-08-01 00:00", periods=6, freq="4h", tz="UTC")
        future = pd.DataFrame(
            {
                "open": [102.0, 103.0, 102.5, 104.0, 110.0, 120.0],
                "high": [104.0, 105.0, 104.5, 106.0, 120.0, 125.0],
                "low": [101.0, 101.5, 101.2, 102.0, 108.0, 115.0],
                "close": [103.0, 104.0, 103.5, 105.0, 118.0, 124.0],
                "volume": [1000.0] * 6,
            },
            index=times,
        )

        res = _resolve_one(
            symbol="BTCUSDT",
            market="crypto",
            interval="4h",
            direction="long",
            entry=100.0,
            stop=95.0,
            target=115.0,
            atr_pct=0.02,
            future=future,
            max_hold=12,
            strategy="core",
        )

        self.assertIsNotNone(res, "Resolution must return a result once expiry bars elapse")
        self.assertEqual(res["result"], "unfilled", "Must be marked unfilled despite +25% excursion")
        self.assertIsNone(res["pnl"], "Unfilled trade must have null pnl")
        self.assertIsNone(res["pnl_frac"], "Unfilled trade must have null pnl_frac")

    def test_filled_limit_order_resolves_accurately(self):
        """When low breaches the limit price within expiry bars, it fills and trades normally."""
        times = pd.date_range("2026-08-01 00:00", periods=4, freq="4h", tz="UTC")
        future = pd.DataFrame(
            {
                "open": [102.0, 101.0, 105.0, 108.0],
                "high": [103.0, 102.0, 112.0, 110.0],
                "low": [101.0, 99.0, 104.0, 106.0],
                "close": [101.5, 100.5, 110.0, 107.0],
                "volume": [1000.0] * 4,
            },
            index=times,
        )

        res = _resolve_one(
            symbol="BTCUSDT",
            market="crypto",
            interval="4h",
            direction="long",
            entry=100.0,
            stop=95.0,
            target=110.0,
            atr_pct=0.02,
            future=future,
            max_hold=12,
            strategy="core",
        )

        self.assertIsNotNone(res)
        self.assertEqual(res["result"], "target")
        self.assertIsNotNone(res["pnl"])
        self.assertGreater(res["pnl"], 0.0, "Winning trade must have positive net PnL")


class TestMetaModelGatingFreeze(unittest.TestCase):
    """Verifies meta_gate_enabled is False by default during audit."""

    def test_meta_gate_disabled_in_config(self):
        self.assertFalse(
            settings.meta_gate_enabled,
            "meta_gate_enabled must remain False to prevent in-sample PAVA distortion from driving live EV",
        )


class TestValidateFutureCandles(unittest.TestCase):
    """Verifies that validate_ohlcv filters out unclosed in-progress candles."""

    def test_future_candle_is_dropped(self):
        # Create 3 past bars and 1 bar 2 hours in the future
        past_times = pd.date_range(end=pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=1), periods=3, freq="1h")
        future_time = pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=2)
        all_times = past_times.append(pd.DatetimeIndex([future_time]))

        df = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0, 103.0],
                "high": [102.0, 103.0, 104.0, 105.0],
                "low": [99.0, 100.0, 101.0, 102.0],
                "close": [101.0, 102.0, 103.0, 104.0],
                "volume": [500.0, 600.0, 700.0, 100.0],
            },
            index=all_times,
        )

        clean_df, report = validate_ohlcv(df, "1h")
        self.assertEqual(len(clean_df), 3, "Future candle must be dropped")
        self.assertEqual(report.get("dropped_future"), 1)
        self.assertNotIn(future_time, clean_df.index)

    def test_past_candles_are_preserved(self):
        past_times = pd.date_range(end=pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=5), periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [105.0] * 5,
                "low": [95.0] * 5,
                "close": [102.0] * 5,
                "volume": [100.0] * 5,
            },
            index=past_times,
        )
        clean_df, report = validate_ohlcv(df, "1h")
        self.assertEqual(len(clean_df), 5, "All valid past candles must be preserved")


class TestSizingAndRuinBoundaryMath(unittest.TestCase):
    """Verifies capital-adaptive mathematical boundaries."""

    def test_quarter_kelly_negative_or_zero_edge(self):
        # 40% win rate on 1:1 reward-to-risk has negative edge
        fk_neg = quarter_kelly(0.40, 1.0)
        self.assertEqual(fk_neg, 0.0, "Quarter-Kelly must be exactly 0.0 on negative edge")

        # 50% win rate on 1:1 has zero edge
        fk_zero = quarter_kelly(0.50, 1.0)
        self.assertEqual(fk_zero, 0.0, "Quarter-Kelly must be exactly 0.0 on zero edge")

    def test_quarter_kelly_positive_edge(self):
        # 60% win rate on 2:1 reward-to-risk:
        # f = p - (1-p)/b = 0.60 - 0.40/2 = 0.40
        # quarter_kelly = 0.40 / 4 = 0.10
        fk_pos = quarter_kelly(0.60, 2.0)
        self.assertAlmostEqual(fk_pos, 0.10, places=5)

    def test_ruin_fraction_bounds_risk_under_cap(self):
        rf = ruin_fraction(0.60, 2.0, cap=0.02, ruin_limit=0.05)
        self.assertLessEqual(rf, 0.02, "Ruin fraction cannot exceed the cap")
        self.assertGreater(rf, 0.0, "Ruin fraction on strong edge must be positive")

    def test_exposure_budget_gross_and_heat_clamp(self):
        # Standard tier ($1,000 equity) has 3.0x max gross ($3,000) and 6% heat ($60)
        eb = exposure_budget(equity=1000.0, open_notional=2500.0, open_heat=0.05)
        self.assertEqual(eb["tier"], "standard")
        self.assertEqual(eb["gross_ceiling"], 3.0)
        self.assertAlmostEqual(eb["remaining_usd"], 500.0, places=1)
        self.assertAlmostEqual(eb["heat_remaining"], 0.01, places=3)
        self.assertIsNone(eb["binding"], "Room remains under both gross and heat")

        # Now saturate heat to 6%
        eb_full_heat = exposure_budget(equity=1000.0, open_notional=2500.0, open_heat=0.06)
        self.assertEqual(eb_full_heat["binding"], "heat", "Heat cap must bind when open heat reaches 6%")


class TestMainSchedulerArbJob(unittest.TestCase):
    """Verifies that main.py actually registers _arb_job in the APScheduler."""

    def test_arb_job_registered_in_scheduler(self):
        import inspect
        from app import main

        source = inspect.getsource(main.lifespan)
        self.assertIn('_scheduler.add_job', source)
        self.assertIn('id="arb"', source, "lifespan must add _arb_job with id='arb'")


if __name__ == "__main__":
    unittest.main()
