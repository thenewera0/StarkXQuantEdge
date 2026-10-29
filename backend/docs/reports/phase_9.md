# StarkX QuantEdge: Phase 9 Report — Pre-Registration Amendment

**Governance Status:** FORMAL RESEARCH PRE-REGISTRATION AMENDMENT (BEFORE ANY FORWARD DATA EVALUATION)  
**Operating Mandate:** Zero Signal-Parameter Changes | Freeze Hash & Live Lock Stay in Force  
**Baseline Freeze Hash:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` (HASH-LOCKED)  
**Live Trading Kill-Switch:** `live_trading_enabled = False` (Rule R4 Permanently Enforced)  
**Pre-Registration Amendment 1 Hash:** `1f3127b3eca41dd45db275bc66dad1b45fc2f4ce8805d636afc9b336e04ecd92`  
**Report Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`  
**Report Generation Engine:** `scripts/generate_report.py` (Rule 4.0 Deterministic Provenance)  

---

## Executive Summary (10-Line Plain-English Overview)

1. **Pre-Registration Timing Lock (9.1 & 9.3):** Prior to the observation or evaluation of any post-freeze out-of-sample forward trade data, this amendment formally updates the forward evaluation trigger while keeping all signal parameters and promotion rules 100% frozen.

2. **Canonical Sample Size Metrics (9.1):** Effective sample size ($N_{\text{eff}}$) is permanently retired from forward decision rules and reports due to mathematical ambiguity across competing cluster models; `active_days` (distinct UTC calendar dates with $\ge 1$ trade) and `n_trades` are enacted as the sole canonical sample size counts.

3. **Plain Counts Forensic Truth (9.1):** The unique crypto `core_4h_long` historical ledger comprises exactly **26 active trading days** containing 156 trades (July: 8 days/110 trades, August: 3 days/4 trades, September: 9 days/23 trades, October: 6 days/19 trades), with mean $6.00$, median $2.5$, and max $32$ trades/day.

4. **19 vs 48 Days Reconciliation (9.1):** The 19-day figure in Phase 8 was the exact intersection of active dates covered by the top-50 coin parquet cache for paired gated simulation; the 48-day figure in Phase 7 was an author transcription mistake confusing `TIMEOUT_BARS = 48` with active days. The true ledger count is 26.

5. **Mutated Stops Resolved (9.1):** A single conditional SQL query on `signals` confirms that out of 1,146 total signals, exactly 357 rows had trailing stops updated; in 29 instances the trailing stop numerically equaled `initial_stop`, leaving exactly 328 rows where stop differed from initial stop ($328 + 29 = 357$).

6. **Statistical Power Table (9.2):** Based on observed day-level return variance ($\sigma_{\text{day}} = 1.6683$ R, $\sigma_S = 10.0099$), the standard error scales as $\text{SE}(K) = \frac{1.6683}{\sqrt{K}}$, yielding SE of $0.3153$ R at $K=28$, $0.2487$ R at $K=45$, $0.2154$ R at $K=60$, and $0.1759$ R at $K=90$.

7. **Simulation Power Results (9.2):** Resampling 10,000 day-clusters confirms that at $K=60$ active days, statistical power $P(\text{PASS})$ reaches **45.3%** under true mean $\mu = +0.40$ R (rising to 68.6% at 90 days), while false-positive PASS probability under null $\mu = 0.0$ R is strictly constrained to **1.3%**.

8. **Pre-Registration Amendment Protocol (9.3):** Formal document [`docs/PRE_REGISTRATION_AMENDMENT.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/PRE_REGISTRATION_AMENDMENT.md) establishes the amended evaluation trigger as the **earliest of `active_days >= 60` or `2027-10-26`**; PASS rule criteria remain unchanged; status prior to trigger is strictly `INCONCLUSIVE`.

9. **Validation & Logging Fixes Documented (9.4):** `enforce_geometry_invariants` and resolver trailing stop isolation are verified as data validation/logging infrastructure fixes that introduce zero parameter changes. Forward evaluation script [`scripts/evaluate_forward.py`](file:///c:/Users/Admin/Trading%20Bot%20app/scripts/evaluate_forward.py) reports results with and without rejected would-be setups ($n=0$ post-freeze).

10. **Absolute Code Freeze Enacted (9.5):** CI guard [`backend/scripts/test_code_freeze_guard.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_code_freeze_guard.py) enforces 100% parameter invariance and verifies the cryptographic amendment hash (`1f3127b3...`). Zero further code changes permitted until the evaluation trigger fires.

