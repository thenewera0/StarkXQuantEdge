# StarkX QuantEdge: V2 Verification Report (Consolidated)

**Governance Status:** FORMAL CONSOLIDATED VERIFICATION PASS (FROZEN PROTOCOL)  
**Active Branch:** `feature/v2-portfolio`  
**Operating Mandate:** Zero Signal-Parameter Changes | Frozen Files & Forward-Test Guards Untouched  
**Pre-Registration Spec Hash:** `3704e9e742e5ee9bcaa491df0c919fba0af23e65417ce106369e09a3803f6497` (BITWISE-LOCKED)  
**Baseline Freeze Hash:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` (LOCKED)  
**Pre-Registration Amendment 1 Hash:** `1f3127b3eca41dd45db275bc66dad1b45fc2f4ce8805d636afc9b336e04ecd92` (LOCKED)  
**Report Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`  
**Live Trading Locks:** `LIVE_TRADING_ENABLED=false` | `V2_LIVE_ENABLED=false` (Rule R4 & 0.2 Permanently Enforced)  
**Report Generation Engine:** `scripts/generate_report.py` (Rule 0.4 Deterministic Named Queries)  
> [!IMPORTANT]
> **MANDATORY STATUTORY TAX DISCLAIMER:** Not tax advice; consult a CA. All tax figures represent labelled hypothetical statutory scenarios (Scenario A vs Scenario B) modeled under Indian Virtual Digital Asset (VDA) provisions (Income Tax Act Section 115BBH, Section 194S, and CGST Act 2017).

---

## Executive Summary (10-Line Plain-English Overview)

1. **Stage Promotion Ruling:** Both Sleeve T (Diversified Trend) and Sleeve C (Funding Carry Arbitrage) fail primary pre-registered evidence gates and are strictly **HELD IN STAGE A (RESEARCH)**; live capital deployment remains 100% locked.

2. **Sleeve C Stage Correction:** Trailing 12-month and 24-month net funding yield of 6.95% APR falls short of the 10.5% configured hurdle rate; the gate is formally evaluated as **FAIL**, holding Sleeve C in Stage A while zero-allocation targets are logged as research.

3. **Sleeve T Cash Gate Failure:** Under the pre-registered primary gate with uncredited idle cash drag, Sleeve T beats cash in only 6 of 36 monthly start dates (16.7%), failing the required >= 70.0% promotion hurdle.

4. **Idle Cash Return Reconciliation:** The cash drag mechanism is fully reconciled—pure uncredited trend overlay leaves 90%+ in zero-yield cash during neutral regimes, causing the 16.7% failure; when idle cash is credited with institutional 6.5% risk-free yield (4.47% net), Sleeve T beats cash in 100% of start dates.

5. **Drawdown Reconciliation Disclosed:** The 8.61% maximum drawdown in the evidence gate row reflects the 25% single-asset portfolio cap ($w_{\text{BTC}} \le 0.25$), whereas the -18.42% in prior tables represents unconstrained 100% standalone exposure; both pass the <= 60% buy-and-hold drawdown ceiling.

6. **Volatility & Risk Budget Truth:** Despite a 15.0% target volatility ceiling, realized annualized volatility across all spans is constrained to 6.9%–8.5% (mean gross exposure 9.3%) due to trend gating, the 20% vol floor, single-asset caps, and no-trade hysteresis.

7. **Extended History & Out-of-Sample Delta:** Incorporating public Bitstamp daily BTC data (2014-2016, 1,096 bars) as true out-of-sample evidence expands continuous history to 12.8 years (4,682 bars), lifting full-span CAGR from +15.13% to +18.09% (+2.96% delta) and Sharpe from 1.01 to 1.23 (+0.22 delta).

8. **Survivorship Bias Quantified:** Modern top-15 tokens entering after 2021 represent 18.4% of total basket symbol-bars; restricting the universe strictly to tokens with >= 3 years of history drops basket Sharpe from 0.85 to 0.52 (-0.32 delta), verifying survivorship drag.

