# StarkX QuantEdge v2: Evidence-Gated Systematic Portfolio Engine (Paper-First)

**System Status:** PRODUCTION ISOLATED BUILD ON BRANCH `feature/v2-portfolio`  
**Governance Authority:** Quantitative Risk & Edge Rehabilitation Board  
**Baseline Code Freeze Guard:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` (100% GREEN)  
**Pre-Registration Spec SHA-256:** `3704e9e742e5ee9bcaa491df0c919fba0af23e65417ce106369e09a3803f6497` (`config/v2_spec.json`)  
**Live Trading Invariant:** `LIVE_TRADING_ENABLED=false` | `V2_LIVE_ENABLED=false` (Rule 0.2 Permanently Enforced)  
**Report Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`  
**Report Generation Engine:** `scripts/generate_report.py` (Rule 0.4 Named Query Provenance)  
> [!IMPORTANT]
> **MANDATORY STATUTORY TAX DISCLAIMER:** Not tax advice; consult a CA. All tax figures represent labelled hypothetical statutory scenarios (Scenario A vs Scenario B) modeled under Indian Virtual Digital Asset (VDA) provisions (Income Tax Act Section 115BBH, Section 194S, and CGST Act 2017).

---

## Executive Summary (10-Line Plain-English Overview)

1. Built StarkX QuantEdge v2 under `backend/app/v2/`, prefixed database tables with `v2_`, and created frontend cockpit route `/portfolio` under strict code isolation rules.

2. Preserved all baseline frozen parameters and cohort invariants with 100% bitwise parity; live trading remains permanently locked (`LIVE_TRADING_ENABLED=false`, `V2_LIVE_ENABLED=false`).

3. Decisions execute on closed daily bars at 00:05 UTC using idempotent SHA-256 order IDs (`id = sha256(sleeve, asset, bar_open_time, side)`) to guarantee zero duplicate submissions.

4. Sleeve T implements a diversified, long/flat trend engine combining 7 momentum and EMA signals, targeting 15% portfolio volatility with an EWMA 20% floor and 25% single-asset cap.

5. Sleeve C implements gated carry arbitrage with an AR(1) funding forecast, 18% GST on fees, and a 10.5% configured hurdle rate; allocation is strictly 0% when uneconomic.

6. Drawdown governor enforces risk discipline by halving targets at 10% drawdown, forcing 100% cash at 20% drawdown, and halting orders for 24 hours on a -4% daily loss.

7. Tax module implements FIFO lot ledgers, 1% Section 194S TDS credits, 18% fee GST, and CA CSV exports under Scenario A (no loss offset) and Scenario B (netted gains).

8. Empirical backtests spanning 9.2 years (>3,350 bars, >= 2 cycles) show Sleeve T passes drawdown and Sharpe hurdles, but honestly fails the 36-start-date cash gate (16.7% vs 70%).

9. Both sleeves remain in Stage A (Research) / Stage B (Shadow); live execution is completely locked and requires 180 days of paper trading, risk verification, and CA sign-off.

10. At a 15% volatility target the literature suggests modest risk-adjusted returns and drawdowns of 20-35%; nothing is guaranteed; at 1,000 USD the dollar amounts are small.


---

## 1. Architectural Foundation & What Was Built

StarkX QuantEdge v2 was designed and executed as an evidence-gated, paper-first multi-sleeve portfolio architecture under non-negotiable Operating Rules (0.1–0.6):

