# StarkX QuantEdge: Quantitative Research & Risk Glossary

**Governance Status:** Active  
**Effective Date:** 2026-10-27 (Pre-Registration Amendment 1)  

---

### Core Metric Definitions

#### `active_days`
- **Definition:** The count of distinct UTC calendar dates ($YYYY-MM-DD$) on which at least one ($\ge 1$) unique, sized trade was initiated or executed in the evaluation cohort.
- **Application:** Canonical, transparent measure of out-of-sample sample size and day-cluster degrees of freedom for statistical testing and power calculations.
- **Decision Status:** **MANDATORY GOVERNANCE METRIC**. Used as the primary sample horizon trigger (`active_days >= 60`) for forward evaluation.

#### `n_trades`
- **Definition:** The total count of unique, sized trades in the evaluation cohort (de-duplicated across sub-bar scans, with zero risk stacking).
- **Application:** Denominator for trade-level mean return, profit factor, win rate, and concentration metrics.
- **Decision Status:** **MANDATORY GOVERNANCE METRIC**. Stated in every forward report and performance ledger alongside `active_days`.

#### `N_eff` (Effective Sample Size)
- **Historical Context:** An exploratory sample-dependence metric evaluated in Phases 0.5–8 using trade-level autocorrelation adjustments (Kish design effect: $N \frac{1-\rho}{1+\rho}$) and day-cluster Herfindahl normalization.
- **Governance Status:** **NOT USED FOR DECISIONS**. Permanently retired from forward reports, stopping triggers, and capital readiness decisions due to estimator ambiguity across competing cluster models. `active_days` and `n_trades` are the sole canonical sample size metrics.

#### `R_net` (Net Realized R-Multiple)
- **Definition:** Realized trade profit or loss divided by initial dollar risk denominator:
  $$R_{\text{net}} = \frac{\text{Realized P&L}}{\text{Initial Dollar Risk}} = \frac{\text{Realized P&L}}{\text{Entry} \times \text{Stop Distance Fraction}}$$
- **Invariant:** Initial risk denominator is strictly computed from `initial_stop` (`entry - stop_mult * atr`) and is immutable. Resolver trailing stops or breakeven ratchets never modify this denominator.

#### `day_block_bootstrap`
- **Definition:** Stationary daily block bootstrap ($B = 10,000$ resamples) that resamples entire active trading days with replacement, exactly preserving intra-day cross-sectional correlation across crypto assets without parametric distribution assumptions.

#### `enforce_geometry_invariants`
- **Definition:** Pre-insertion validation and data-sanitation filter enforcing all 7 geometric validity invariants (stop opposing trade direction, target advancing trade direction, non-zero target distance, minimum stop distance, and target multiple in $[0.50\text{R}, 5.00\text{R}]$).
- **Governance Classification:** **VALIDATION & LOGGING FIX**. Does not alter strategy parameters, indicator formulas, entry rules, or calibration weights.

#### `freeze_hash`
- **Definition:** The cryptographic SHA-256 fingerprint (`3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`) locking all 14 frozen signal parameters in `config/frozen_core_long_v1_1.json`. Monitored continuously by CI guards.

#### `live_trading_enabled`
- **Definition:** Production order-routing kill-switch. Strictly locked to `False` (Rule R4). Real-money exchange execution cannot occur under any circumstances during the paper evaluation horizon.