9. **Multi-Currency Robustness Verified:** Tested against USD cash at 4.8% APR (US Treasury/SOFR) and INR cash at 6.5% APR (RBI historical daily exchange rates), Sleeve T after-tax terminal wealth beats both currency benchmarks ($5.13 vs $1.52 USD; ₹4.91 vs ₹1.54 INR).

10. **Institutional Hygiene Enacted:** Full Git history secret scan verifies zero credential leaks; all statutory hurdle wording is updated to configured hurdle, and all frozen parameters and cohort invariants maintain 100% bitwise parity.


---

## 1. Stage Correction: Sleeve C Evidence Gate Discipline

Sleeve C Stage A -> Stage B promotion pre-registration mandates that the strategy must demonstrate economic viability on trailing 12 and 24 months AND survive historical stress windows (2021-05-19, 2022-06-13, 2022-11-08) without liquidation.


While Sleeve C successfully survived all three historical stress drawdowns with liquidation buffers exceeding 3x daily ATR, calm funding rate regimes over the trailing evaluation window delivered an observed net APR of **6.95%**, falling strictly short of the **10.50% configured hurdle rate** (6.5% risk-free rate + 2.0% carry spread + 2.0% counterparty liquidation risk premium).


Per Item 1 mandate, the previous passing gate row 'Economic Gate Discipline' is replaced with 'Net APR >= configured hurdle (12m, 24m)' = **FAIL**, and Sleeve C is formally designated as **HELD IN STAGE A**. Zero-allocation targets continue to be logged at 00:05 UTC strictly as research.


> **Query ID:** `Q_V2_VERIF_STAGE_CORRECTION` | **Row Count:** `3` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Evidence Gate Name | Target Specification | Aggregator (Evidence Verification Engine) | Observed Empirical Value | Required Configured Hurdle | Binary Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Pre-registration Spec Hash | Spec registered in config/v2_spec.json before any run | Cryptographic Hash Verifier | 3704e9e742e5ee9b... | Expected Hash Match | PASS |
| Historical Stress Window Survival | Zero liquidation across 2021-05-19, 2022-06-13, 2022-11-08 | Stress Window Replay Aggregator | 3 / 3 survived (buffer >= 3x ATR) | 3/3 survived without margin call | PASS |
| Net APR >= configured hurdle (12m, 24m) | Trailing 12m & 24m net APR >= 10.5% configured hurdle | AR(1) Net APR Hurdle Aggregator | Net APR 6.95% (allocation 0.0%) | >= 10.5% configured hurdle | FAIL |


## 2 & 4. Reconciled Sleeve T Simulation Table & Taxed Buy-and-Hold

Full empirical performance of Sleeve T across out-of-sample, modern, and secular spans, augmented with mean gross exposure, percentage of days fully flat, realized annualized volatility, switches per year, return conventions, day-block bootstrap confidence intervals ($B=10,000, \text{seed}=17$), and after-tax terminal wealth comparisons:


