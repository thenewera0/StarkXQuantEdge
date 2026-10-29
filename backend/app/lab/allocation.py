"""StarkX LAB: Portfolio Allocation, Hedge Weighting & Self-Improvement Actions.

Section 5 Requirements:
- Allocation: Hedge algorithm (eta=0.1 on daily net R per unit risk),
  James-Stein shrinkage toward zero when n < 100,
  floor 2%, cap 30%, normalized. T0 variants fixed at floor (2%).
- Actions:
  - PAUSE: posterior P(mean R > 0) < 5% after >= 100 trades and >= 40 days,
    OR account drawdown >= 15%, OR daily loss <= -2% (24h pause).
  - RETIRE: 90 days paused without recovery.
  - SPAWN: For each T1+ variant with mean net R > 0, create up to 2 neighbours
    (numeric params +/- 20% inside bounds), max 1 spawn per strategy per 30 days,
    max 40 concurrent variants; increments research_trials and logs in lab_events.
  - CHAMPION SWAP: challenger beats champion on overlapping days with paired day-block lower 95% bound > 0 and >= 100 trades.
- Section 6: Lab Portfolio net BTC-beta-adjusted exposure cap <= 2.0 x equity.
- Expected False Positives = 0.05 * (variants tested at T2/T3).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
from app.lab.tiers import day_block_ci, paired_difference_ci


class HedgeAllocator:
    """Computes virtual risk share weights across active Lab variants."""

    ETA: float = 0.10
    FLOOR_WEIGHT: float = 0.02   # 2% floor
    CAP_WEIGHT: float = 0.30     # 30% cap
    MAX_BETA_EXPOSURE: float = 2.0

    @classmethod
    def compute_weights(
        cls,
        variant_metrics: Dict[str, Dict],
    ) -> Dict[str, float]:
        """Calculates normalized hedge weights with shrinkage and constraints.
        
        variant_metrics: mapping of variant_id -> {
            'tier': 'T0'|'T1'|'T2'|'T3',
            'status': 'active'|'paused'|'retired',
            'n_trades': int,
            'mean_net_r': float,
            'std_r': float,
        }
        """
        active_variants = {
            vid: m for vid, m in variant_metrics.items()
            if m.get("status") == "active"
        }
        if not active_variants:
            return {}

        raw_scores = {}
        for vid, m in active_variants.items():
            tier = m.get("tier", "T0")
            n = m.get("n_trades", 0)
            mean_r = m.get("mean_net_r", 0.0)

            # T0 variants are fixed at the floor
            if tier == "T0":
                raw_scores[vid] = cls.FLOOR_WEIGHT
                continue

            # James-Stein shrinkage toward zero when n < 100
            if n < 100:
                shrinkage_factor = max(0.0, 1.0 - (10.0 / max(n, 1)))
                shrunk_mean_r = mean_r * shrinkage_factor
            else:
                shrunk_mean_r = mean_r

            # Hedge algorithm update: exp(eta * performance)
            score = math.exp(cls.ETA * max(-5.0, min(5.0, shrunk_mean_r)))
            raw_scores[vid] = score

        # Normalize raw scores to sum to 1.0
        total_score = sum(raw_scores.values())
        if total_score <= 0:
            equal = 1.0 / len(active_variants)
            return {vid: round(equal, 4) for vid in active_variants}

        weights = {vid: s / total_score for vid, s in raw_scores.items()}

        # Apply Floor (2%) and Cap (30%) iteratively
        adjusted = weights.copy()
        for _ in range(5):
            excess = 0.0
            free_keys = []
            for vid, w in adjusted.items():
                tier = active_variants[vid].get("tier", "T0")
                if tier == "T0" or w < cls.FLOOR_WEIGHT:
                    excess += (cls.FLOOR_WEIGHT - w)
                    adjusted[vid] = cls.FLOOR_WEIGHT
                elif w > cls.CAP_WEIGHT:
                    excess -= (w - cls.CAP_WEIGHT)
                    adjusted[vid] = cls.CAP_WEIGHT
                else:
                    free_keys.append(vid)

            if abs(excess) < 1e-4 or not free_keys:
                break

            delta = excess / len(free_keys)
            for k in free_keys:
                adjusted[k] = max(cls.FLOOR_WEIGHT, min(cls.CAP_WEIGHT, adjusted[k] - delta))

        # Final normalization to exactly 1.0
        final_total = sum(adjusted.values())
        norm_weights = {vid: round(w / final_total, 4) for vid, w in adjusted.items()}
        return norm_weights


class SelfImprovementGovernor:
    """Evaluates automated lifecycle actions: Pause, Retire, Spawn, Champion Swap."""

    @staticmethod
    def evaluate_pause(
        n_trades: int,
        active_days: int,
        returns: List[float],
        dates: List[str],
        account_drawdown_pct: float,
        daily_loss_pct: float,
    ) -> Tuple[bool, Optional[str]]:
        """Evaluates pause triggers per Section 5."""
        # 1. 24h pause on daily loss <= -2%
        if daily_loss_pct <= -2.0:
            return True, f"Daily loss trigger: {daily_loss_pct:.2f}% <= -2.0%"

        # 2. Account drawdown >= 15%
        if account_drawdown_pct >= 15.0:
            return True, f"Account drawdown trigger: {account_drawdown_pct:.2f}% >= 15.0%"

        # 3. Posterior P(mean R > 0) < 5% after >= 100 trades and >= 40 active days
        if n_trades >= 100 and active_days >= 40 and returns:
            s = np.array(returns)
            mean_r = float(np.mean(s))
            std_r = float(np.std(s)) if len(s) > 1 else 1.0
            se = std_r / math.sqrt(len(s))
            # Normal approximation for posterior probability P(mean > 0)
            z = mean_r / max(se, 1e-6)
            p_mean_gt_zero = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
            if p_mean_gt_zero < 0.05:
                return True, f"Posterior P(mean R > 0)={p_mean_gt_zero:.1%} < 5.0% after {n_trades} trades"

        return False, None

    @staticmethod
    def evaluate_retire(paused_days: int) -> bool:
        """Retire after 90 days paused without recovery."""
        return paused_days >= 90

    @staticmethod
    def evaluate_champion_swap(
        champ_returns: List[float],
        challenger_returns: List[float],
        overlapping_dates: List[str],
    ) -> Tuple[bool, float]:
        """Evaluates whether challenger beats champion: paired lower 95% bound > 0 and >= 100 trades."""
        if len(challenger_returns) < 100 or len(champ_returns) < 100:
            return False, 0.0

        low_95, _ = paired_difference_ci(
            strat_returns=challenger_returns,
            control_returns=champ_returns,
            dates=overlapping_dates,
            ci_pct=95.0,
        )
        should_swap = low_95 > 0.0
        return should_swap, low_95

    @staticmethod
    def generate_spawn_candidates(
        parent_variant_id: str,
        current_params: dict,
        numeric_bounds: dict,
    ) -> List[dict]:
        """Generates up to 2 neighbour configurations: each numeric parameter +/-20% within bounds."""
        neighbours = []
        for direction, mult in [("high", 1.20), ("low", 0.80)]:
            cand = {}
            for k, val in current_params.items():
                if isinstance(val, (int, float)) and k in numeric_bounds:
                    b_min, b_max = numeric_bounds[k]
                    new_val = val * mult
                    if isinstance(val, int):
                        new_val = int(round(new_val))
                    else:
                        new_val = round(new_val, 2)
                    cand[k] = max(b_min, min(b_max, new_val))
                else:
                    cand[k] = val
            neighbours.append(cand)

        return neighbours