---

## 9.1 Plain Counts & Discrepancy Reconciliation

Forensic verification of distinct UTC calendar trading dates, trades per active day, and resolution of historical reporting discrepancies:


### Plain Counts Overview & Monthly Breakdown

> **Query ID:** `Q_P9_PLAIN_COUNTS_OVERVIEW` | **Row Count:** `6` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Evaluation Cohort / Period | Aggregator (Distinct UTC Dates / Count) | Active Trading Days (active_days) | Total Unique Trades (n_trades) | Mean Trades / Day | Median Trades / Day | Max Trades / Day | Cohort Scope & Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Overall Crypto Core 4h Long Ledger | Distinct UTC Dates / Count | 26 | 156 | 6.00 | 2.5 | 32 | Full historical ledger (all unique crypto core_4h_long) |
| Calendar Month: 2026-07 | Monthly Slice / Daily Count | 8 | 110 | 13.75 | 10.5 | 32 | July launch volume cluster (peak day 2026-07-15: 32 trades) |
| Calendar Month: 2026-08 | Monthly Slice / Daily Count | 3 | 4 | 1.33 | 1.0 | 2 | August low-volatility lull |
| Calendar Month: 2026-09 | Monthly Slice / Daily Count | 9 | 23 | 2.56 | 1.0 | 6 | September steady scanning volume |
| Calendar Month: 2026-10 (Pre-Freeze) | Monthly Slice / Daily Count | 6 | 19 | 3.17 | 2.0 | 8 | October pre-freeze activity (up to 2026-10-23) |
| Window 2026-07-01..2026-10-23 | Canonical Filter Window | 26 | 156 | 6.00 | 2.5 | 32 | Pre-registered evaluation baseline (all trades within window) |

### Reconciliation of Stated Discrepancies

> **Query ID:** `Q_P9_DISCREPANCY_RECONCILIATION` | **Row Count:** `6` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Forensic Discrepancy Case | Aggregator (Forensic SQL Dissection) | Stated / Audit Figure | Verified True Figure | Reconciled Causal Mechanism | Verification Query / Protocol |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Active Days: Phase 8 Stated (19) | Intersection of Parquet Cache | 19 days | 26 true days | 7 ledger trade dates in altcoins omitted from top-50 parquet cache | Parquet cache intersection |
| Active Days: Phase 7 Stated (48) | Author Transcription Inadvertence | 48 days | 26 true days | Mistook TIMEOUT_BARS=48 (trade duration limit) for calendar days | SELECT count(distinct as_of::date) |
| True Active Days (Ledger Canonical) | Strict UTC Calendar Date Aggregator | 26 days | 26 true days | Canonical integer degrees of freedom across 156 unique trades | SELECT count(distinct (as_of at time zone 'UTC')::date) |
| Mutated Stops: Phase 8 Count (357) | Trailing Stop Update Filter | 357 rows | 357 rows | Signals where trailing_stop IS NOT NULL from resolver updates | SELECT count(*) FILTER (WHERE trailing_stop IS NOT NULL) |
| Mutated Stops: Stop != Initial (328/330) | Inequality Filter to Initial | 328 rows | 328 rows | Initial stop differed from final stop (was 330 before PEPE initial_stop fix) | SELECT count(*) FILTER (WHERE stop != initial_stop) |
| Mutated Stops: Trailing == Initial (29) | Equality Invariant Filter | 29 rows | 29 rows | Trailing stop ratcheted to exactly equal initial_stop (328 + 29 = 357) | SELECT count(*) FILTER (WHERE trailing_stop = initial_stop) |

### Single-Query Resolution of Mutated Stops (357 vs 330/328)

> **Query ID:** `Q_P9_MUTATED_STOPS_RESOLUTION` | **Row Count:** `1` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Database Table | Aggregator (SQL Conditional FILTER) | Total Signals | Trailing Stop Set (Mutated) | Stop != Initial Stop | Trailing Stop == Initial Stop | Single-Query Reconciliation Identity |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| signals (Production Table) | SQL Conditional FILTER Aggregator | 1,146 | 357 | 328 | 29 | Reconciled: 328 (stop!=initial) + 29 (stop==initial) = 357 mutated |