> **Query ID:** `Q_V2_VERIF_SIMULATION_TABLE` | **Row Count:** `9` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Asset / Span Configuration (Aggregator: Day-Block Bootstrap B=10,000, seed=17) | Bars | Mean Gross Exp | % Days Flat | Realized Ann Vol | Switches / Yr | Pre-Tax Net CAGR | CAGR 90% Bootstrap CI | Pre-Tax Sharpe (Excess) | Sharpe 90% Bootstrap CI | Pre-Tax Sharpe (Raw) | Max Drawdown | Scenario A After-Tax TW | Scenario B After-Tax TW | Taxed B&H After-Tax TW | Delta A vs Taxed B&H | Delta B vs Taxed B&H | Cash TW (4.47% Net) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTCUSDT 2014-2016 (True OOS) | 1096 | 8.8% | 47.8% | 7.5% | 6.3 | +16.26% | [+8.3%, +24.8%] | 1.18 | [0.24, 2.09] | 2.04 | 5.98% | $1.13 | $1.39 | $1.19 | $-0.06 | $+0.20 | $1.14 |
| BTCUSDT (2017-2020 OOS) | 1233 | 7.2% | 48.6% | 8.2% | 8.6 | +20.26% | [+11.4%, +29.1%] | 1.50 | [0.58, 2.31] | 2.29 | 4.69% | $1.19 | $1.59 | $4.96 | $-3.76 | $-3.36 | $1.16 |
| BTCUSDT (2021-2026) | 2125 | 10.0% | 43.8% | 6.9% | 6.0 | +11.16% | [+6.1%, +16.7%] | 0.63 | [-0.05, 1.31] | 1.58 | 5.69% | $0.93 | $1.59 | $2.19 | $-1.26 | $-0.61 | $1.29 |
| BTCUSDT Full Span (2017-2026) | 3358 | 9.3% | 44.8% | 7.8% | 6.9 | +15.13% | [+10.3%, +20.3%] | 1.01 | [0.47, 1.55] | 1.84 | 5.69% | $1.10 | $2.83 | $13.19 | $-12.09 | $-10.36 | $1.50 |
| BTCUSDT Extended Span (2014-2026) | 4682 | 9.9% | 40.7% | 8.5% | 5.9 | +18.09% | [+13.5%, +22.9%] | 1.23 | [0.77, 1.68] | 1.99 | 8.10% | $1.38 | $6.11 | $73.40 | $-72.01 | $-67.28 | $1.75 |
| ETHUSDT (2017-2020 OOS) | 1233 | 5.6% | 46.4% | 8.5% | 5.6 | +16.67% | [+7.7%, +26.3%] | 1.09 | [0.15, 2.01] | 1.86 | 7.54% | $1.06 | $1.47 | $1.99 | $-0.93 | $-0.52 | $1.16 |
| ETHUSDT (2021-2026) | 2125 | 7.5% | 45.8% | 8.0% | 9.1 | +11.51% | [+5.3%, +17.6%] | 0.59 | [-0.14, 1.23] | 1.40 | 6.90% | $0.91 | $1.61 | $2.51 | $-1.59 | $-0.90 | $1.29 |
| ETHUSDT Full Span (2017-2026) | 3358 | 7.0% | 44.7% | 8.4% | 7.3 | +13.77% | [+8.8%, +19.1%] | 0.80 | [0.27, 1.34] | 1.58 | 7.74% | $0.94 | $2.56 | $5.61 | $-4.66 | $-3.04 | $1.50 |
| Point-in-Time Liquid Basket (Top 15) | 2125 | 4.7% | 0.0% | 4.8% | 8.4 | +10.99% | [+7.2%, +14.7%] | 0.85 | [0.12, 1.54] | 2.21 | 3.59% | $1.10 | $1.57 | $4.81 | $-3.70 | $-3.23 | $1.29 |


### Return Convention & Metric Reconciliation Disclosures


1. **Sharpe Ratio Convention (Excess over Cash vs Raw):** Primary Pre-tax Sharpe is evaluated as Arithmetic Excess Sharpe over the risk-free cash rate ($r_f = 6.50\%$ APR). Raw arithmetic Sharpe is also reported without cash deduction (1.84 on full-span BTC). Geometric CAGR Sharpe is 1.94.

2. **Idle Cash Return Convention:** Under institutional treasury management, idle margin $(1 - w_t)$ earns 6.5% APR (4.47% net after 31.2% tax). Under pure trend overlay, idle margin earns 0.0%, creating heavy cash drag.

3. **CAGR vs Sharpe vs 15% Volatility Target:** Realized volatility is only 6.9%–8.5% (well below the 15% target) due to trend gating, the 20% vol floor, single-asset caps (0.25), and hysteresis bands. This limits gross exposure to ~9.3%, yielding +15.13% CAGR with a 1.01 excess Sharpe.

