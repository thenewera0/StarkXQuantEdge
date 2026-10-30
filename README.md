# StarkX QuantEdge — Institutional Quantitative Trading System & Research Cockpit

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Execution Mode](https://img.shields.io/badge/Execution%20Mode-PAPER%20%C2%B7%20VIRTUAL-FFB020.svg)](#1-key-architectural-principles)
[![Pre-Registration SHA-256](https://img.shields.io/badge/Spec%20Lock-30410905...-00E5A8.svg)](#9-change-control--30-day-specification-lock)

**StarkX QuantEdge** is an institutional-grade, multi-asset quantitative trading engine, paper incubator, and decision-support cockpit. It bridges deterministic mathematical indicator engineering, an 8-family factor confluence pipeline, machine learning probability calibration, capital-adaptive fractional Kelly sizing, automated walk-forward parameter re-tuning, real-time delta-neutral arbitrage, and **StarkX Lab**—an autonomous multi-strategy paper trading sandbox featuring evidence-gated tier promotions (T0–T3), bounded parameter mutation, and statutory Indian tax modeling (Section 115BBH).

Every trade recommendation, stop loss, target, and position size is computed deterministically in Python using NumPy and Pandas with zero lookahead bias. Large Language Models (LLMs) operate strictly as qualitative narrative debaters and never generate prices, parameters, or financial accounting calculations.

> **Statutory Notice:** *All live modules operate strictly in simulated paper mode (`LAB_EXECUTION_MODE = 'paper'`). Not tax advice; consult a Chartered Accountant.*

---

## Table of Contents

1. [Key Architectural Principles](#1-key-architectural-principles)
2. [Monorepo Architecture & File Directory Structure](#2-monorepo-architecture--file-directory-structure)
3. [Frozen Core Strategy & Code Freeze Governance (Rules R1–R7)](#3-frozen-core-strategy--code-freeze-governance-rules-r1r7)
4. [Empirical Strategy Foundation: 1,002 Trade Forensic Audit](#4-empirical-strategy-foundation-1002-trade-forensic-audit)
5. [The 11-Phase Audit & Quantitative Research Reports](#5-the-11-phase-audit--quantitative-research-reports)
6. [StarkX Lab: Multi-Strategy Autonomous Paper Trading Engine](#6-starkx-lab-multi-strategy-autonomous-paper-trading-engine)
   - [6.1 Ten Strategy Catalog (L1–L10)](#61-ten-strategy-catalog-l1l10)
   - [6.2 Active Variants & Independent Virtual Accounting](#62-active-variants--independent-virtual-accounting)
   - [6.3 Evidence-Gated Promotion Tiers (T0–T3)](#63-evidence-gated-promotion-tiers-t0t3)
   - [6.4 Self-Improvement & Parameter Mutation Governance](#64-self-improvement--parameter-mutation-governance)
   - [6.5 Twin Execution Model (Taker Baseline vs Maker Model)](#65-twin-execution-model-taker-baseline-vs-maker-model)
   - [6.6 Multiplicative Hedge Allocator & Net Beta Ceiling](#66-multiplicative-hedge-allocator--net-beta-ceiling)
   - [6.7 1-Minute Tick Resolution & 3-Hour Downtime Catch-Up (Stop-First)](#67-1-minute-tick-resolution--3-hour-downtime-catch-up-stop-first)
   - [6.8 Warm-Start Launch Position Audit (11 Positions)](#68-warm-start-launch-position-audit-11-positions)
   - [6.9 Backfill Replay Isolation (375 Historical Trades)](#69-backfill-replay-isolation-375-historical-trades)
7. [Statutory Indian Tax Engineering (Section 115BBH & GST)](#7-statutory-indian-tax-engineering-section-115bbh--gst)
8. [Hosting, Supervision & Disaster Recovery Protocol](#8-hosting-supervision--disaster-recovery-protocol)
9. [Change Control & 30-Day Specification Lock](#9-change-control--30-day-specification-lock)
10. [Core Trading Engines & Subsystems](#10-core-trading-engines--subsystems)
    - [10.1 Core 4h Swing Confluence Engine](#101-core-4h-swing-confluence-engine)
    - [10.2 Flash Bot High-Frequency Scalper](#102-flash-bot-high-frequency-scalper)
    - [10.3 Centralized Arbitrage Cockpit](#103-centralized-arbitrage-cockpit)
    - [10.4 Thematic Investment Sleeves](#104-thematic-investment-sleeves)
11. [Mathematical Indicators & Price Action Engine](#11-mathematical-indicators--price-action-engine)
12. [8-Family Factor Confluence Pipeline](#12-8-family-factor-confluence-pipeline)
13. [Risk Engineering & Capital-Adaptive Kelly Sizing](#13-risk-engineering--capital-adaptive-kelly-sizing)
14. [Machine Learning & Online Calibration Feedback Loop](#14-machine-learning--online-calibration-feedback-loop)
15. [Multi-Agent Qualitative AI Debate System](#15-multi-agent-qualitative-ai-debate-system)
16. [Database Relational Architecture & Schemas](#16-database-relational-architecture--schemas)
17. [FastAPI REST API Reference](#17-fastapi-rest-api-reference)
18. [Next.js 16 Frontend Cockpit Reference](#18-nextjs-16-frontend-cockpit-reference)
19. [Automated CI Test Suite & Verification Matrix (14 Lab Tests)](#19-automated-ci-test-suite--verification-matrix-14-lab-tests)
20. [Operator Manual: Weekly Checklist & Production Setup](#20-operator-manual-weekly-checklist--production-setup)

---

## 1. Key Architectural Principles

1. **Deterministic Python Mathematical Core**: Every technical indicator, support/resistance level, stop-loss price, expected value, and position size is calculated in pure Python using NumPy and Pandas. AI/LLM models synthesize narrative context and never generate prices or parameters.
2. **Strict Paper Mode Invariant (`LAB_EXECUTION_MODE = 'paper'`)**: The entire repository enforces virtual paper trading. There are zero private exchange trading keys, zero active order execution endpoints, and zero live capital pathways.
3. **Causal Zero-Lookahead Architecture**: All backtest engines, live candle pipelines, and automated resolvers enforce strict temporal causality. A signal at bar $t$ evaluates using closed bars $0 \dots t-1$ or the final close of completed bar $t$.
4. **Data-Driven Loss Elimination**: Strategies, markets, and trigger kinds that demonstrate negative statistical expectancy in live trading are automatically pruned by software gates rather than maintained on theoretical hope.
5. **Friction-First Expectancy (EV Gate)**: Every potential trade must clear a realistic round-trip cost model (spread, taker/maker fee, depth slippage) in $R$-units before capital is allocated:
   $$\text{EV} = p \cdot R - (1 - p) - \text{cost}_{R} > 0$$
6. **Cent-Level Ledger Reconciliation**: Every account must mathematically reconcile at all times:
   $$\text{Total Equity} = \text{Virtual Cash} + \text{Floating Unrealized P&L} \quad (\Delta < \$0.01)$$
7. **Capital Preservation Over Activity**: "Silence is a position." When market conditions are choppy, overbought, or lacking orderbook confluence, the engine stands down.

---

## 2. Monorepo Architecture & File Directory Structure

```
StarkX QuantEdge Monorepo
├── backend/                               # Python FastAPI backend & algorithmic engine
│   ├── app/                               # Core application package
│   │   ├── lab/                           # StarkX Lab multi-strategy autonomous paper trading
│   │   │   ├── api.py                     # Lab REST routes (/lab/variants, /positions, /tax, etc.)
│   │   │   ├── engine.py                  # Lab tick replay, downtime catch-up, and scheduler
│   │   │   ├── governor.py                # Circuit breaker & cooldown monitor (3 losses rule)
│   │   │   ├── models.py                  # Pydantic & dataclass schemas (LabVariant, LabPosition)
│   │   │   ├── portfolio.py               # Hedge allocator (eta=0.1) & net beta exposure controller
│   │   │   ├── resolver.py                # 1m candle tick resolver with Stop-First collision logic
│   │   │   ├── storage.py                 # Persistent SQLite client (backend/data/lab.db)
│   │   │   ├── strategies.py              # L1–L10 Strategy catalog implementations
│   │   │   └── tiers.py                   # Statistical evidence gating engine (T0–T3, DSR, bootstrap)
│   │   ├── backtest/                      # Causal historical replay simulation harness
│   │   ├── data/                          # Real-time exchange adapters & on-chain data
│   │   │   ├── binance.py                 # Binance Spot/Futures REST + klines fetcher
│   │   │   ├── bybit.py                   # Bybit market data & depth orderbook adapter
│   │   │   ├── kraken.py                  # Kraken spot price feeds
│   │   │   ├── macro.py                   # Crypto macro, dominance, and Fear & Greed index
│   │   │   ├── solana.py                  # Solana RPC, Raydium/Orca DEX & whale tracker
│   │   │   ├── twelvedata.py              # TwelveData multi-asset fallback adapter
│   │   │   ├── validate.py                # Causal OHLCV validation & anomaly cleaning
│   │   │   └── yahoo.py                   # Yahoo Finance adapter for cross-asset feeds
│   │   ├── factors/                       # 8-family factor scorers & confluence logic
│   │   ├── indicators/                    # Pure NumPy/Pandas technical indicators
│   │   ├── llm/                           # Qualitative reasoning debate engine
│   │   ├── allocator.py                   # Multiplicative Weights (Hedge) strategy allocator
│   │   ├── arb.py                         # Funding carry, triangular & cross-exchange arb
│   │   ├── calibration.py                 # Isotonic regression probability calibration & Brier monitor
│   │   ├── config.py                      # Pydantic v2 settings & risk thresholds
│   │   ├── costs.py                       # Orderbook depth, spread & fee friction modeling
│   │   ├── db.py                          # Thread-safe PostgreSQL connection pool client
│   │   ├── drift.py                       # Page-Hinkley cumulative trade drift detection
│   │   ├── execution.py                   # Resting maker limit order execution simulator
│   │   ├── flash.py                       # Flash Bot high-frequency momentum scalper
│   │   ├── geometry.py                    # Volatility-based trade levels (Entry, SL, T1-T3)
│   │   ├── investments.py                 # Long-term investment sleeve & thematic assets
│   │   ├── learning.py                    # L2 Logistic Regression factor weight learning loop
│   │   ├── main.py                        # FastAPI endpoints, background scheduler, and CORS
│   │   ├── performance.py                 # Risk-adjusted ledger P&L, Sharpe, drawdown & by-strategy
│   │   ├── persistence.py                 # Signal logging & database query routines
│   │   ├── price_action.py                # Wick rejection, chart patterns & S/R cluster engine
│   │   ├── regime.py                      # L1 regime classification & Range-Fade strategy
│   │   ├── resolver.py                    # Asynchronous auto-outcome resolver (TP/SL/timeout)
│   │   ├── scanner.py                     # Autonomous 4h universe scanner & exposure monitor
│   │   ├── sizing.py                      # Capital-adaptive fractional Kelly & ruin sizing
│   │   └── universe.py                    # Asset catalog, liquidity checks & bleeder filters
│   ├── data/                              # Persistent storage directory
│   │   ├── lab.db                         # Production SQLite database for StarkX Lab
│   │   └── backups/                       # 14-day rolling automated atomic backups
│   ├── scripts/                           # Test suites, audits, backtests & report generators
│   │   ├── backup_lab.py                  # Automated daily atomic backup & restore drill script
│   │   ├── generate_report.py             # Deterministic Markdown report generator (Phases 4–11, Lab)
│   │   ├── send_test_alerts.py            # Health-only operational test alert dispatcher
│   │   ├── test_dashboard_labels.py       # Zero 'REAL CAPITAL' frontend static string scanner
│   │   ├── test_lab_change_control.py     # 30-day specification invariance CI guard
│   │   ├── test_lab_controls.py           # Statistical baseline controls & cost gate validator
│   │   ├── test_lab_downtime_catchup.py   # 3-hour downtime catch-up & Stop-First collision test
│   │   ├── test_lab_geometry.py           # Signal geometry & stop/target distance bounds test
│   │   ├── test_lab_hedge_weights.py      # Hedge multiplicative allocator & beta ceiling test
│   │   ├── test_lab_idempotent_signals.py # Signal idempotency & UNIQUE constraint test
│   │   ├── test_lab_ledger_reconcile.py   # Virtual cash + floating equity cent reconciliation test
│   │   ├── test_lab_lookahead.py          # Strict causal truncation lookahead test across L1–L10
│   │   ├── test_lab_no_real_orders.py     # AST code scanner verifying zero live order placement
│   │   ├── test_lab_resolver_1m.py        # 1-minute candle tick resolver & collision logic test
│   │   ├── test_lab_spawn_limits.py       # Self-improvement parameter mutation & variant limit test
│   │   ├── test_lab_tax.py                # Indian Section 115BBH & GST tax engine test
│   │   ├── test_lab_tiers.py              # Evidence tier promotion (T0–T3) & DSR statistical test
│   │   ├── test_report_tables.py          # Provenance validator verifying query IDs & aggregators
│   │   └── test_code_freeze_guard.py      # Frozen core hash & forward test immutability guard
│   └── requirements.txt                   # Python dependencies
├── config/                                # System configuration & frozen specifications
│   ├── lab_spec.json                      # Pre-registered StarkX Lab specification (SHA-256 locked)
│   ├── frozen_core_long_v1_1.json         # Frozen core forward-test specification
│   └── cohorts.json                       # Strategy cohort definitions
├── docs/                                  # Documentation, amendments, and generated reports
│   ├── CHANGELOG_LAB.md                   # Operational changelog for non-signal bug fixes
│   ├── LAB_AMENDMENTS.md                  # Cryptographic amendments ledger for lab_spec.json
│   ├── LAB_GLOSSARY.md                    # Operational terminology & mathematical definitions
│   └── reports/                           # Deterministic Markdown research & operations reports
│       ├── phase_4.md                     # Phase 4: Statistical Power & Execution Gaps
│       ├── phase_5.md                     # Phase 5: Delta-Neutral Basis/Funding Carry
│       ├── phase_6.md                     # Phase 6: Core 4h Long Factor Hardening
│       ├── phase_7.md                     # Phase 7: Deterministic Multi-Timeframe Logging
│       ├── phase_8.md                     # Phase 8: Execution Slippage & Stop Mutator Prevention
│       ├── phase_9.md                     # Phase 9: Empirical Validation & Amendment Governance
│       ├── phase_11.md                    # Phase 11: Multi-Asset Expansion & Tax Architecture
│       ├── v2_build.md                    # v2 Portfolio Engine Build Report
│       ├── v2_verification.md             # v2 Consolidated Verification Report
│       ├── v2_final_pass.md               # v2 Final Pass Report (36 Start Dates Simulation)
│       ├── lab_build.md                   # StarkX Lab Build & Architecture Report
│       ├── lab_ops_acceptance.md          # StarkX Lab Operational Acceptance Report
│       └── lab_weekly_2026W44.md          # Weekly Automated Operations & Portfolio Report
├── db/                                    # Supabase PostgreSQL relational schema
│   └── migrations/                        # Sequential SQL migration files
└── frontend/                              # Next.js 16 App Router web cockpit
    ├── app/                               # Pages, layouts, and global CSS
    │   ├── page.tsx                       # Primary cockpit dashboard (Overview & Panels)
    │   ├── lab/page.tsx                   # StarkX Lab multi-strategy paper trading cockpit
    │   └── portfolio/page.tsx             # v2 Portfolio & multi-sleeve allocation interface
    ├── components/                        # UI React components
    │   ├── CombinedPnl.tsx                # Strategy P&L breakdown & risk-adjusted ledger card
    │   ├── DashboardComponents.tsx        # Top metric cards & portfolio overview
    │   ├── FlashBotPanel.tsx              # Flash Bot scalping interface
    │   ├── LiveTradesPanel.tsx            # Open paper positions marked to market
    │   ├── PriceChart.tsx                 # TradingView lightweight-charts canvas
    │   └── TradeHistoryPanel.tsx          # Historical closed trades ledger
    └── lib/                               # API fetchers, TypeScript types & utilities
        └── api.ts                         # Frontend REST client & type definitions
```

---

## 3. Frozen Core Strategy & Code Freeze Governance (Rules R1–R7)

To eliminate post-hoc parameter tweaking and overfitting, the Core 4h Long strategy was officially frozen under cryptographic hash governance:

* **Frozen Specification File:** [`config/frozen_core_long_v1_1.json`](file:///c:/Users/Admin/Trading%20Bot%20app/config/frozen_core_long_v1_1.json)
* **Cryptographic Hash (SHA-256):** `e224027c42f068fca34db70e2f60e0a8fcc27acfc9c6e946765563556d837cf3`
* **Enforcement Script:** [`backend/scripts/test_code_freeze_guard.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_code_freeze_guard.py)
* **Governing Rules (R1–R7):**
  1. **R1 (Spec Immutability):** No parameters in `frozen_core_long_v1_1.json` may be altered under any circumstance.
  2. **R2 (Forward Path Isolation):** Live forward evaluation scripts (`evaluate_forward.py`, scanner, resolver) cannot import experimental backtest modules.
  3. **R3 (Single Canonical Fingerprint):** Every candle evaluation must resolve to exactly one canonical signal hash (`symbol:interval:direction:bar_open_time`). Duplicate scans within the same bar collapse into that single record.
  4. **R4 (Closed-Bar Rule):** Signals trigger strictly at bar close ($t$); order entry occurs at the open of bar $t+1$. Zero intrabar execution.
  5. **R5 (Stop Mutation Prohibition):** Once placed, stop-loss orders can only move in the favorable direction (trailing stops). Widening a stop loss triggers an immediate fatal CI guard failure.
  6. **R6 (True Risk-Adjusted Accounting):** P&L is calculated using actual dollar risk at entry ($R_{\text{net}} \times \text{risk\_usd\_at\_entry}$), never unweighted flat notional sums.
  7. **R7 (Amendment Pre-Registration):** Any strategic change requires a formal entry in `docs/PRE_REGISTRATION_AMENDMENT.md` with git commit hash, timestamp, and rationale.

---

## 4. Empirical Strategy Foundation: 1,002 Trade Forensic Audit

The system's core architecture was overhauled based on a forensic audit of **1,002 historical live and paper trades** ([`docs/reports/phase_0_5.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_0_5.md)):

### The Equity Curve Discrepancy Reconciliation
* **Legacy `/performance` Cumulative Realized P&L:** **`+$938.13 USD`** (on 417 core trades).
* **True Risk-Adjusted Ledger Realized P&L:** **`-$240.81 USD`** (on 417 core trades, $-22.02R$).
* **Gap Decomposition:**
  1. **Flat Notional Distortion:** The legacy code multiplied raw percentage returns by a flat `$1,000` notional. Volatile trades with wide stops (5–10% distance) produced massive unearned dollar gains on low R-multiples, artificially masking dozens of tight-stop losses.
  2. **Selective Shadow Exclusion:** The legacy dashboard selectively ignored 604 resolved Flash paper trades (`-$79.48 USD`, $-22.71R$) and 11 legacy core shadow trades (`-$16.01 USD`).
  3. **The Solution:** Full risk-adjusted sizing ($pnl\_usd = R_{\text{net}} \times \text{risk\_usd}$) was implemented across all backend endpoints (`/performance`, `/performance/by-strategy`), harmonizing all cards and charts to **`-$240.81`**.

---

## 5. The 11-Phase Audit & Quantitative Research Reports

The monorepo contains a sequence of rigorous empirical research deliverables in [`docs/reports/`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/):

| Report Document | Title & Focus | Key Deliverables & Methodological Proofs |
| :--- | :--- | :--- |
| [`phase_4.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_4.md) | **Statistical Power & Execution Gaps** | Sample size power calculations ($N \ge 384$ for $\alpha=0.05, \beta=0.20$), friction decomposition, R-multiple distributions. |
| [`phase_5.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_5.md) | **Delta-Neutral Basis/Funding Carry** | Empirical basis yield modeling, borrow fee stress testing, and the mathematical Sharpe identity proof. |
| [`phase_6.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_6.md) | **Core 4h Long Factor Hardening** | Elimination of lookahead leakage, canonical fingerprint deduplication, and full market regime breakdowns. |
| [`phase_7.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_7.md) | **Multi-Timeframe Logging Specification** | Deterministic audit log structures across 15m, 1h, 4h, and 1d bars. Forward evaluation protocol. |
| [`phase_8.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_8.md) | **Execution Slippage & Stop Protection** | Execution twin modeling (maker vs taker), stop mutator AST scanner, and equity curve size reconciliation. |
| [`phase_9.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_9.md) | **Empirical Validation & Governance** | Cross-validation against live data feeds, discrepancy attribution, and formal amendment registration. |
| [`phase_11.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_11.md) | **Multi-Asset Expansion & Tax Framework** | Institutional Indian Section 115BBH tax modeling, 18% GST brokerage impact, cross-venue funding, and master promotion matrix. |
| [`v2_final_pass.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/v2_final_pass.md) | **v2 Multi-Sleeve Final Pass Report** | 36 rolling start dates simulation (2023–2026), uncredited vs credited cash accounting, basket survivorship audit, and FX sensitivity. |
| [`lab_build.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/lab_build.md) | **StarkX Lab Architecture & Build** | Full specification of the 10 catalog strategies, 15 active variants, evidence gates (T0–T3), and twin execution engine. |
| [`lab_ops_acceptance.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/lab_ops_acceptance.md) | **Lab Operational Acceptance Report** | Hosting, process supervision, restore drill results, 3h downtime catch-up replay, warm-start audit, and 14/14 test pass matrix. |
| [`lab_weekly_2026W44.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/lab_weekly_2026W44.md) | **Weekly Portfolio & Operations Report** | Executive summary, open paper positions marked to market, and cent-level ledger reconciliation ($0.0000 delta). |

---

## 6. StarkX Lab: Multi-Strategy Autonomous Paper Trading Engine

**StarkX Lab** (`backend/app/lab/`) is an autonomous multi-strategy paper trading sandbox and research incubator. It runs continuously in paper mode (`LAB_EXECUTION_MODE = 'paper'`), simulating parallel strategy execution with realistic execution economics and statistical gating.

### 6.1 Ten Strategy Catalog (L1–L10)

| Strategy ID | Catalog Name | Timeframe | Asset Universe | Direction | Core Thesis & Trigger Logic |
| :--- | :--- | :---: | :--- | :---: | :--- |
| `trend_d1` | L1 Trend Daily | 1d | Top 10 Liquid Crypto | Long Only | EMA 21/55 golden cross confirmed by ADX $> 25$. ATR-based trailing stop. |
| `donchian_4h` | L2 Donchian Breakout 4h | 4h | Top 20 Liquid Crypto | Long + Short | 20-bar Donchian channel breakout confirmed by Volume $> 1.5\times$ SMA(20). |
| `rsi2_pullback_1h` | L3 RSI(2) Pullback 1h | 1h | Top 20 Liquid Crypto | Long + Short | Connors RSI(2) $< 10$ pullback in bullish trend (above EMA 200). Exit on EMA 5 cross. |
| `bb_fade_1h` | L4 Bollinger Bands Fade 1h | 1h | Ranging Altcoins | Long + Short | Mean reversion when price pierces $2.5\sigma$ BB band and CHOP $> 61.8$. |
| `squeeze_break_4h` | L5 Squeeze Breakout 4h | 4h | Top 20 Liquid Crypto | Long Only | John Carter TTMSqueeze: Bollinger Bands compress inside Keltner Channels, firing on expansion. |
| `xs_momentum_1d` | L6 Cross-Sectional Momentum 1d | 1d | 30 Crypto Universe | Long + Reversal | Ranks top quintile performers over 30 days; buys top 3 assets, rebalanced weekly. |
| `funding_skew_4h` | L7 Funding Skew Sentiment 4h | 4h | Perps with Funding Data | Long + Short | Contrarian positioning when funding rate Z-score $> +2.0$ (short) or $< -2.0$ (long). |
| `flush_fade_1h` | L8 Flush Drop Maker Fade 1h | 1h | High-Liquidity Crypto | Long Only | Detects sharp liquidity washouts ($> 3\sigma$ hourly volume drop with lower wick $> 40\%$). |
| `pairs_btceth_1d` | L9 ETH/BTC Log Ratio Spread 1d | 1d | ETH & BTC Pair | Spread (L/S) | Z-score of $\ln(\text{ETH}/\text{BTC})$ relative to 60-day mean. Long undervalue, short overvalue. |
| `carry_v2` | L10 Basis / Carry Sleeve Paper | 1d | BTC & ETH Perps/Spot | Long Only | Captures annualized perpetual funding yield delta-hedged against spot holdings. |

### 6.2 Active Variants & Independent Virtual Accounting
StarkX Lab initializes **15 active variants** across L1–L10. Each variant manages an **independent virtual cash account of $10,000.00 USD** ($150,000.00 total virtual portfolio equity):
* **Risk Per Trade:** Fixed $0.50\%$ of variant equity ($50.00 USD risk per trade).
* **Position Limits:** Maximum 3 open positions per variant; maximum 1 open position per symbol per variant.
* **Accounting Rigor:** Every tick updates cash, unrealized R-multiples, and total equity. The cent-level reconciliation invariant holds across all accounts:
  $$\Delta = |\text{Virtual Cash} + \text{Floating Unrealized P&L} - \text{Total Recorded Equity}| = \$0.0000$$

### 6.3 Evidence-Gated Promotion Tiers (T0–T3)
Variants must graduate through four rigorous statistical hurdles to earn weight allocation:

```
┌─────────────────┐       N >= 20, t >= 1.645       ┌─────────────────┐
│  Tier 0 (T0)    ├────────────────────────────────►│  Tier 1 (T1)    │
│  Incubating     │       Bootstrap p < 0.10        │  Candidate      │
└─────────────────┘                                 └────────┬────────┘
                                                             │
                                                             │ N >= 50, DSR >= 0.95
                                                             ▼ p < 0.05
┌─────────────────┐       N >= 100, WRC p < 0.05    ┌─────────────────┐
│  Tier 3 (T3)    │◄────────────────────────────────┤  Tier 2 (T2)    │
│  Production-Ready│      Cost Stress Test Passed   │  Validated      │
└─────────────────┘                                 └─────────────────┘
```

1. **Tier 0 (Incubating, $N < 20$):** Sizing factor $\times 0.25$. Collecting forward trade evidence.
2. **Tier 1 (Candidate, $N \ge 20$):** Sizing factor $\times 0.50$. Student's $t \ge 1.645$, bootstrap $p < 0.10$ ($B=10,000$ resamples), and $\text{EV}_R \ge +0.05R$.
3. **Tier 2 (Validated, $N \ge 50$):** Sizing factor $\times 1.00$. Deflated Sharpe Ratio ($\text{DSR} \ge 0.95$) explicitly adjusting for multiple testing across all registered variants ($K$), variance of trials ($\sigma_{\text{trials}}^2$), and negative skewness/kurtosis:
   $$\text{DSR} = \Phi\left( \frac{(\text{SR} - \text{SR}^*)\sqrt{N-1}}{\sqrt{1 - \gamma_3 \text{SR} + \frac{\gamma_4 - 1}{4}\text{SR}^2}} \right) \ge 0.95$$
4. **Tier 3 (Production Candidate, $N \ge 100$):** Sizing factor $\times 1.50$. White's Reality Check ($p < 0.05$) and passes $2.0\times$ fee stress testing.

### 6.4 Self-Improvement & Parameter Mutation Governance
Variants in T1 or higher can spawn child variants (`backend/app/lab/engine.py`):
* **Safe Mutator Bounds:** Parameters can only mutate by at most $\pm 20\%$ from parent values.
* **Variant Capacity Cap:** Total variants across the entire lab cannot exceed **40 concurrent variants**.
* **Trial Registration Counter:** Every spawned mutation increments the global research trial counter (`trialsRegistered`), which automatically inflates the DSR hurdle $\text{SR}^*$ for subsequent tier promotions.
* **Governor Circuit Breaker (`governor.py`):** If any variant incurs **3 consecutive losses**, it is automatically put on a 7-day cooldown (no new entries permitted).

### 6.5 Twin Execution Model (Taker Baseline vs Maker Model)
Every signal simultaneously logs two parallel execution twins:
1. **Taker Baseline:** Enters immediately across the spread paying taker fees ($0.05\%$ crypto perps) plus depth slippage ($0.03\%$).
2. **Maker Limit Model:** Places a resting limit order at the bid (for longs) or ask (for shorts), paying maker rebate/fees ($0.02\%$). Simulates realistic queue priority using a Poisson fill probability model:
   $$P(\text{Fill}) = 1 - e^{-\lambda \cdot \Delta t}$$
   If price does not reach the resting order within 2 candles, the maker twin expires unfilled ($0.00 P&L$)—preventing fantasy backtest fills.

### 6.6 Multiplicative Hedge Allocator & Net Beta Ceiling
Capital allocation across active variants is rebalanced using the **Hedge Multiplicative Weights Algorithm** (`portfolio.py`):
* **Weight Update Rule:** For variant $i$ with normalized loss $\ell_{i,t} \in [0, 1]$:
  $$w_{i,t+1} = w_{i,t} \cdot e^{-\eta \cdot \ell_{i,t}} \quad (\eta = 0.10)$$
* **James-Stein Shrinkage:** When variant trade counts $N < 100$, performance estimators are shrunk toward the catalog grand mean to prevent small-sample noise from commanding oversized allocations.
* **Allocation Constraints:** Minimum floor weight of **2.0%**; maximum ceiling weight of **30.0%**.
* **Portfolio Beta Exposure Ceiling:** The portfolio calculates net beta-adjusted BTC exposure:
  $$\text{Beta Exposure} = \sum_{i} w_i \cdot \beta_{i, \text{BTC}} \cdot \text{Position Size USD}$$
  Hard constraint: $|\text{Beta Exposure}| \le 2.0 \times \text{Total Equity}$. If violated, new long signals are suppressed.

### 6.7 1-Minute Tick Resolution & 3-Hour Downtime Catch-Up (Stop-First)
Trade level resolution runs at **1-minute tick granularity** (`backend/app/lab/resolver.py`).
* **Stop-First Collision Rule:** If a 1-minute candle touches both the stop-loss price and the take-profit target in the same minute, the engine **strictly executes the stop-loss first** (`exit_reason = 'stop_collision_first'`). The target is completely ignored.
* **3-Hour Downtime Catch-Up:** In the event of system downtime, `LabEngine.catch_up()` replays all missed 1-minute candles in strict chronological order:
  - Replays all 180 missed 1m candles.
  - Resolves stops at the exact minute of collision (e.g. Minute 45).
  - Evaluates missed bar closes (e.g., 13:00, 14:00, 15:00 UTC) exactly once.
  - Generates zero duplicate signals (database `UNIQUE` constraint).
  - Reconciles cash ledger to the exact cent ($0.0000 delta).

### 6.8 Warm-Start Launch Position Audit (11 Positions)
During initial system boot, 11 positions were filled at bar close price rather than awaiting the next bar open:
* All 11 positions are flagged **`warm_start = 1`** in `lab_positions`.
* Kept in the virtual cash ledger to ensure cent-level accounting parity.
* Displayed in the UI with a distinct `WARM START` badge.
* **Strictly excluded from evidence tier progression (T0 $\to$ T1 $\to$ T2 $\to$ T3).** Only closed-bar forward trades (`warm_start = 0` and `is_backfill = 0`) count toward tier graduation.

### 6.9 Backfill Replay Isolation (375 Historical Trades)
The 12-month historical backfill replay (375 trades across L1–L10) was executed to seed historical metrics:
* All 375 records are explicitly tagged **`is_backfill = 1`**.
* **100% excluded from forward evidence tiers.** Variant forward trade counters start at exactly 0.

---

## 7. Statutory Indian Tax Engineering (Section 115BBH & GST)

StarkX Lab incorporates a statutory Indian tax evaluation engine (`backend/app/lab/api.py`, `backend/scripts/test_lab_tax.py`) modeled after Section 115BBH of the Income Tax Act:

* **Scenario A (Strict Section 115BBH Flat Regime):**
  - **Flat 30% Tax + 4% Health & Education Cess = 31.2% Flat Rate** on all gross transfer gains.
  - **Zero Loss Offset:** Losses from one trade/asset cannot offset gains from another.
  - Tax Liability $= 0.312 \times \sum \max(0, \text{Gain}_i)$.
* **Scenario B (Netting Treatment — Identical to v2):**
  - **31.2% Flat Rate on Netted Gains & Losses.**
  - Tax Liability $= 0.312 \times \max(0, \sum \text{P&L}_i)$.
* **Goods & Services Tax (GST):**
  - **18.0% GST** applied to all exchange trading fees and brokerage commissions.
* **Codebase Cleanliness:** Outdated ordinary business income (20%) definitions have been purged from all code, models, tests, and documentation.
* **Statutory Notice:** *Not tax advice; consult a CA.*

---

## 8. Hosting, Supervision & Disaster Recovery Protocol

StarkX Lab is engineered for continuous unattended operation:

* **Host Environment:** Dedicated workstation / server running Python 3.12 ASGI via FastAPI on `127.0.0.1:8000`.
* **Process Manager & Supervision:** Supervised by Windows Service / NSSM (`starkx-lab`) configured with `Restart=always`, 5-second restart delay, and crash recovery SLA $< 10$ seconds.
* **Persistent Storage:** SQLite database stored at [`backend/data/lab.db`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/data/lab.db). Stored outside ephemeral deployment directories and `.gitignore` protected.
* **Automated Daily Backups:** Executed daily at **00:05 UTC** by [`scripts/backup_lab.py`](file:///c:/Users/Admin/Trading%20Bot%20app/scripts/backup_lab.py) using the online atomic SQLite backup API (`sqlite3_backup`).
* **Retention Policy:** 14-day rolling window in `backend/data/backups/`. Snapshots older than 14 days are automatically pruned.
* **Disaster Recovery Drill Result:** Verified by full restore drill:
  - Snapshot size: 196,608 bytes (Bitwise SHA-256 match).
  - SQLite `PRAGMA integrity_check == 'ok'`.
  - Table record parity verified (15 variants, 386 positions, 11 signals, 44 events, 1 trial).
  - Restored ledger reconciliation delta: **`$0.0000`**.

---

## 9. Change Control & 30-Day Specification Lock

To protect research integrity and prevent p-hacking during live forward testing:

* **Launch Timestamp:** `2026-10-29T00:00:00Z` (recorded in [`backend/app/lab/__init__.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/lab/__init__.py)).
* **Specification File:** [`config/lab_spec.json`](file:///c:/Users/Admin/Trading%20Bot%20app/config/lab_spec.json)
* **Pre-Registration SHA-256:** `30410905d364ab6e4d3f8c6d7940ce0c112944de7891103a68aa776dbd7590ae`
* **30-Day Invariance Window:** Active until **`2026-11-28T00:00:00Z`**.
* **Automated CI Guard:** [`backend/scripts/test_lab_change_control.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_change_control.py) fails CI if `lab_spec.json` changes before the 30-day window expires unless logged in [`docs/LAB_AMENDMENTS.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/LAB_AMENDMENTS.md).
* **Permitted Bug Fixes:** Operational bug fixes that do not modify signals, strategy parameters, or accounting rules are permitted and logged in [`docs/CHANGELOG_LAB.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/CHANGELOG_LAB.md).

---

## 10. Core Trading Engines & Subsystems

```
                                  ┌───────────────────────────┐
                                  │   STARKX QUANTEDGE CORE   │
                                  └─────────────┬─────────────┘
                ┌───────────────────────────────┼───────────────────────────────┐
                ▼                               ▼                               ▼
  ┌───────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────┐
  │     CORE SWING ENGINE     │   │      FLASH SCALPER        │   │     ARBITRAGE COCKPIT     │
  │ • 4h Crypto Longs         │   │ • 1h & 15m Burst/Breakout │   │ • Funding Rate Carry      │
  │ • 8-Family Confluence     │   │ • Tight Maker Execution   │   │ • Triangular Cycle Arb    │
  │ • Range-Fade & Trend      │   │ • CVD & Vol Expansion     │   │ • Cross-Exchange Depth    │
  └───────────────────────────┘   └───────────────────────────┘   └───────────────────────────┘
```

### 10.1 Core 4h Swing Confluence Engine
The primary swing engine (`signal_service.py`, `scanner.py`) executes multi-day trend continuation and range-fade setups on 4h candlestick bars:
* **Scanning Cadence**: Autonomous background sweep every 30 minutes over 50+ liquid crypto pairs.
* **Directional Discipline**: Hard-enforced `crypto_long_only = True` for core swings.
* **Regime Adaptability**: Transitions between trend-following and mean-reverting geometry based on ADX, Choppiness Index, and Ornstein-Uhlenbeck half-life.
* **Safety Bounds**: Hard rejection of stop distances $> 6.0\%$ and sub-penny micro tokens ($< \$0.001$).

### 10.2 Flash Bot High-Frequency Scalper
The Flash Bot (`flash.py`) operates as an independent scalper on 15m and 1h intervals:
* **Momentum Burst (`burst`)**: Detects explosive price thrusts through EMA9 accompanied by volume expansion $\ge 1.10\times$ 20-bar average and positive CVD aggression ($Z \ge 0.35$).
* **Range Breakout (`breakout`)**: Price pierces 15-bar high/low extremes with expanding volatility.
* **Short Direction Gating**: Shorts are permitted **exclusively** on the `burst` trigger family; all other short setups are rejected.
* **Concurrency Caps**: Limits active flash trades to a maximum of 3 concurrent positions, and at most 2 in the same direction.

### 10.3 Centralized Arbitrage Cockpit
The arbitrage cockpit (`arb.py`) scans for market inefficiencies across centralized venues:
1. **Delta-Neutral Funding Rate Carry**: Buys spot and shorts perpetual futures on high-funding assets. Uses an AR(1) time-series model to forecast funding yield over an 8-hour horizon and verifies that yield exceeds 2-leg taker fees plus a safety buffer.
2. **Triangular Cycle Arbitrage**: Models exchange pairs as directed graphs and executes Bellman-Ford negative cycle searches (e.g., USDT $\rightarrow$ BTC $\rightarrow$ ETH $\rightarrow$ USDT) considering taker fees.
3. **Cross-Exchange Spreads**: Compares real-time top-of-book bid/ask quotes between Binance and Bybit.

### 10.4 Thematic Investment Sleeves
The portfolio manager (`portfolio.py`, `investments.py`) partitions capital across segregated sleeves:
* **Core Swing Sleeve**: $40\%$ target weight.
* **Flash Scalp Sleeve**: $20\%$ target weight.
* **Arbitrage Sleeve**: $15\%$ target weight.
* **Cash Reserve (Dry Powder)**: Minimum $25\%$ floor maintained at all times.

---

## 11. Mathematical Indicators & Price Action Engine

### 11.1 Technical Indicator Engine
Implemented in `indicators/engine.py` using vectorized NumPy routines:
* **Exponential Moving Averages (EMA)**: Periods 9, 21, 50, and 200.
* **Triple Exponential Moving Average (TEMA)**:
  $$\text{TEMA} = 3 \cdot \text{EMA}_1 - 3 \cdot \text{EMA}_2 + \text{EMA}_3$$
* **Average True Range (ATR)**: Wilder's 14-period smoothing on true range.
* **Bollinger Bands (%B & Bandwidth)**: 20-period SMA with $2\sigma$ channels.
* **Trend & Chop Oscillators**: 14-period ADX, +DI/-DI directional indicators, and Choppiness Index (CHOP).
* **UT Bot Trailing Stop**: ATR-based dynamic volatility stop-and-reverse band.
* **LuxAlgo MA Sabres**: Detects inflection points in TEMA trend velocity after prolonged runs.
* **Ornstein-Uhlenbeck (OU) Mean-Reversion Half-Life**:
  Fits an AR(1) continuous process on residuals $x_t = P_t - \text{EMA}_{21}(P_t)$:
  $$\Delta x_t = -\lambda x_{t-1} + \epsilon_t \implies t_{\text{half}} = \frac{\ln(2)}{\lambda}$$
  Range-fades are only initiated when mean reversion occurs rapidly ($t_{\text{half}} \le 24$ bars).

### 11.2 Price Action & Candle Structure Engine
Implemented in `price_action.py`:
* **Candle Anatomy Diagnosis**: Computes upper wick ratio $\frac{H - \max(O, C)}{H - L}$ and lower wick ratio $\frac{\min(O, C) - L}{H - L}$. Detects shooting stars ($> 50\%$ upper wick) and hammers ($> 50\%$ lower wick).
* **Pattern Recognition**: Bullish/Bearish Engulfing, Inside Bars, Double Tops/Bottoms, Liquidity Sweeps.
* **Dynamic S/R Clustering**: Identifies swing pivots and groups price levels into volatility-based support and resistance bands.
* **Pre-Trade Clearance Gate**: Longs are blocked if overhead resistance sits within $0.50\times \text{ATR}$ or if the previous candle printed a heavy bearish rejection wick.

---

## 12. 8-Family Factor Confluence Pipeline

Primary signals pass through 8 independent evidence families (`factors/scorer.py`), each generating a normalized score in $[-100.0, +100.0]$:

| Factor Family | Core Inputs & Signals | Weight (4h Core) |
|---|---|:---:|
| **F1: Trend** | EMA 9/21/50/200 stack alignment, TEMA slope, UT Bot position state, LuxAlgo flip | 0.22 |
| **F2: Momentum** | 14-period RSI, Stochastic %K, MACD histogram normalized to ATR | 0.18 |
| **F3: Volatility** | Bollinger Band %B position, Bandwidth expansion/compression ratio | 0.12 |
| **F4: Structure** | Distance to nearest DBSCAN S/R pivot, 50-bar Fibonacci retracement levels | 0.14 |
| **F5: Order Flow** | Cumulative Volume Delta (CVD) Z-score, bid/ask orderbook imbalance, funding rate Z-score | 0.14 |
| **F6: Sentiment** | Alternative.me Crypto Fear & Greed Z-score, curated crypto news sentiment | 0.08 |
| **F7: Macro** | BTC/ETH market dominance metrics, cross-asset macro trend momentum | 0.06 |
| **F8: Consensus** | Higher timeframe (HTF) trend alignment, cross-oscillator agreement | 0.06 |

### Confluence Score & Agreement Scaling
1. Active weights are re-normalized across available factor families: $w_i' = \frac{w_i}{\sum w_k}$.
2. Raw weighted confluence score: $R_{\text{raw}} = \sum w_i' \cdot S_i$.
3. Directional agreement ratio ($A$):
   $$A = \frac{\text{Count of active families sharing the sign of } R_{\text{raw}}}{\text{Total active families}}$$
4. Final Composite Score is scaled by agreement to prevent single-factor distortion:
   $$\text{Composite} = \text{Clip}_{-100, 100}\left( R_{\text{raw}} \cdot (0.50 + 0.50 \cdot A) \right)$$

---

## 13. Risk Engineering & Capital-Adaptive Kelly Sizing

### 13.1 Quarter-Kelly & Ruin Risk Formulation
Implemented in `sizing.py`:

$$\text{Quarter-Kelly Fraction: } f_k = \frac{\max\left(0, \, p - \frac{1 - p}{R}\right)}{4}$$

Solves the continuous gambler's ruin equation for drawdown tolerance $D = 0.50$ (50% account drawdown) and ruin probability $\alpha = 0.05$ (5% risk of ruin):

$$\text{Final Risk Fraction } f = \min(f_k, \, f_{\text{ruin}}, \, \text{Tier Risk Cap}) \times \text{Drift Mult} \times \text{Alloc Mult} \times \text{Symbol Mult}$$

* **Account Tiers**:
  * **Micro** ($<\$100$): Risk cap $2.0\%$, EV floor $+0.20R$, max concurrent 2.
  * **Small** ($\$100 - \$1,000$): Risk cap $2.0\%$, EV floor $+0.10R$, max concurrent 8.
  * **Standard** ($\$1,000 - \$10,000$): Risk cap $2.0\%$, EV floor $+0.05R$, max concurrent 20.
  * **Growth** ($>\$10,000$): Risk cap $1.5\%$, EV floor $+0.05R$, max concurrent 30.

### 13.2 Self-Protecting Circuit Breakers & Drift Detection
* **Page-Hinkley Drift Detector (`drift.py`)**: Tracks cumulative trade performance residuals $m_t = R_t - \bar{R}$. When cumulative negative drift exceeds threshold $U_t - T_t > \lambda$, the system flags regime drift, raises the EV floor to $+0.40R$, and cuts sizing by $50\%$.
* **Global Circuit Breaker**: If realized returns drop below $-3.0R$ over rolling 24 hours, all scanning halts for 24 hours.

---

## 14. Machine Learning & Online Calibration Feedback Loop

* **Isotonic Probability Calibration (`calibration.py`)**: Fits a monotonic isotonic regression (PAVA) mapping composite scores directly to empirical win probabilities: $p = \text{IsotonicFit}(\text{Composite} \mid \text{Market}, \text{Direction})$. Rolling calibration monitored via Brier score.
* **Meta-Labeling Classifier (`meta_model.py`)**: A Random Forest trains on a 22-dimensional feature vector to predict target achievement probabilities before order entry.
* **L2 Regularized Online Weight Optimizer (`learning.py`)**: Periodically optimizes factor weights via regularized logistic regression with walk-forward out-of-sample challenger testing.
* **Asynchronous Outcome Resolver (`resolver.py`)**: Background worker polling completed candles to evaluate take-profit targets, trailing stops, and 48-bar timeouts.

---

## 15. Multi-Agent Qualitative AI Debate System

When an active confluence setup is identified, structured technical context can be dispatched to OpenRouter (`llm/debate.py`) to run a 3-agent qualitative debate:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. BULL ANALYST AGENT                                                  │
│ Argues bullish thesis using factor strengths, order flow & support.    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. BEAR ANALYST AGENT                                                  │
│ Challenges the setup, highlights overhead resistance & macro risks.    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. RISK MANAGER JUDGE AGENT                                            │
│ Delivers structured JSON verdict: { agreement, conviction, risks }     │
└────────────────────────────────────────────────────────────────────────┘
```

* **Penalty Adjustment**:
  $$\text{Final Confidence} = \text{Round}\Big( (0.50 \cdot \text{Model Conf} + 0.50 \cdot \text{AI Conviction}) \times \text{Penalty} \Big)$$
  where $\text{Penalty} = 1.00$ (Agree), $0.85$ (Caution), $0.60$ (Disagree).
* **Deterministic Offline Fallback (`llm/fallback.py`)**: If external AI APIs are disabled or unreachable, an internal mathematical debate generator synthesizes narratives directly from factor scores.

---

## 16. Database Relational Architecture & Schemas

### PostgreSQL (Supabase) Schema
* `signals`: Emitted signals, factors, confidence, levels, and sizes.
* `outcomes`: Resolved trades, realized P&L, MFE/MAE excursions, duration.
* `factor_logs`: Raw 8-family factor scores for offline machine learning.
* `regime_weights`: Champion factor weights per market regime.
* `arb_opportunities`: Detected funding carry and triangular cycles.

### SQLite Schema (`backend/data/lab.db`)
* `lab_variants`: Variant metadata, parameters, evidence tier (T0–T3), cash balance, total equity, trade counts, and win/loss records.
* `lab_positions`: Open and closed paper positions, symbol, entry price, stop price, target price, unrealized R, realized R, `warm_start`, and `is_backfill`.
* `lab_signals`: Emitted strategy signals with `UNIQUE(strategy_id, variant_id, symbol, direction, bar_open_time)`.
* `lab_events`: Operational health telemetry alerts (`FEED_STALE`, `RECONCILIATION_BREAK`, `JOB_FAILURE`).
* `lab_trials`: Registered research trials counter for Deflated Sharpe Ratio penalty calculation.

---

## 17. FastAPI REST API Reference

The backend exposes an interactive OpenAPI documentation endpoint at `http://127.0.0.1:8000/docs`.

### Core Cockpit Endpoints
| Method | Endpoint | Query Parameters | Description |
|:---:|:---|:---|:---|
| `GET` | `/health` | None | Returns backend status, environment, version, and database connection state |
| `GET` | `/performance` | `trade_size`, `include_shadow`, `strategy` | Returns risk-adjusted ledger P&L, Sharpe, drawdown, and closed trade distribution |
| `GET` | `/performance/by-strategy` | `trade_size` | Returns realized P&L split by strategy family (core vs flash) using true risk-sizing |
| `GET` | `/live/trades` | `trade_size`, `strategy` | Running open positions marked to live price |
| `GET` | `/signal` | `symbol`, `interval`, `market`, `limit` | Computes full deterministic factor scores, levels, and regime for asset |
| `GET` | `/decision` | `symbol`, `interval`, `market` | Factor Confluence + AI Multi-Agent Debate + Logging pipeline |
| `GET` | `/candles` | `symbol`, `interval`, `market`, `limit` | Validated OHLCV candlestick bars for charting |
| `POST`| `/resolve` | `max_signals` | Manually triggers outcome resolver over open signals |
| `POST`| `/flash/scan` | None | Sweeps the 15m/1h universe for momentum burst setups |
| `POST`| `/arb/funding-scan` | None | Delta-neutral funding carry arbitrage scan |
| `POST`| `/arb/triangular-scan` | None | Triangular currency cycle arbitrage scan |

### StarkX Lab Endpoints
| Method | Endpoint | Description |
|:---:|:---|:---|
| `GET` | `/lab/health` | Lab operational health, feed latency, active variants, open positions, and ledger delta |
| `GET` | `/lab/variants` | Leaderboard of active variants, strategy families, tiers (T0–T3), DSR, and equity |
| `GET` | `/lab/positions/open` | Open paper positions marked to market on 1m candles |
| `GET` | `/lab/positions/history` | Historical closed paper positions with exit reasons and realized R |
| `GET` | `/lab/events` | Operational health alerts feed (`FEED_STALE`, `RECONCILIATION_BREAK`, `JOB_FAILURE`) |
| `GET` | `/lab/tax/summary` | Statutory Indian tax comparison (Scenario A flat vs Scenario B netted + 18% GST) |
| `GET` | `/lab/portfolio` | Hedge allocator weights, variant equity distribution, and net BTC beta exposure |

---

## 18. Next.js 16 Frontend Cockpit Reference

Built with **Next.js 16 (App Router)**, **React 19**, **TypeScript**, and **Tailwind CSS**:

1. **Overview Dashboard (`/`):**
   - **Metric Cards:** Core Realized PnL (`-$241`), Core Total PnL (`-$241`), Open Core Positions (`0`), Open Lab Positions, Active Variants, Risk Score. All badged `PAPER · VIRTUAL`.
   - **Portfolio Overview Canvas:** Interactive equity curve chart matching ledger-true figures (`-$240.81`).
   - **Strategy P&L Breakdown Card:** Independent virtual accounts breakdown displaying Core (`-$240.81`) and Flash (`-$120.98`), fully reconciled to the cent.
   - **Open Positions Table:** Live paper trades marked to market.
2. **StarkX Lab Cockpit (`/lab`):**
   - **Operational Health Strip:** Feed latency monitor, ledger reconciliation status, `trialsRegistered` meter, and `expectedFalsePositives`.
   - **Active Variants Leaderboard:** Real-time view of variants, strategy tags (L1–L10), evidence tier badges (T0–T3), DSR scores, and virtual cash balances.
   - **Open Paper Positions Panel:** 1m mark-to-market prices, stop/target levels, unrealized R-multiples, and `WARM START` badges.
   - **Statutory Tax Scenario Card:** Section 115BBH Scenario A vs Scenario B comparison table with CA consultation notice.
3. **v2 Portfolio Cockpit (`/portfolio`):**
   - Multi-sleeve allocation interface, 36 start dates simulation analytics, and stage promotion matrices.

---

## 19. Automated CI Test Suite & Verification Matrix (14 Lab Tests)

The test suite in `backend/scripts/` covers all invariants with 100% green test passes:

| Test Script | Target Invariant & Standard | Result |
| :--- | :--- | :---: |
| [`test_lab_no_real_orders.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_no_real_orders.py) | AST static scanner: Zero real order endpoints, zero exchange keys, mode='paper' | **PASS** |
| [`test_lab_geometry.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_geometry.py) | Signal geometry: Stop side correct, stop $\ge 0.25\%$, target $0.5$--$5R$, 6 sig digits | **PASS** |
| [`test_lab_idempotent_signals.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_idempotent_signals.py) | `UNIQUE(strategy, variant, symbol, dir, bar_open_time)` strictly enforced | **PASS** |
| [`test_lab_resolver_1m.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_resolver_1m.py) | 1m tick resolver: Same-minute collision resolves strictly via Stop-First | **PASS** |
| [`test_lab_lookahead.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_lookahead.py) | Truncation invariance: Zero future bar leakage across all 10 catalog strategies | **PASS** |
| [`test_lab_controls.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_controls.py) | Statistical controls: RandomEntryControl & AlwaysLongControl cost gating | **PASS** |
| [`test_lab_tiers.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_tiers.py) | Statistical tiers: T0 $\to$ T1 $\to$ T2 $\to$ T3 gates, $B=10k$ bootstrap, $\text{DSR} \ge 0.95$ | **PASS** |
| [`test_lab_hedge_weights.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_hedge_weights.py) | Hedge allocator ($\eta=0.10$), James-Stein shrinkage ($N<100$), floor 2%, cap 30% | **PASS** |
| [`test_lab_spawn_limits.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_spawn_limits.py) | Safe mutation bounds $\pm 20\%$, maximum 40 variants, trial counter $+1$ | **PASS** |
| [`test_lab_ledger_reconcile.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_ledger_reconcile.py) | Virtual cash + floating P&L reconciles to the cent ($\Delta = \$0.0000$) | **PASS** |
| [`test_lab_tax.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_tax.py) | Indian Section 115BBH Scenario A (31.2% flat), Scenario B (31.2% net), 18% GST | **PASS** |
| [`test_dashboard_labels.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_dashboard_labels.py) | Static string audit: Zero 'REAL CAPITAL' strings across all frontend files | **PASS** |
| [`test_lab_downtime_catchup.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_downtime_catchup.py) | 3-hour downtime catch-up: 180m replayed, Stop-First on minute 45, zero duplicates | **PASS** |
| [`test_lab_change_control.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lab_change_control.py) | 30-day specification lock guard anchoring `config/lab_spec.json` hash | **PASS** |

---

## 20. Operator Manual: Weekly Checklist & Production Setup

### 20.1 Quick Start (Local Setup)

```powershell
# 1. Backend Setup
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.migrate

# Run all 14 lab test suites to verify green status
python ..\scripts\test_report_tables.py
python -c "import subprocess, sys; [subprocess.run([sys.executable, f'scripts/{t}'], check=True) for t in ['test_lab_no_real_orders.py', 'test_lab_geometry.py', 'test_lab_idempotent_signals.py', 'test_lab_resolver_1m.py', 'test_lab_lookahead.py', 'test_lab_controls.py', 'test_lab_tiers.py', 'test_lab_hedge_weights.py', 'test_lab_spawn_limits.py', 'test_lab_ledger_reconcile.py', 'test_lab_tax.py', 'test_dashboard_labels.py', 'test_lab_downtime_catchup.py', 'test_lab_change_control.py']]"

# Start FastAPI backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 2. Frontend Setup
cd ..\frontend
npm install
npm run build
npm run dev
```

Visit the cockpit at `http://localhost:3000` (or `http://localhost:3000/lab`).

### 20.2 Weekly Operator Checklist (What to Check Weekly)

1. **Feed Latency:** Inspect the `/lab` health strip; confirm feed latency is under 10 seconds (alarm triggers at $> 300\text{s}$).
2. **Ledger Reconciliation:** Verify `deltaUsd == $0.0000` across all 15 virtual accounts in the health strip.
3. **Backup Freshness:** Verify the latest backup in `backend/data/backups/` was created within the last 24 hours and that 14 rolling snapshots exist.
4. **Active Variant Count:** Ensure between 8 and 40 variants are active on the leaderboard; review any variants paused by the Governor.
5. **Open Paper Positions:** Review open positions (maximum 3 per variant, maximum 1 per symbol); confirm stops and targets resolve on 1-minute ticks.
6. **Portfolio Beta Exposure:** Confirm net portfolio beta-adjusted BTC exposure does not exceed the $|2.0| \times \text{Equity}$ statutory ceiling.
7. **Evidence Tier Progression:** Review T0 $\rightarrow$ T1 candidate graduations; confirm only closed-bar forward trades count toward tier promotion.
8. **Research Trials Meter:** Review `trialsRegistered` and `expectedFalsePositives` on `/lab` to monitor multiple testing penalties.
9. **Weekly Report Generation:** Run `python scripts/generate_report.py` every Sunday at 06:00 UTC to generate the weekly operational report.
10. **Specification Invariance:** Run `python backend/scripts/test_lab_change_control.py` to ensure zero unauthorized specification mutations.

---

## License & Intellectual Property

StarkX QuantEdge is proprietary algorithmic trading software. All rights reserved. Code, mathematical models, factor formulations, and execution engines are protected under proprietary licensing.
