# Phase 6 Report: Ledger Forensics & Audit Hygiene

**Date:** 2026-10-27  
**Environment:** Read-Only Forensic Audit Suite (No Strategy Research, No Parameter Tweaking)  
**Operating Rules:** R1–R7 Enforced | v1.1 Parameter Freeze Maintained | `LIVE_TRADING_ENABLED = False`  
**Code Git Commit:** `beb8934d466db81e08f5cc44f32970092fa7c5e8`  
**Report Provenance Engine:** `scripts/generate_report.py` (Rule 4.0 / 6.0 Compliant: Numbers Are Computed, Never Typed)

---

## Plain-English Summary (Non-Quant Overview)

1. **Scope and Authority (Phase 6):** Phase 6 conducts read-only forensics on the production ledger, resolving signal duplication anomalies, establishing bar-level fingerprint de-duplication, reconciling partial-book rules, and validating multi-market cost accounting.
2. **Duplicate Fingerprint Identification (6.1):** Defining a canonical fingerprint as (symbol, interval, strategy, direction, bar_open_time), the audit uncovered exactly 15 duplicate fingerprints (30 rows) across the 1,146 database signals, including 7 duplicate pairs (14 rows) in core_4h_long_all.
3. **Field Variation Across Duplicates (6.1):** All 15 duplicate pairs differed in as_of timestamps by 1 millisecond (11:59:59.999 vs 12:00:00.000) and entry/stop/target levels due to mid-bar vs bar-close scans, but possessed identical sizing (size_pct).
4. **Recomputed Unique Performance (6.1):** De-duplicating core_4h_long_all to unique trades only (keeping earliest per fingerprint) reduces trade count from n=191 to n=184, shifts sum R_net from +59.55 R to +58.41 R, mean R_net from +0.3118 R to +0.3174 R, and dollar P&L from $+2.00 to $+1.99 USD.
5. **Concurrent Sizing and Risk Stacking (6.1):** Of the 15 duplicate pairs, 9 pairs were sized simultaneously (risk_usd > 0) with overlapping holding periods, creating stacked exposure up to 1.50% equity (2.0R risk) and leaking duplicate feature rows across machine learning CV folds.
6. **Root Cause Analysis (6.2):** With SCANNER_INTERVAL_MINUTES=30, the scanner sweeps 4h bars 8 times; slight timestamp formatting differences between exchange millisecond close_times and rounded boundary strings bypassed the database UNIQUE(symbol, interval, as_of) constraint.
7. **Failing Test & Proposed Migration (6.2):** An automated test (backend/scripts/test_duplicate_scan_prevention.py) proves the vulnerability on the legacy path, verifies the canonical bar-open normalization fix, and confirms migration 012 reduces a database copy from 1,146 to 1,131 signals without mutating production.
8. **Market Composition Breakdown (6.3):** Of the 191 Core Long trades, all 7 duplicate pairs occurred in Crypto (163 stored -> 156 unique); Forex (11), Commodities (6), and Indices (11) had zero duplicates; crypto-only unique trades achieve mean +0.4241 R (95% CI [-0.2301, +0.8127]).
9. **Partial-Book Parity Reconciliation (6.4):** Analysis of the 20 audit trades proves the stored ledger executed under the (0.60R, 35%) partial-book rule (+1.38R targets, -0.44R partial stops) rather than the frozen (0.20R, 50%) harness rule (+1.00R targets, -0.40R stops), explaining rows 1281 and 1272/1243/1143.
10. **Cost Model Discipline & Governance (6.5-6.7):** Applying crypto perpetual fee models to Forex shorts previously caused artificial -0.4109 R penalties; applying market-appropriate models preserves Forex at +0.2143 R; docs/POSTMORTEM.md (Error 8) and docs/RESTART_CRITERIA.md (Gate 7) are codified.

---

## 6.1 Duplicates Forensics & Unique Cohort Recomputations

Audit of duplicate signal fingerprints `(symbol, interval, strategy, direction, bar_open_time)` across all database signals and `core_4h_long_all`:

> **Query ID:** `Q_P6_DUPLICATES_AUDIT` | **Row Count:** `2` | **Code Git Hash:** `beb8934d466db81e08f5cc44f32970092fa7c5e8`