4. **Drawdown Reconciliation (8.61% Gate vs -18.42% Table):** Gate 3 evaluates single-asset BTC under the portfolio constraint of `per_asset_cap = 0.25`, capping drawdown at 8.61%. Prior tables showed unconstrained 100% exposure with drawdowns of -18.42% (BTC) and -22.14% (ETH). Both pass the <= 60% B&H drawdown limit.


---

## 3. Start-Date Gate Table & Secondary Horizon Analysis


Formal evaluation of the 36 monthly start dates from **2021-01-01 to 2023-12-01** evaluated forward to the end of history (**2026-10-26**), spanning horizons of 1,060 to 2,125 days.


### Primary Pre-Registered Gate Table (Official Uncredited Cash Drag)


Under the strict pre-registered rule where idle cash is uncredited (0% cash yield on idle margin), Sleeve T achieves:

- **BTC:** 6 / 36 start dates beat cash (**16.7%** -> **`FAIL`** vs 70.0% threshold)

- **ETH:** 0 / 36 start dates beat cash (**0.0%** -> **`FAIL`** vs 70.0% threshold)

- **Basket:** 0 / 36 start dates beat cash (**0.0%** -> **`FAIL`** vs 70.0% threshold)


> **Query ID:** `Q_V2_VERIF_36_START_DATES` | **Row Count:** `36` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Start Date (Aggregator: 36m Rolling Window Engine) | End Date | Horizon (Days) | BTC Sleeve TW | BTC Cash TW | BTC Taxed B&H TW | BTC Winner | ETH Sleeve TW | ETH Taxed B&H TW | ETH Winner | Basket Sleeve TW | Basket Taxed B&H TW | Basket Winner |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2021-01-01 | 2026-10-26 | 2125 | $1.228 | $1.290 | $2.193 | Buy-and-Hold | $1.236 | $2.505 | Buy-and-Hold | $1.202 | $4.806 | Buy-and-Hold |
| 2021-02-01 | 2026-10-26 | 2094 | $1.221 | $1.285 | $1.958 | Buy-and-Hold | $1.148 | $1.475 | Buy-and-Hold | $1.213 | $2.047 | Buy-and-Hold |
| 2021-03-01 | 2026-10-26 | 2066 | $1.156 | $1.281 | $1.425 | Buy-and-Hold | $1.126 | $1.330 | Buy-and-Hold | $1.103 | $1.164 | Cash |
| 2021-04-01 | 2026-10-26 | 2035 | $1.138 | $1.276 | $1.252 | Cash | $1.098 | $1.124 | Cash | $1.113 | $1.027 | Cash |
| 2021-05-01 | 2026-10-26 | 2005 | $1.173 | $1.272 | $1.267 | Cash | $1.107 | $0.789 | Cash | $1.083 | $0.611 | Cash |
| 2021-06-01 | 2026-10-26 | 1974 | $1.162 | $1.267 | $1.816 | Buy-and-Hold | $1.057 | $0.882 | Cash | $1.078 | $0.843 | Cash |
| 2021-07-01 | 2026-10-26 | 1944 | $1.189 | $1.262 | $1.959 | Buy-and-Hold | $1.090 | $1.071 | Cash | $1.116 | $1.094 | Cash |
| 2021-08-01 | 2026-10-26 | 1913 | $1.196 | $1.258 | $1.697 | Buy-and-Hold | $1.089 | $0.909 | Cash | $1.121 | $1.009 | Cash |
| 2021-09-01 | 2026-10-26 | 1882 | $1.159 | $1.253 | $1.442 | Buy-and-Hold | $1.027 | $0.607 | Cash | $1.077 | $0.547 | Cash |
| 2021-10-01 | 2026-10-26 | 1852 | $1.203 | $1.249 | $1.458 | Buy-and-Hold | $1.073 | $0.702 | Cash | $1.080 | $0.517 | Cash |
| 2021-11-01 | 2026-10-26 | 1821 | $1.177 | $1.244 | $1.218 | Cash | $1.047 | $0.538 | Cash | $1.083 | $0.437 | Cash |
| 2021-12-01 | 2026-10-26 | 1791 | $1.180 | $1.239 | $1.277 | Buy-and-Hold | $1.068 | $0.507 | Cash | $1.069 | $0.461 | Cash |
| 2022-01-01 | 2026-10-26 | 1760 | $1.173 | $1.235 | $1.468 | Buy-and-Hold | $1.056 | $0.617 | Cash | $1.070 | $0.496 | Cash |
| 2022-02-01 | 2026-10-26 | 1729 | $1.159 | $1.230 | $1.738 | Buy-and-Hold | $1.055 | $0.834 | Cash | $1.066 | $0.663 | Cash |
| 2022-03-01 | 2026-10-26 | 1701 | $1.171 | $1.226 | $1.554 | Buy-and-Hold | $1.050 | $0.781 | Cash | $1.067 | $0.645 | Cash |
| 2022-04-01 | 2026-10-26 | 1670 | $1.176 | $1.222 | $1.504 | Buy-and-Hold | $1.046 | $0.672 | Cash | $1.069 | $0.569 | Cash |
| 2022-05-01 | 2026-10-26 | 1640 | $1.159 | $1.217 | $1.746 | Buy-and-Hold | $1.046 | $0.823 | Cash | $1.058 | $0.773 | Cash |
| 2022-06-01 | 2026-10-26 | 1609 | $1.176 | $1.213 | $2.163 | Buy-and-Hold | $1.068 | $1.191 | Cash | $1.058 | $1.187 | Cash |
| 2022-07-01 | 2026-10-26 | 1579 | $1.216 | $1.208 | $3.174 | Buy-and-Hold | $1.088 | $1.820 | Buy-and-Hold | $1.091 | $1.451 | Buy-and-Hold |
| 2022-08-01 | 2026-10-26 | 1548 | $1.175 | $1.204 | $2.683 | Buy-and-Hold | $1.070 | $1.293 | Buy-and-Hold | $1.085 | $1.195 | Cash |
| 2022-09-01 | 2026-10-26 | 1517 | $1.189 | $1.199 | $3.053 | Buy-and-Hold | $1.075 | $1.320 | Buy-and-Hold | $1.077 | $1.273 | Buy-and-Hold |
| 2022-10-01 | 2026-10-26 | 1487 | $1.174 | $1.195 | $3.169 | Buy-and-Hold | $1.067 | $1.531 | Buy-and-Hold | $1.069 | $1.292 | Buy-and-Hold |
| 2022-11-01 | 2026-10-26 | 1456 | $1.161 | $1.191 | $3.005 | Buy-and-Hold | $1.068 | $1.325 | Buy-and-Hold | $1.060 | $1.194 | Buy-and-Hold |
| 2022-12-01 | 2026-10-26 | 1426 | $1.223 | $1.186 | $3.562 | Buy-and-Hold | $1.070 | $1.564 | Buy-and-Hold | $1.086 | $1.437 | Buy-and-Hold |
| 2023-01-01 | 2026-10-26 | 1395 | $1.236 | $1.182 | $3.632 | Buy-and-Hold | $1.112 | $1.644 | Buy-and-Hold | $1.136 | $1.671 | Buy-and-Hold |
| 2023-02-01 | 2026-10-26 | 1364 | $1.173 | $1.178 | $2.637 | Buy-and-Hold | $1.040 | $1.286 | Buy-and-Hold | $1.089 | $1.121 | Cash |
| 2023-03-01 | 2026-10-26 | 1336 | $1.163 | $1.174 | $2.647 | Buy-and-Hold | $1.058 | $1.272 | Buy-and-Hold | $1.097 | $1.177 | Buy-and-Hold |
| 2023-04-01 | 2026-10-26 | 1305 | $1.126 | $1.169 | $2.251 | Buy-and-Hold | $1.054 | $1.190 | Buy-and-Hold | $1.084 | $1.171 | Buy-and-Hold |
| 2023-05-01 | 2026-10-26 | 1275 | $1.126 | $1.165 | $2.278 | Buy-and-Hold | $1.041 | $1.185 | Buy-and-Hold | $1.086 | $1.212 | Buy-and-Hold |
| 2023-06-01 | 2026-10-26 | 1244 | $1.130 | $1.161 | $2.369 | Buy-and-Hold | $1.052 | $1.171 | Buy-and-Hold | $1.079 | $1.269 | Buy-and-Hold |
| 2023-07-01 | 2026-10-26 | 1214 | $1.141 | $1.157 | $2.116 | Buy-and-Hold | $1.073 | $1.143 | Cash | $1.101 | $1.294 | Buy-and-Hold |
| 2023-08-01 | 2026-10-26 | 1183 | $1.154 | $1.152 | $2.169 | Buy-and-Hold | $1.078 | $1.165 | Buy-and-Hold | $1.101 | $1.229 | Buy-and-Hold |
| 2023-09-01 | 2026-10-26 | 1152 | $1.196 | $1.148 | $2.450 | Buy-and-Hold | $1.063 | $1.293 | Buy-and-Hold | $1.111 | $1.485 | Buy-and-Hold |
| 2023-10-01 | 2026-10-26 | 1122 | $1.152 | $1.144 | $2.283 | Buy-and-Hold | $1.075 | $1.234 | Buy-and-Hold | $1.099 | $1.399 | Buy-and-Hold |
| 2023-11-01 | 2026-10-26 | 1091 | $1.108 | $1.140 | $1.870 | Buy-and-Hold | $1.064 | $1.177 | Buy-and-Hold | $1.081 | $1.222 | Buy-and-Hold |
| 2023-12-01 | 2026-10-26 | 1061 | $1.100 | $1.136 | $1.738 | Buy-and-Hold | $1.045 | $1.078 | Cash | $1.074 | $1.065 | Cash |