```sql

-- Canonical Single SQL Query Resolving Mutated Stop Counts

SELECT 

    count(*) as total_signals,

    count(*) FILTER (WHERE trailing_stop IS NOT NULL) as total_mutated_signals,

    count(*) FILTER (WHERE stop != initial_stop) as stops_different_from_initial,

    count(*) FILTER (WHERE trailing_stop IS NOT NULL AND stop = initial_stop) as mutated_but_trailing_equals_initial

FROM signals;

-- Output: total=1,146 | total_mutated=357 | stop!=initial=328 | trailing==initial=29

```


- **Retirement of $N_{\text{eff}}$:** Because effective sample size metrics evaluated in Phases 6–8 varied by over an order of magnitude (111.7 under Kish autocorrelation vs 9 under Herfindahl cluster variance vs 48 under duration confusion), $N_{\text{eff}}$ is permanently retired from forward decision rules and reports. From now on, every forward report states `active_days` (distinct UTC calendar dates with $\ge 1$ unique trade) and `n_trades`.


## 9.2 Statistical Power Table & Scaling Simulation

Using the corrected ledger (156 trades, mean $+0.4076$ R, sum $+63.5920$ R, $K=26$ observed days, $\bar{n}=6.00$ trades/day, daily sum standard deviation $\sigma_S = 10.0099$, day-level return standard deviation $\sigma_{\text{day}} = \sigma_S / \bar{n} = 1.6683$ R):


$$\text{Standard Error of the Mean: } \mathrm{SE}(K) = \frac{\sigma_{\text{day}}}{\sqrt{K}} = \frac{\sigma_S / \bar{n}}{\sqrt{K}} = \frac{1.6683}{\sqrt{K}}$$


A candidate strategy satisfies the pre-registered PASS rule if and only if:

1. Sample Mean Net $R \ge +0.1500$ R

2. 95% Day-Block Bootstrap Lower Bound $> 0.0000$ R ($1.96 \times \mathrm{SE} < \mathrm{Mean}$)

3. Top-5 positive trades contribute $\le 20.0\%$ of positive R sum


### Statistical Power & Detection Probabilities (10,000 Resamples)

> **Query ID:** `Q_P9_POWER_TABLE` | **Row Count:** `4` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Active Days (K) | Aggregator (Day-Block Resample B=10,000) | Standard Error (SE) | Min Mean for PASS | P(PASS | mu=0.0) | P(PASS | mu=+0.1) | P(PASS | mu=+0.2) | P(PASS | mu=+0.4) | Statistical Power Assessment |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| K = 28 Active Days | Day-Block Resample (B=10,000) | 0.3153 R | +0.6180 R | 0.9% | 2.4% | 4.9% | 14.9% | Severe underpower: only 14.9% chance of PASS even at true +0.40R |
| K = 45 Active Days | Day-Block Resample (B=10,000) | 0.2487 R | +0.4875 R | 1.3% | 4.1% | 9.2% | 30.5% | Sub-critical power: 30.5% detection probability at +0.40R |
| K = 60 Active Days (Trigger) | Day-Block Resample (B=10,000) | 0.2154 R | +0.4221 R | 1.3% | 5.1% | 12.9% | 45.3% | Pre-Registration Amendment 1 trigger: 45.3% power, Type I error strictly <= 1.3% |
| K = 90 Active Days | Day-Block Resample (B=10,000) | 0.1759 R | +0.3447 R | 1.3% | 7.3% | 21.7% | 68.6% | High power benchmark: 68.6% detection probability at +0.40R |