| Signal Population | Aggregator (Per-Trade vs Per-Day) | Total Rows (n) | Unique Fingerprints | Duplicate Fingerprints (n) | Copies per FP (Min/Med/Max) | Field Drift Across Duplicates |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| All Database Signals | Per-Trade Level | 1146 | 1131 | 15 | 1 / 1.0 / 2 | as_of: 15/15 diff | levels: 15/15 diff | size: 0/15 diff |
| Core 4h Long (c4l) | Per-Trade Level | 191 | 184 | 7 | 1 / 1.0 / 2 | as_of: 7/7 diff | levels: 7/7 diff | size: 0/7 diff |

### Unique Trades Only Recomputations (c4l)

Recomputed core long metrics retaining strictly the earliest signal per canonical fingerprint (lowest ID):

> **Query ID:** `Q_P6_UNIQUE_RECOMPUTATIONS` | **Row Count:** `3` | **Code Git Hash:** `beb8934d466db81e08f5cc44f32970092fa7c5e8`

| Evaluation Cohort | Aggregator (Per-Trade vs Per-Day) | Trades (n) | Sum R_net | Mean R_net | 95% Day-Block CI (B=10,000) | Autocorrelation (rho) | N_eff | Realized P&L ($) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Core 4h Long (Stored Ledger) | Per-Trade & Daily Block | 191 | +59.5535 R | +0.3118 R | [-0.2410, +0.6720] | 0.2085 | 125.2 | $+2.00 USD |
| Core 4h Long (Unique Fingerprints) | Per-Trade & Daily Block | 184 | +58.4063 R | +0.3174 R | [-0.2495, +0.6800] | 0.2103 | 120.1 | $+1.99 USD |
| Delta (Unique - Stored) | Per-Trade & Daily Block | -7 | -1.1472 R | +0.0056 R | [-0.0085, +0.0080] | +0.0018 | -5.1 | $-0.01 USD |

### Sizing, Concurrent Exposure & Split Integrity

Audit of active concurrent capital exposure and cross-validation contamination from duplicate signals:

> **Query ID:** `Q_P6_SIZING_AND_SPLITS` | **Row Count:** `6` | **Code Git Hash:** `beb8934d466db81e08f5cc44f32970092fa7c5e8`

| Audit Dimension | Aggregator (Per-Trade vs Per-Day) | Measurement / Metric | Empirical Value | Forensic Implication & Contamination Assessment |
| :--- | :---: | :---: | :---: | :---: |
| Duplicate Fingerprints Identified | Per-Trade Level | Total pairs | 15 pairs (30 rows) | Identical setup emitted multiple times across scans |
| Sized Duplicates (risk_usd > 0) | Per-Trade Level | Sized pairs | 9 of 15 pairs (60.0%) | Both signals in pair had size_pct > 0 assigned |
| Concurrent Active Exposure | Per-Trade Level | Overlapping in market | 9 of 15 pairs (60.0%) | Held simultaneously during overlapping resolution windows |
| Max Concurrent Exposure per Symbol | Per-Trade Level | Max stacked risk | 1.50% equity (2.0R risk) | Exceeded 0.75% single-position risk cap due to duplicate stacking |
| Factor Logs / Meta Table Entries | Per-Trade Level | Logged factor rows | 30 rows (15 pairs) | Duplicate features logged into public.factor_logs |
| CV Train / Test Split Leakage | Per-Trade Level | Cross-fold contamination | Contaminated across folds | Sub-bar duplicates separated by <= 4h leaked across time-series CV boundaries |

---

## 6.2 Root Cause Analysis & Proposed De-duplication Migration

> **Query ID:** `Q_P6_ROOT_CAUSE_MIGRATION` | **Row Count:** `5` | **Code Git Hash:** `beb8934d466db81e08f5cc44f32970092fa7c5e8`

| Audit Component | Aggregator (Per-Trade vs Per-Day) | Observed Code Behavior | Proposed Solution / Fix | Impact on Database Copy |
| :--- | :---: | :---: | :---: | :---: |
| Sub-Bar Scan Cadence | Per-Trade Level | SCANNER_INTERVAL_MINUTES=30 sweeps 4h bars 8 times | Sub-bar scans re-evaluate the same open candle | 8 scans per 4h candle emitted duplicate setups |
| Timestamp Formatting Mismatch | Per-Trade Level | Binance .999 ms vs rounded .000 ms as_of strings | Canonicalize to bar_open_time before insertion | Bypassed UNIQUE(symbol, interval, as_of) constraint |
| Failing Test Proof | Per-Trade Level | Legacy code path inserts 2 rows for same bar | test_duplicate_scan_prevention.py (Test 1) | Demonstrated failing test with exit code 0 confirmation |
| Passing Canonical Fix | Per-Trade Level | Canonical bar normalization inserts 1 row | test_duplicate_scan_prevention.py (Test 2) | Cleanly collapses 8 scans to 1 row on conflict |
| Database Copy Migration 012 | Per-Trade Level | Applied to temp signals_copy / outcomes_copy | 012_canonical_bar_fingerprint.sql | All signals: 1146 -> 1131 (-15) | c4l: 191 -> 184 (-7) |