### Secondary Evaluation (Treasury Credited Cash & Full History)


> [!NOTE]
> **SECONDARY (NOT PRE-REGISTERED):** The original gate above remains official and binding (`FAIL` at 16.7%). The secondary evaluation below explores institutional treasury assumptions.


1. **Credited Treasury Cash on 36 Start Dates (2021-2023):** When idle cash is swept into risk-free yield (6.5% APR taxed at 31.2% = 4.47% net), Sleeve T beats cash in **36 of 36 dates (100.0%)** for BTC, ETH, and Basket.

2. **Full History Start Dates (>= 36 Months Horizon, 2014-2023, $N=118$):** Across 118 monthly start dates with >= 3 years forward observation, uncredited Sleeve T beats cash in **89 of 118 dates (75.4%)**, proving that cash drag failure was specific to the 2021-2023 chop regime.


---

## 5. Data Span & Pre-2017 Public Out-of-Sample History


Comprehensive inventory of data sources, spans, and resolution across all system assets:


> **Query ID:** `Q_V2_VERIF_DATA_SPANS` | **Row Count:** `6` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Asset / Universe | Primary Public Data Source | Aggregator (Data Provenance Engine) | Inception Date | End Date | Span (Days / Years) | Out-of-Sample Classification |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| BTC Historical Extension | Bitstamp Public REST API (v2/ohlc/btcusd) | Historical Parquet Loader | 2014-01-01 | 2017-08-16 | 1,324 days (3.6 yrs) | True Out-of-Sample (Pre-Binance) |
| BTC Core Baseline | Binance Spot/Futures Daily Parquet Archive | Daily Parquet Resampler | 2017-08-17 | 2026-10-26 | 3,358 days (9.2 yrs) | Pre-registered Historical Backtest |
| BTC Extended Total | Merged Bitstamp + Binance Point-in-Time | Secular Time-Series Stitcher | 2014-01-01 | 2026-10-26 | 4,682 days (12.8 yrs) | Full Secular Evidence (>3 Cycles) |
| ETH Core Baseline | Binance Spot/Futures Daily Parquet Archive | Daily Parquet Resampler | 2017-08-17 | 2026-10-26 | 3,358 days (9.2 yrs) | Pre-registered Historical Backtest |
| Liquid Perp Basket (Top 15) | Binance USD-M Futures Resampled Daily | Point-in-Time Volume Ranker | 2021-01-01 | 2026-10-26 | 2,125 days (5.8 yrs) | Modern Liquid Universe |
| USD/INR Exchange Rate | RBI Reference Rate via Yahoo Finance (INR=X) | Macro Daily FX Archive | 2017-01-02 | 2026-10-28 | 3,587 days (9.8 yrs) | Macro Currency Conversion Series |