- **Power Evaluation:** At $K=28$ days, the test is severely underpowered ($14.9\%$ probability of passing even if the strategy's true mean is $+0.40$ R). Setting the evaluation horizon trigger to $K=60$ active days ensures that standard error decreases to $0.2154$ R, detection power triples to $45.3\%$ (reaching $68.6\%$ at 90 days), while false discovery under the null hypothesis ($\mu = 0.0$ R) remains strictly controlled at $1.3\%$.


## 9.3 Pre-Registration Amendment 1 Specification

Formal research amendment executed prior to any forward data evaluation:


### Pre-Registration Amendment Specification Matrix

> **Query ID:** `Q_P9_AMENDMENT_SPECIFICATION` | **Row Count:** `1` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Governance Artifact | Aggregator (SHA-256 Bitwise Digest) | Effective Timestamp | Amended Evaluation Trigger | Pre-Registered PASS Rule | Operational Status Prior to Trigger | Cryptographic Artifact Hash |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| docs/PRE_REGISTRATION_AMENDMENT.md | Cryptographic SHA-256 Digest | 2026-10-27T10:00:00Z | Earliest of active_days >= 60 or 2027-10-26 | Mean >= +0.15R & 95% CI > 0 & Top-5 <= 20% | INCONCLUSIVE (Strictly No Interim Decisions) | 1f3127b3eca41dd45db275bc66dad1b45fc2f4ce8805d636afc9b336e04ecd92 |

- **Governance Rules Maintained:**

  - **Evaluation Trigger:** Earliest of `active_days >= 60` or `2027-10-26`.

  - **PASS Rule Unchanged:** Mean $\ge +0.15$ R, 95% Day-Block CI lower $> 0$, Top-5 share $\le 20%$.

  - **Interim Decisions Strictly Prohibited:** Pipeline outputs exclusively `STATUS: INCONCLUSIVE` prior to the trigger.

  - **Timing Only:** Zero changes to signal parameters, indicators, weights, or entry/exit models.

  - **Cryptographic Hash Lock:** `test_code_freeze_guard.py` enforces bitwise match of `docs/PRE_REGISTRATION_AMENDMENT.md` hash (`1f3127b3...`).


## 9.4 Validation & Logging Fixes Audit

Verification that data hygiene and logging changes are infrastructure fixes that preserve strategy parameter invariance:


### Infrastructure Fix Classification Matrix

> **Query ID:** `Q_P9_VALIDATION_FIXES_AUDIT` | **Row Count:** `3` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Hardened Component | Aggregator (Validation Classification) | Nature of Change | Parameter Invariance Impact | Governance Standard Enforced | Tracking & Reporting Channel | Compliance & Verification Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| enforce_geometry_invariants | Validation Filter & Invariant Gate | Validation / Logging | Zero parameter mutation (freeze hash 3fae909f... intact) | Invariants 1-7 (stops, targets, bounds) | docs/FORWARD_LOG.md weekly rejection counts | Enforced behind flag (0 rejected post-freeze) |
| Resolver Stop Immutability | Column Isolation & Schema Migration | Validation / Logging | Zero parameter mutation (freeze hash 3fae909f... intact) | Initial risk denominator immutability | signals.trailing_stop separate from initial_stop | Fully deployed (Migration 013 verified) |
| Forward Evaluation Invariant Logging | Conditional Cohort Aggregator | Validation / Logging | Zero parameter mutation (freeze hash 3fae909f... intact) | Reports with & without rejected setups | scripts/evaluate_forward.py output | Active (identical performance: 0 rejected) |

- **Weekly Invariant Rejection Tracking:** Added weekly rejected setup tracking to [`docs/FORWARD_LOG.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/FORWARD_LOG.md). Over weeks 2026-W43 and 2026-W44, exactly **0 setups** have been rejected post-freeze.

- **Reconstructed Forward Performance:** [`scripts/evaluate_forward.py`](file:///c:/Users/Admin/Trading%20Bot%20app/scripts/evaluate_forward.py) reports forward performance both with and without setups rejected by `enforce_geometry_invariants`. With 0 post-freeze rejections to date, both cohorts are identical ($n=0$, Mean $R=+0.0000$ R).


## 9.5 Absolute Code Freeze & Live Lock Handover

With Phase 9 complete, all development, tuning, and report generation scripts are permanently locked:

- **Signal Freeze Hash:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` verified by CI.

- **Amendment Hash:** `1f3127b3eca41dd45db275bc66dad1b45fc2f4ce8805d636afc9b336e04ecd92` verified by CI.

- **Live Lock:** `live_trading_enabled = False` permanently locked (Rule R4).

- **Evaluation Protocol:** Strictly no code changes until the evaluation trigger fires (`active_days >= 60` or `2027-10-26`).


```

====================================================================================

PHASE 9 COMPLETE — PRE-REGISTRATION AMENDMENT RATIFIED & LOCKED

FORWARD EVALUATION TRIGGER: EARLIEST OF (ACTIVE_DAYS >= 60) OR (2027-10-26)

CURRENT OPERATIONAL STATUS: >>> INCONCLUSIVE (LOG-ONLY OBSERVATION ACTIVE) <<<

====================================================================================

```
