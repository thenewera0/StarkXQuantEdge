# StarkX LAB: Weekly Operations & Portfolio Report (Week 44, 2026)


> **Operational Mode:** `LAB_EXECUTION_MODE = 'paper'` (Strict Rule 0.1 Invariant)  

> **Report Period:** 2026-W44 (Sunday Weekly Scheduled Dispatch)  

> **Git Commit Hash:** `451299e6a8030ba95f404b3d09718a8cb04b1dca`  

> **Statutory Indian Tax Notice:** Not tax advice; consult a CA.


---


## 1. Executive Operations Summary


> **Query ID:** `Q_LAB_WEEKLY_EXECUTIVE_SUMMARY` | **Row Count:** `7` | **Code Git Hash:** `451299e6a8030ba95f404b3d09718a8cb04b1dca`

| Portfolio Metric | Weekly Audited Value | Benchmark / Rule Reference | Aggregator (Weekly Operations Report) | Compliance Threshold | Health Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Active Research Variants | 15 Variants | Minimum 8, Maximum 40 concurrent | Aggregator (Weekly Operations Report) | >= 8 Active | NOMINAL |
| Live Open Paper Positions | 11 Positions | Max 3/variant, Max 1/symbol | Aggregator (Weekly Operations Report) | <= 45 Positions | NOMINAL |
| Total Virtual Portfolio Equity | $150,000.00 | Sum of Variant Virtual Balances | Aggregator (Weekly Operations Report) | $150,000.00 | RECONCILED |
| Cent-Level Ledger Delta | $0.0000 | Cash + Unrealized R vs Total Equity | Aggregator (Weekly Operations Report) | Delta < $0.01 | PASS |
| Beta-Adjusted BTC Exposure | 0.85x Equity | |Beta Exposure| <= 2.0x Equity | Aggregator (Weekly Operations Report) | <= 2.0x Cap | COMPLIANT |
| Registered Research Trials | 10 Trials | lab_trials research counter | Aggregator (Weekly Operations Report) | Monitored | NOMINAL |
| Expected False Positives | 0.05 E[FP] | 0.05 x (T2 + T3 variants) | Aggregator (Weekly Operations Report) | <= 1.0 | CONTROLLED |


---


## 2. Weekly Open Positions Marked-to-Market


> **Query ID:** `Q_LAB_WEEKLY_OPEN_POSITIONS` | **Row Count:** `11` | **Code Git Hash:** `451299e6a8030ba95f404b3d09718a8cb04b1dca`

| Position ID | Variant ID | Symbol | Direction | Entry Mode | Aggregator (Weekly Operations Report) | Entry Price USD | Mark Price USD | Unrealized R (Sum) | Warm Start Status | Risk USD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| pos_13e71e59f7b3d752_taker | rsi2_pullback_1h_base | BNBUSDT | LONG | taker | Aggregator (Weekly Operations Report) | $736.81 | $736.81 | +0.00R | WARM START | $50.00 |
| pos_ad63eed9e43a2b25_taker | rsi2_pullback_1h_short | ADAUSDT | SHORT | taker | Aggregator (Weekly Operations Report) | $0.20 | $0.20 | +0.00R | WARM START | $50.00 |
| pos_0efa1d158cb20390_taker | rsi2_pullback_1h_short | AVAXUSDT | SHORT | taker | Aggregator (Weekly Operations Report) | $8.88 | $8.88 | +0.00R | WARM START | $50.00 |
| pos_d4f48bfd1abc8ff7_taker | rsi2_pullback_1h_short | NEARUSDT | SHORT | taker | Aggregator (Weekly Operations Report) | $4.50 | $4.50 | +0.00R | WARM START | $50.00 |
| pos_f72c78a48cf633f5_taker | rsi2_pullback_1h_short | APTUSDT | SHORT | taker | Aggregator (Weekly Operations Report) | $0.69 | $0.69 | +0.00R | WARM START | $50.00 |
| pos_a233bebfc3542923_taker | rsi2_pullback_1h_short | ARBUSDT | SHORT | taker | Aggregator (Weekly Operations Report) | $0.17 | $0.17 | +0.00R | WARM START | $50.00 |
| pos_51d5cc26403fcde3_taker | rsi2_pullback_1h_short | DOTUSDT | SHORT | taker | Aggregator (Weekly Operations Report) | $1.01 | $1.01 | +0.00R | WARM START | $50.00 |
| pos_a536a02a5c57638e_taker | rsi2_pullback_1h_short | ATOMUSDT | SHORT | taker | Aggregator (Weekly Operations Report) | $1.64 | $1.64 | +0.00R | WARM START | $50.00 |
| pos_9339e6f14a7d9ae1_taker | rsi2_pullback_1h_short | FILUSDT | SHORT | taker | Aggregator (Weekly Operations Report) | $0.91 | $0.91 | +0.00R | WARM START | $50.00 |
| pos_07d8e028c90ed125_taker | carry_v2_base | BTCUSDT | LONG | taker | Aggregator (Weekly Operations Report) | $80214.45 | $80214.45 | +0.00R | WARM START | $50.00 |
| pos_b5e46520f6333a84_taker | carry_v2_base | ETHUSDT | LONG | taker | Aggregator (Weekly Operations Report) | $2324.11 | $2324.11 | +0.00R | WARM START | $50.00 |


---


## 3. Weekly Cent-Level Ledger Reconciliation


> **Query ID:** `Q_LAB_WEEKLY_LEDGER_RECONCILIATION` | **Row Count:** `4` | **Code Git Hash:** `451299e6a8030ba95f404b3d09718a8cb04b1dca`

| Ledger Component | Recorded Amount USD | Accounting Rule | Aggregator (Weekly Operations Report) | Audited Balance USD | Reconciliation Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Total Virtual Cash Ledger | $150,000.00 | 15 Variant Accounts ($10k each) | Aggregator (Weekly Operations Report) | $150,000.00 | RECONCILED |
| Total Floating Unrealized P&L | $0.00 | Mark-to-market on 1m candles | Aggregator (Weekly Operations Report) | $0.00 | AUDITED |
| Total Portfolio Equity | $150,000.00 | Cash + Floating Unrealized USD | Aggregator (Weekly Operations Report) | $150,000.00 | EXACT SUM |
| Ledger Reconciliation Delta | $0.0000 | Difference (Expected - Recorded) | Aggregator (Weekly Operations Report) | $0.0000 | RECONCILED TO THE CENT |


---


**STOP. Weekly report generated via `scripts/generate_report.py`. Not tax advice.**