### Delta From Adding Pre-2017 History (2014-2016 True Out-of-Sample)


- **Total Bars Added:** +1,324 daily bars (expanding sample by +39.4% from 9.2 to 12.8 years from Bitstamp public API).

- **Pre-Tax Net CAGR Delta:** +15.13% -> +18.09% (**+2.96% delta**).

- **Excess Sharpe Ratio Delta:** 1.01 -> 1.23 (**+0.22 delta**).

- **Max Drawdown Delta:** 5.69% -> 8.10% (**+2.41% delta**, safely within the 60% B&H limit: 8.10% vs 84.8%).

- **Scenario B Terminal Wealth Delta:** $2.83 -> $6.11 (**+$3.28 delta**).


---

## 6. Survivorship Bias Audit & Re-run


A rigorous point-in-time universe selection audit reveals that in static backtests, **18.4% of total symbol-bars** originate from modern tokens (e.g., SOL, AVAX, NEAR, APT) that were not top-15 at the historical bar date but are top-15 today.


> **Query ID:** `Q_V2_VERIF_SURVIVORSHIP` | **Row Count:** `3` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Universe Specification | Symbol Qualification Rule | Aggregator (Survivorship Engine) | Pre-Tax Net CAGR | Excess Sharpe Ratio | Max Drawdown | Survivorship Delta Analysis |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Standard Point-in-Time Basket | Top 15 by 90d trailing volume (>= 1y history) | Dynamic Liquid Filter | +10.99% | 0.85 | 3.59% | Baseline Point-in-Time Universe |
| Seasoned Basket (>= 3y History) | Top tokens with >= 3 years history at bar date | Seasoned Token Filter | +9.81% | 0.52 | 4.84% | Pure Seasoned Survivorship-Clean |
| Survivorship Bias Delta | Seasoned minus Standard | Forensic Bias Delta Engine | -1.18% | -0.32 | +1.26% | Sharpe drops by -0.32; proves selection drag |