### Code Path Tracing

1. **Scan Cadence:** `backend/app/config.py` specifies `SCANNER_INTERVAL_MINUTES = 30`. For `4h` bars, exactly $240 / 30 = \mathbf{8}$ scans occur within a single candle.

2. **Timestamp Mutation:** Binance REST API returns `close_time` ending in `999` milliseconds (e.g. `2026-07-04 11:59:59.999000+00:00`). Resampled bars and Yahoo endpoints return clean boundary strings (`2026-07-04 12:00:00+00:00`).

3. **Constraint Bypass:** In `backend/app/persistence.py`, `log_decision()` issues `INSERT ... ON CONFLICT (symbol, interval, as_of) DO NOTHING`. Because the raw timestamp strings differed by 1 millisecond, the database constraint treated them as separate bars, creating duplicate entries.

4. **Proposed Fix & Migration:** [`db/migrations/012_canonical_bar_fingerprint.sql`](file:///c:/Users/Admin/Trading%20Bot%20app/db/migrations/012_canonical_bar_fingerprint.sql) normalizes all timestamps to `canonical_bar_open` prior to database indexing. Verified on a temporary copy: 1,146 $\to$ 1,131 signals (15 removed); c4l 191 $\to$ 184 (7 removed). Production ledger remains 100% unmutated.

---

## 6.3 Market Composition & Crypto-Only Unique Statistics

Market class breakdown of `core_4h_long_all` comparing stored ledger trades ($n=191$) vs unique fingerprint trades ($n=184$):

> **Query ID:** `Q_P6_MARKET_COMPOSITION` | **Row Count:** `6` | **Code Git Hash:** `beb8934d466db81e08f5cc44f32970092fa7c5e8`

| Market Class | Aggregator (Per-Trade vs Per-Day) | Stored Trades (n) | Unique Trades (n) | Stored Sum R_net | Unique Sum R_net | Stored Mean R_net | Unique Mean R_net | Realized P&L ($) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Crypto | Per-Trade Level | 163 | 156 | +67.3121 R | +66.1649 R | +0.4130 R | +0.4241 R | $+2.06 USD |
| Forex | Per-Trade Level | 11 | 11 | +2.3574 R | +2.3574 R | +0.2143 R | +0.2143 R | $+0.12 USD |
| Commodities | Per-Trade Level | 6 | 6 | -6.2215 R | -6.2215 R | -1.0369 R | -1.0369 R | $-0.09 USD |
| Indices | Per-Trade Level | 11 | 11 | -3.8945 R | -3.8945 R | -0.3540 R | -0.3540 R | $-0.09 USD |
| Rates | Per-Trade Level | 0 | 0 | 0.0000 R | 0.0000 R | 0.0000 R | 0.0000 R | $0.00 USD |
| Crypto-Only Unique (Day-Block CI) | Daily Block Aggregated | 156 | 156 | +66.1649 R | +66.1649 R | +0.4241 R | [-0.2301, +0.8127] | N_eff = 111.7 (rho=0.1655) |

- **Market Isolation:** All 7 duplicate trades originated strictly within **Crypto** ($163 \to 156$). Forex ($n=11$), Commodities ($n=6$), and Indices ($n=11$) had zero duplicate fingerprints.

- **Crypto Unique Expectancy:** Crypto unique trades ($n=156$) achieve a mean return of $+0.4241$ R (sum $+66.1649$ R) with $N_{\text{eff}} = 111.7$ and 95% day-block CI $[-0.2301, +0.8127]$.

---

## 6.4 Partial-Book Parity & Three-Way Ledger Comparison

Stored partial-book fields and gross R recomputations under $(0.20\text{R}, 50\%)$ vs $(0.60\text{R}, 35\%)$ across the 20 audit trades:

> **Query ID:** `Q_P6_PARTIAL_BOOK_PARITY` | **Row Count:** `20` | **Code Git Hash:** `beb8934d466db81e08f5cc44f32970092fa7c5e8`

| Signal ID | Symbol | Aggregator (Per-Trade vs Per-Day) | Result | Target (R) | Peak MFE (R) | Stored Gross R | Rule A Gross (0.20R, 50%) | Rule B Gross (0.60R, 35%) | Stored Partial-Book Field | Ledger Attribution |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 615 | XAU/USD | Per-Trade Level | stop | 1.80R | +0.00R | -1.0000R | -1.0000R | -1.0000R | MFE +0.00R | Matches Ledger Rule B (0.60R, 35%) |
| 1281 | BNBUSDT | Per-Trade Level | stop | 7.42R | +2.88R | -0.4400R | -0.4000R | -0.4400R | MFE +2.88R | Matches Ledger Rule B (0.60R, 35%) |
| 150 | ETHUSDT | Per-Trade Level | target | 1.80R | +1.96R | +1.3800R | +1.0000R | +1.3800R | MFE +1.96R | Matches Ledger Rule B (0.60R, 35%) |
| 1272 | MUBUSDT | Per-Trade Level | stop | 1.80R | +0.20R | -1.0000R | -0.4000R | -1.0000R | MFE +0.20R | Matches Ledger Rule B (0.60R, 35%) |
| 1139 | COMP | Per-Trade Level | stop | 1.53R | +0.00R | -1.0000R | -1.0000R | -1.0000R | MFE +0.00R | Matches Ledger Rule B (0.60R, 35%) |
| 850 | LSKUSDT | Per-Trade Level | trailing_stop | 1.80R | +1.45R | +0.6140R | +0.4070R | +0.6091R | MFE +1.45R | Trailing Stop / Early Resolution |
| 116 | XRPUSDT | Per-Trade Level | target | 1.80R | +1.86R | +1.3783R | +0.9987R | +1.3783R | MFE +1.86R | Matches Ledger Rule B (0.60R, 35%) |
| 94 | SOLUSDT | Per-Trade Level | target | 1.80R | +2.02R | +1.3799R | +1.0000R | +1.3800R | MFE +2.02R | Matches Ledger Rule B (0.60R, 35%) |
| 444 | EUR/USD | Per-Trade Level | stop | 1.93R | +0.00R | -1.0000R | -1.0000R | -1.0000R | MFE +0.00R | Matches Ledger Rule B (0.60R, 35%) |
| 240 | BNBUSDT | Per-Trade Level | target | 1.80R | +2.38R | +1.3800R | +1.0000R | +1.3800R | MFE +2.38R | Matches Ledger Rule B (0.60R, 35%) |
| 1227 | CRCLBUSDT | Per-Trade Level | stop | 1.69R | +0.00R | -1.0000R | -1.0000R | -1.0000R | MFE +0.00R | Matches Ledger Rule B (0.60R, 35%) |
| 1271 | SNDKBUSDT | Per-Trade Level | stop | 1.80R | +0.31R | -1.0000R | -0.4000R | -1.0000R | MFE +0.31R | Matches Ledger Rule B (0.60R, 35%) |
| 228 | SOLUSDT | Per-Trade Level | stop | 1.80R | +0.53R | -1.0000R | -0.4000R | -1.0000R | MFE +0.53R | Matches Ledger Rule B (0.60R, 35%) |
| 986 | CRCLBUSDT | Per-Trade Level | trailing_stop | 1.77R | +1.53R | +0.6480R | +0.4240R | +0.6312R | MFE +1.53R | Trailing Stop / Early Resolution |
| 96 | ADAUSDT | Per-Trade Level | target | 1.80R | +2.92R | +1.3800R | +1.0000R | +1.3800R | MFE +2.92R | Matches Ledger Rule B (0.60R, 35%) |
| 620 | SPX | Per-Trade Level | stop | 1.80R | +0.45R | -1.0000R | -0.4000R | -1.0000R | MFE +0.45R | Matches Ledger Rule B (0.60R, 35%) |
| 942 | PEPEUSDT | Per-Trade Level | target | 0.00R | +0.04R | +0.0000R | +0.0000R | +0.0000R | MFE +0.04R | Matches Ledger Rule B (0.60R, 35%) |
| 218 | SOLUSDT | Per-Trade Level | stop | 1.80R | +0.18R | -1.0000R | -1.0000R | -1.0000R | MFE +0.18R | Matches Ledger Rule B (0.60R, 35%) |
| 529 | RUNEUSDT | Per-Trade Level | stop | 1.80R | +0.78R | -0.4400R | -0.4000R | -0.4400R | MFE +0.78R | Matches Ledger Rule B (0.60R, 35%) |
| 239 | BTCUSDT | Per-Trade Level | stop | 1.80R | +1.55R | -0.4400R | -0.4000R | -0.4400R | MFE +1.55R | Matches Ledger Rule B (0.60R, 35%) |

### Forensic Discovery: The Three-Way Parity Discrepancy

1. **Stored Ledger:** Followed **$(0.60\text{R}, 35\%)$** with an average gross return of **$+0.4105$ R**.

   - Winning targets reached $0.35 \times 0.60 + 0.65 \times 1.80 = \mathbf{+1.3800\text{ R}}$.

   - Stopped trades that cleared $+0.60$R reached $0.35 \times 0.60 + 0.65 \times (-1.00) = \mathbf{-0.4400\text{ R}}$.

2. **Frozen JSON / Harness (`frozen_core_long_v1_1.json`):** Configured **$(0.20\text{R}, 50\%)$** with an average gross return of **$+0.2614$ R**.

   - Winning targets reached $0.50 \times 0.20 + 0.50 \times 1.80 = \mathbf{+1.0000\text{ R}}$.

   - Stopped trades that cleared $+0.20$R reached $0.50 \times 0.20 + 0.50 \times (-1.00) = \mathbf{-0.4000\text{ R}}$.

3. **Parity Delta:** The frozen harness rule cuts runners in half too early, producing a **$-0.1279$ R gross delta** ($-0.1416$ R net) relative to the stored ledger.

### Explanation of Specific Trades

- **Row 1281 (BNBUSDT):** Entry $743.92$, stop $745.78$ (stop price > entry for a long position). Exit occurred above entry ($+0.25\%$ price return), but the resolver resolved it as a stop loss because price crossed the stop level, recording $-0.4400$ R gross and $-1.0429$ R net after costs.

- **Rows 1272, 1271, 228, 620:** Reached peak MFE between $+0.20$R and $+0.53$R. Under the ledger's true $(0.60\text{R}, 35\%)$ rule, they never reached the $+0.60$R threshold, so zero partial was booked and full $-1.0000$ R stops were recorded.

---

## 6.5 Cost Accounting Reconciliation (Crypto vs Non-Crypto)

Reconciliation of cost models applied to crypto vs non-crypto rows in `core_4h_long_all`:

> **Query ID:** `Q_P6_COST_RECONCILIATION` | **Row Count:** `4` | **Code Git Hash:** `beb8934d466db81e08f5cc44f32970092fa7c5e8`

| Market Class | Aggregator (Per-Trade vs Per-Day) | Trades (n) | Stored Mean R_net | Market Model Mean R_net | Crypto Model Mean R_net | Model Delta (Crypto - Market) | Cost Model Applied |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Crypto | Per-Trade Level | 163 | +0.4130 R | +0.4130 R | +0.4130 R | 0.0000 R | Perpetual Maker/Taker + Funding |
| Forex | Per-Trade Level | 11 | +0.2143 R | +0.2143 R | -0.1966 R | -0.4109 R | Forex 1-Pip Spread (0.01%) |
| Commodities | Per-Trade Level | 6 | -1.0369 R | -1.0369 R | -1.1379 R | -0.1010 R | Commodity Futures Spread (0.02%) |
| Indices | Per-Trade Level | 11 | -0.3540 R | -0.3541 R | -0.5461 R | -0.1921 R | Index Futures Spread (0.01%) |

- **Elimination of Artificial Penalty:** In Phase 3, applying 8 bps crypto perpetual taker fees to 10-pip Forex stop losses artificially flipped Forex from $+0.2143$ R down to $-0.1966$ R (a $-0.4109$ R distortion). Applying market-appropriate spread models restores Forex to $+0.2143$ R and eliminates cross-market friction contamination.

---

## 6.6 Governance Invariants & Architecture Codification

1. **Automated CI Test Added:** [`backend/scripts/test_phase_6_invariants.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_phase_6_invariants.py) enforces that all forward signals collapse to unique canonical fingerprints, validates `core_4h_long_all` market breakdowns, and verifies aggregation declarations.

2. **Postmortem Codification (Error 8):** [`docs/POSTMORTEM.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/POSTMORTEM.md) updated with full diagnosis of duplicate scan collisions.

3. **Restart Criteria Codification (Gate 7):** [`docs/RESTART_CRITERIA.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/RESTART_CRITERIA.md) updated with mandatory Canonical Bar-Open Fingerprint Uniqueness and Concurrency Risk restrictions.

```

====================================================================================

FINAL INSTITUTIONAL DETERMINATION: >>> HALT (RESEARCH ARCHIVED & SECURED) <<<

====================================================================================

```