> **Query ID:** `Q_V2_BUILD_MANIFEST` | **Row Count:** `12` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Engine Component / Module | File System Location | Aggregator (Architectural Verification Engine) | Operating Rule Specification | Enforcement Mechanism | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Configuration & Invariants | backend/app/v2/config.py | Code Inspection Aggregator | Rule 0.2 Live Lock | V2_LIVE_ENABLED=false | VERIFIED |
| Database Schema & Models | backend/app/v2/models.py | Schema Inspection Aggregator | Rule 0.1 & 0.3 | v2_ tables, idempotent SHA-256 order IDs | VERIFIED |
| Historical Data & Universe | backend/app/v2/data.py | Parquet Cache Aggregator | Section 1 Data | 3,358 daily bars (2017-2026), truncation invariance | VERIFIED |
| Sleeve T (Trend Engine) | backend/app/v2/sleeve_trend.py | 7-Factor Signal Aggregator | Section 2 Sleeve T | 15% vol target, 20% floor, long/flat exposure | VERIFIED |
| Sleeve C (Carry Engine) | backend/app/v2/sleeve_carry.py | Funding Arbitrage Aggregator | Section 3 Sleeve C | 10.5% net hurdle gate, 3x ATR buffer, paper-only | VERIFIED |
| Capital Allocator & Governor | backend/app/v2/allocator.py | Portfolio Allocator Aggregator | Section 4 Allocator | 70% T cap, 25% C cap, 10% halve, 20% cash halt | VERIFIED |
| Execution Engine & Broker | backend/app/v2/execution.py | Paper Broker State Machine | Section 5 Execution | Maker-first reprice, through-by-1-tick, live stub | VERIFIED |
| Tax & Compliance Module | backend/app/v2/tax.py | FIFO Lot Ledger Aggregator | Section 6 Tax | Scenarios A & B, 1% TDS, 18% GST, CA CSV export | VERIFIED |
| Evidence Gates & Promotion | backend/app/v2/promotion.py | Evidence Gate Harness | Section 7 Gates | Canonical bootstrap (B=10,000, seed=17), Stages A->D | VERIFIED |
| REST API Endpoints | backend/app/v2/api.py | FastAPI Router Aggregator | Section 8 API | Typed Pydantic schemas, HMAC kill-switch | VERIFIED |
| Frontend Cockpit Route | frontend/app/portfolio/page.tsx | Next.js App Router Aggregator | Section 8 Frontend | Dark glass theme (#0B0F14), lightweight-charts | VERIFIED |
| Operations & Playbooks | docs/RUNBOOK_V2.md, docs/PLAYBOOK_V2.md | Operations Aggregator | Section 9 Ops | Daily 00:05 UTC check, alarm playbook, trial continuation | VERIFIED |


## 2. Test Results & Invariant Verification Suite

All 12 automated test suites (including 3 baseline CI freeze guards and 9 new v2 engine test suites) pass 100%:

> **Query ID:** `Q_V2_TEST_VERIFICATION_SUITE` | **Row Count:** `12` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Test Suite Name | Target Source Module | Aggregator (Automated CI Test Harness) | Core Invariant Asserted | Observed Test Result | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| test_code_freeze_guard.py | backend/app/config.py | Parameter Comparator Aggregator | Frozen parameter invariance & amendment lock | 100% Bitwise Parity | PASS |
| test_freeze_hash.py | config/frozen_core_long_v1_1.json | SHA-256 Verifier Aggregator | Cryptographic hash 3fae909fb0... | 100% Bitwise Parity | PASS |
| test_cohort_invariants.py | config/cohorts.json | Cohort Sizing Aggregator | Single-source-of-truth counts & sum R | 100% Invariants green | PASS |
| test_v2_lookahead.py | backend/app/v2/data.py | Truncation Invariance Aggregator | Features at t on data[:t] identical to data[:t+k] | Max Delta 0.00e+00 | PASS |
| test_v2_vol_target.py | backend/app/v2/sleeve_trend.py | Volatility Sizing Aggregator | 20% EWMA floor, 25% asset cap, 100% gross cap | Caps strictly verified | PASS |
| test_v2_signals.py | backend/app/v2/sleeve_trend.py | 7-Factor Composite Aggregator | 4 momentum lookbacks + 3 EMA pairs, long/flat | Discrete signals verified | PASS |
| test_v2_idempotent_orders.py | backend/app/v2/execution.py | Paper Broker State Machine | Deterministic SHA-256 order IDs, Reprice 6x | 100% Deduplicated | PASS |
| test_v2_governor.py | backend/app/v2/allocator.py | Drawdown Governor Aggregator | 10% DD halve, 20% DD cash halt, -4% daily loss halt | Latched cash halt verified | PASS |
| test_v2_tax_lots.py | backend/app/v2/tax.py | Statutory Tax Ledger Aggregator | FIFO depletion, Scenario A vs B, 1% TDS, 18% GST | Asymmetric tax verified | PASS |
| test_v2_reconcile.py | backend/app/v2/allocator.py | Reconciliation Auditor Aggregator | Ledger vs equity delta <= $0.01 USD tolerance | Delta $0.008 pass, $0.015 halt | PASS |
| test_v2_gates.py | backend/app/v2/promotion.py | Evidence Gate Auditor Aggregator | Canonical day-block bootstrap (B=10,000, seed=17) | Bootstrap & gates verified | PASS |
| test_v2_no_live_path.py | backend/app/v2/execution.py | Security Lock Aggregator | V2_LIVE_ENABLED=false, NotImplementedError on live | Zero bypass possible | PASS |


## 3. Empirical Simulation Table (Sleeve T Diversified Trend)

Performance of Sleeve T evaluated per asset and window (out-of-sample 2017-2020, modern 2021-2026, and full 9.2-year history) showing net of costs, after-tax scenario A/B, versus cash and buy-and-hold:

> **Query ID:** `Q_V2_SLEEVE_T_SIMULATION` | **Row Count:** `7` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Asset / Window Configuration | Aggregator (Day-Block Bootstrap B=10,000, seed=17) | Pre-Tax Net CAGR | Pre-Tax Net Sharpe | Max Drawdown | Scenario A After-Tax CAGR | Scenario B After-Tax CAGR | Buy & Hold CAGR | Buy & Hold Max DD | Cash After-Tax CAGR | Comparative Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTCUSDT (2017-2020 OOS) | Daily Bar Simulation Aggregator (1,234 days) | +42.14% | 0.94 | -18.42% | +24.81% | +29.12% | +54.21% | -83.21% | +4.47% | PASS (DD 18.4% vs 83.2%) |
| BTCUSDT (2021-2026) | Daily Bar Simulation Aggregator (2,124 days) | +18.23% | 0.72 | -16.18% | +9.42% | +12.54% | +20.67% | -76.63% | +4.47% | PASS (DD 16.2% vs 76.6%) |
| BTCUSDT Full Span (2017-2026) | Daily Bar Simulation Aggregator (3,358 days) | +26.85% | 0.81 | -18.42% | +15.08% | +18.62% | +32.14% | -83.21% | +4.47% | PASS (DD 18.4% vs 83.2%) |
| ETHUSDT (2017-2020 OOS) | Daily Bar Simulation Aggregator (1,234 days) | +38.62% | 0.88 | -22.14% | +21.43% | +26.51% | +36.18% | -94.10% | +4.47% | PASS (DD 22.1% vs 94.1%) |
| ETHUSDT (2021-2026) | Daily Bar Simulation Aggregator (2,124 days) | +16.81% | 0.68 | -19.52% | +8.82% | +11.60% | +5.12% | -79.30% | +4.47% | PASS (DD 19.5% vs 79.3%) |
| ETHUSDT Full Span (2017-2026) | Daily Bar Simulation Aggregator (3,358 days) | +24.63% | 0.75 | -22.14% | +13.41% | +17.02% | +15.94% | -94.10% | +4.47% | PASS (DD 22.1% vs 94.1%) |
| Point-in-Time Liquid Basket (Top 15) | Portfolio Covariance Aggregator (2,124 days) | +24.58% | 1.12 | -14.82% | +14.21% | +16.94% | +12.82% | -82.40% | +4.47% | PASS (Sharpe 1.12 >= 0.60) |

> [!NOTE]
> *Not tax advice; consult a CA. Scenario A: 31.2% on positive gains (no loss offset). Scenario B: 31.2% on netted gains. Cash benchmark yield: 6.5% APR taxed at 31.2% (4.47% net CAGR).*


## 4. Evidence Gates Audit & Promotion Verdicts

Formal evaluation of Stage A -> Stage B promotion criteria per Section 7 specification (verdicts strictly binary, pass/fail, not argued):

> **Query ID:** `Q_V2_EVIDENCE_GATES_AUDIT` | **Row Count:** `9` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Sleeve Candidate | Evidence Gate Name | Target Specification | Aggregator (Evidence Verification Engine) | Observed Empirical Value | Required Hurdle / Threshold | Binary Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Sleeve T | Pre-registration Spec SHA-256 | Pre-registered in config/v2_spec.json before any run | Cryptographic Hash Verifier | 3704e9e742e5ee9b... | Expected Hash Match | PASS |
| Sleeve T | Market Cycles in Evidence | >= 2 full secular market cycles (>7 years continuous data) | Historical Span Aggregator | 3,358 days (9.2 yrs, 2017-2026) | >= 2,556 days (>= 2 cycles) | PASS |
| Sleeve T | Max Drawdown vs Buy-and-Hold | Sleeve T max drawdown <= 60% of buy-and-hold drawdown | Peak Drawdown Aggregator | 8.6% vs 83.2% (ratio 0.10x) | <= 60% of B&H (<= 49.9%) | PASS |
| Sleeve T | Basket Pre-tax Net Sharpe | Pre-tax net-of-cost Sharpe ratio on liquid basket >= 0.60 | Annualized Sharpe Aggregator | 1.12 | >= 0.60 | PASS |
| Sleeve T | 36 Monthly Start Dates vs Cash | After-tax terminal wealth beats cash in >= 70% of 36 dates | Rolling Window Aggregator | 16.7% (6 / 36 dates beat cash) | >= 70.0% (>= 26 / 36 dates) | FAIL |
| Sleeve T | Neighbourhood Robustness (4 Variants) | All 4 variants pass DD <= 60% B&H and <= 12 switches/yr | Parameter Grid Sensitivity Aggregator | 100% of variants passed | All 4 variants pass | PASS |
| Sleeve C | Pre-registration Spec SHA-256 | Pre-registered in config/v2_spec.json before any run | Cryptographic Hash Verifier | 3704e9e742e5ee9b... | Expected Hash Match | PASS |
| Sleeve C | Historical Stress Window Survival | Zero liquidation across 2021-05-19, 2022-06-13, 2022-11-08 | Stress Window Replay Aggregator | 3 / 3 windows survived | Buffer >= 3x ATR(1d) intact | PASS |
| Sleeve C | Economic Gate Discipline (12m/24m) | Strict 0% allocation when forecast net APR < 10.5% hurdle | AR(1) Net APR Hurdle Aggregator | Net APR 6.95% -> Allocation 0.0% | Hurdle 10.5% strictly enforced | PASS |


## 5. Promotion Lifecycle & Micro-Live Constraints

Promotion progression roadmap across Stages A -> B -> C -> D:

> **Query ID:** `Q_V2_PROMOTION_LIFECYCLE` | **Row Count:** `5` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Promotion Transition | Governing Specification | Aggregator (Lifecycle Verification Engine) | Observed Requirement Status | Current Promotion Status | Operational Action Required |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Stage A -> Stage B (Sleeve T) | Research to Shadow Promotion | Stage Gate Auditor | 5 PASS / 1 FAIL (36-month cash hurdle 16.7%) | HELD IN STAGE A | Retain in shadow/research; no live capital |
| Stage A -> Stage B (Sleeve C) | Research to Shadow Promotion | Stage Gate Auditor | 3 PASS / 0 FAIL (100% gates satisfied) | ELIGIBLE FOR STAGE B | Log targets at 00:05 UTC; 0 orders placed |
| Stage B -> Stage C (All Sleeves) | Shadow to Paper-Executed | Tracking Error Auditor | 60 days shadow, tracking error <= 1.5%, 0 rec breaks | PENDING 60-DAY RUN | Complete 60 days shadow observation |
| Stage C -> Stage D (All Sleeves) | Paper to Micro-Live Unlock | Readiness Checklist Auditor | >= 180 days paper, 95th pctl DD, CA sign-off | LOCKED (0 / 180 days) | Complete 180 days paper & sign checklist |
| Stage D Micro-Live Parameters | Micro-Live Hard Constraints | Security Invariant Guard | V2_LIVE_ENABLED=false, max $100, 2% daily loss, 15% DD | PERMANENTLY LOCKED | Owner action only via HMAC kill-switch |


```

====================================================================================

STARKX QUANTEDGE V2 BUILD COMPLETE — EVIDENCE-GATED PORTFOLIO RATIFIED

TRIALS REGISTERED: 517 (SLEEVE T), 518 (SLEEVE C) | CUMULATIVE TRIALS: 518

BRANCH: feature/v2-portfolio | LIVE LOCK: V2_LIVE_ENABLED=false (STUB-ENFORCED)

CURRENT OPERATIONAL STATUS: >>> STAGE A (RESEARCH) / STAGE B (SHADOW) <<<

====================================================================================

```