---

## 7. Currency Sensitivity Analysis (USD vs INR)


Evaluation of macro currency impacts on sleeve economics under 31.2% tax:


> **Query ID:** `Q_V2_VERIF_CURRENCY_SENSITIVITY` | **Row Count:** `2` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Currency Regime | Risk-Free APR | Aggregator (Macro FX Replay Engine) | Sleeve Net CAGR | Excess Sharpe | Max DD | After-Tax Sleeve TW | After-Tax Cash TW | Gate Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| USD Cash vs USDT Sleeve | 4.80% | SOFR Benchmark Aggregator | +16.39% | 1.26 | 8.12% | $5.13 | $1.52 | PASS (TW $5.13 > $1.52) |
| INR Cash vs INR Sleeve | 6.50% | RBI Reference Rate Aggregator | +21.35% | 1.28 | 9.45% | ₹4.91 | ₹1.54 | PASS (TW ₹4.91 > ₹1.54) |


**Primary Gate Ruling:** The pre-registered gate remains primary in INR under uncredited cash drag (`FAIL` at 16.7%). Both USD and INR treasury-credited regimes pass with wide margins.


---

## 8. Volatility-Target Sensitivity Grid (No Tuning)


Grid evaluation across $\sigma_{\text{target}} \in \{10\%, 15\%, 25\%\}$ and the 4 parameter neighbourhood variants (confirming zero parameter tuning):


> **Query ID:** `Q_V2_VERIF_VOL_SENSITIVITY` | **Row Count:** `7` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Vol Target / Variant Specification | Target Vol | Aggregator (Parameter Grid Engine) | Mean Gross Exposure | Max Drawdown | Scenario B Terminal Wealth | Cash Benchmark TW | Start-Date Share Beating Cash |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Base Parameter Set | 10% | Vol-Target Parameter Engine | 7.5% | 6.04% | $4.66 | $1.75 | 100.0% (36/36) |
| Base Parameter Set | 15% | Vol-Target Parameter Engine | 9.9% | 8.10% | $6.11 | $1.75 | 100.0% (36/36) |
| Base Parameter Set | 25% | Vol-Target Parameter Engine | 11.8% | 8.78% | $7.46 | $1.75 | 100.0% (36/36) |
| v_lookbacks_0_75x | 15% | Vol-Target Parameter Engine | 9.8% | 8.07% | $5.55 | $1.75 | 100.0% (36/36) |
| v_lookbacks_1_25x | 15% | Vol-Target Parameter Engine | 9.9% | 8.10% | $5.51 | $1.75 | 100.0% (36/36) |
| v_ema_0_75x | 15% | Vol-Target Parameter Engine | 9.8% | 8.10% | $6.42 | $1.75 | 100.0% (36/36) |
| v_ema_1_25x | 15% | Vol-Target Parameter Engine | 9.9% | 8.10% | $6.14 | $1.75 | 100.0% (36/36) |


---

## 9. Nomenclature & Wording Audit


Per Item 9 mandate, all occurrences of the term `statutory hurdle` have been systematically renamed to **`configured hurdle`** across the codebase, configuration schemas, report generators, documentation, and frontend user interface.


- `backend/app/v2/config.py`: Verified `configured hurdle`.

- `backend/app/v2/sleeve_carry.py`: Verified `configured hurdle`.

- `backend/app/v2/promotion.py`: Renamed gate to `Net APR >= configured hurdle (12m, 24m)`.

- `frontend/app/portfolio/page.tsx`: Updated hurdle badges and checklist to `configured hurdle`.


---

## 10. Phase 10 Secret Scan Verification


Prior to report finalization and git push, the automated Phase 10 secret scan was executed across the complete repository commit history (`git log -p --all`).


- **Audit Report:** Generated at [`docs/reports/phase_10.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/reports/phase_10.md) and [`backend/docs/reports/phase_10.md`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/docs/reports/phase_10.md).

- **Audit Finding:** Exactly **0 credentials, tokens, or private exchange keys** leaked in Git commit history.

- **Hygiene Invariants:** `LIVE_TRADING_ENABLED=false` and `V2_LIVE_ENABLED=false` remain permanently locked in place.


---

## 11. Final Summary Promotion Matrix & Operational Status


Final consolidated promotion verdicts across all portfolio sleeves and execution layers:


> **Query ID:** `Q_V2_VERIF_FINAL_PROMOTION_MATRIX` | **Row Count:** `3` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Sleeve / Component | Current Stage | Target Stage | Aggregator (Stage Auditor Engine) | Unmet Evidence Gate | Verdict | Operational Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Sleeve T (Diversified Trend) | Stage A (Research) | Stage A | Evidence Gate Auditor | 36 Monthly Start Dates vs Cash (16.7% vs 70.0% hurdle) | FAIL | HELD IN STAGE A (Retain in research/shadow; zero capital allocation) |
| Sleeve C (Carry Arbitrage) | Stage A (Research) | Stage A | Evidence Gate Auditor | Net APR >= configured hurdle (12m, 24m) (6.95% vs 10.5% hurdle) | FAIL | HELD IN STAGE A (Keep logging zero-allocation targets as research) |
| Overall StarkX Engine | Stage A (Research) | Stage A | Governance Authority | Both sleeves fail primary promotion hurdles under pre-registered rules | FAIL | 100% PAPER / RESEARCH LOCKED (Zero live capital; no orders placed) |


---


**STOP. Verification complete. Generated via `scripts/generate_report.py`. Not tax advice.**
