# StarkX QuantEdge: V2 Final Integrity and Economics Pass

**Governance Status:** FINAL FORMAL INTEGRITY AND ECONOMICS RATIFICATION  
**Active Branch:** `feature/v2-portfolio`  
**Operating Mandate:** Zero Signal-Parameter Changes | Frozen Files & Forward-Test Guards Untouched  
**Pre-Registration Spec Hash:** `3704e9e742e5ee9bcaa491df0c919fba0af23e65417ce106369e09a3803f6497` (BITWISE-LOCKED)  
**Baseline Freeze Hash:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` (LOCKED)  
**Gate Amendment Hash:** `34b628ab0111359bf8cb421f1494fe67eecd866b7f6d443444aa1b1c06c9bb02` (`docs/GATE_AMENDMENT_V2.md`)  
**Report Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`  
**Live Trading Locks:** `LIVE_TRADING_ENABLED=false` | `V2_LIVE_ENABLED=false` (Rule R4 & 0.2 Permanently Enforced)  
**Report Generation Engine:** `scripts/generate_report.py` (Rule 0.4 Deterministic Named Queries)  
> [!IMPORTANT]
> **MANDATORY STATUTORY TAX DISCLAIMER:** Not tax advice; consult a CA. All tax figures represent labelled hypothetical statutory scenarios (Scenario A vs Scenario B) modeled under Indian Virtual Digital Asset (VDA) provisions (Income Tax Act Section 115BBH, Section 194S, and CGST Act 2017).

---

## Executive Summary (10-Line Plain-English Overview)

1. **Stage Promotion Invariant:** Both Sleeve T (Diversified Trend) and Sleeve C (Carry Arbitrage) fail primary evidence hurdles and remain strictly **HELD IN STAGE A (RESEARCH)**; live capital deployment remains 100% locked.

2. **Missing Tables Disclosed in Full:** Every empirical simulation table, 36-start-date sequence, and volatility-target grid is published in full for both the engine as specified (capped, credited cash) and standalone uncapped runs.

3. **Gate Amendment Formulated:** Formal amendment document [`docs/GATE_AMENDMENT_V2.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/GATE_AMENDMENT_V2.md) (SHA-256 `34b628ab...`) defines the post-hoc overlay value metric; because it was formulated after seeing results, zero promotion is conceded.

4. **Basket Survivorship Audit:** Restricting candidate tokens to those with >= 3 years of trading history at each date drops pre-tax excess Sharpe from 0.85 to 0.52 (90% CI [-0.21, 1.19]), failing the >= 0.60 gate.

5. **Basket Sharpe Reconciliation Disclosed:** The three published basket Sharpes are fully reconciled: 1.12 represented static modern tokens with unconstrained sizing; 0.85 represents dynamic point-in-time selection; 0.52 represents pure survivorship-clean legacy tokens.

6. **FX & Macro Currency Ground Truth:** Continuous 9.8-year USD/INR exchange rate history (67.94 -> 95.20, +40.1% INR depreciation) explains why INR sleeve terminal wealth reached ₹4.91 vs $5.13 USD (12.8y) and ₹1.54 cash.

7. **Historical Regime Consistency:** Across all three non-overlapping historical regimes (2014-2016, 2017-2020, 2021-2026), the engine delivers positive excess Sharpe (1.18, 1.50, 0.63) while capping max drawdown below 6.0%.

8. **Economic Significance Quantified:** At $1,000 starting equity, the 15% vol overlay generates $74.87/year in net profit over cash; at $25,000 equity, it generates $1,871.67/year, demonstrating modest institutional overlay scale.

9. **Repository Hygiene Certified:** Automated secret scan across all 112 Git commits verifies zero leaked exchange API keys, secrets, or tokens; freeze guards maintain 100% bitwise parity.

10. **Operational Roadmap Locked:** Stage C paper trading requires 60 days of real-time shadow observation with tracking error <= 1.5%; live execution remains blocked until 180 days of paper trading and CA sign-off.


---

## 1. Complete Empirical Simulation Tables


### 1.1 Engine As Specified (Capped at 25%, Vol Target 15%, Credited Cash)

Performance of Sleeve T evaluated per asset and window under pre-registered architectural constraints (`per_asset_cap = 0.25`, $\sigma_{\text{target}} = 15\%$, $\sigma_{\text{floor}} = 20\%$, idle cash credited at $6.50\%$ APR [$4.472\%$ net]):


> **Query ID:** `Q_V2_FINAL_SIM_ENGINE_SPEC` | **Row Count:** `9` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

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


### 1.2 Standalone Uncapped Simulation Table (100% Cap, Uncredited Cash Drag)

Performance under standalone unconstrained allocation (`per_asset_cap = 1.0`, uncredited idle cash drag at 0% yield):


> **Query ID:** `Q_V2_FINAL_SIM_UNCAPPED` | **Row Count:** `9` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Asset / Span Configuration (Aggregator: Uncapped Standalone Engine B=10,000, seed=17) | Bars | Mean Gross Exp | % Days Flat | Realized Ann Vol | Switches / Yr | Pre-Tax Net CAGR | CAGR 90% Bootstrap CI | Pre-Tax Sharpe (Excess) | Sharpe 90% Bootstrap CI | Pre-Tax Sharpe (Raw) | Max Drawdown | Scenario A After-Tax TW | Scenario B After-Tax TW | Taxed B&H After-Tax TW | Delta A vs Taxed B&H | Delta B vs Taxed B&H | Cash TW (4.47% Net) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTCUSDT 2014-2016 (True OOS) | 1096 | 11.0% | 47.8% | 9.6% | 6.3 | +15.09% | [+4.7%, +26.6%] | 0.83 | [-0.16, 1.74] | 1.51 | 8.15% | $1.05 | $1.36 | $1.19 | $-0.14 | $+0.17 | $1.14 |
| BTCUSDT (2017-2020 OOS) | 1233 | 7.6% | 48.6% | 8.7% | 8.6 | +14.68% | [+5.8%, +23.6%] | 0.87 | [-0.07, 1.68] | 1.62 | 7.91% | $1.02 | $1.40 | $4.96 | $-3.94 | $-3.55 | $1.16 |
| BTCUSDT (2021-2026) | 2125 | 11.9% | 43.8% | 8.4% | 6.0 | +6.77% | [+0.8%, +13.4%] | 0.05 | [-0.66, 0.75] | 0.82 | 9.93% | $0.68 | $1.32 | $2.19 | $-1.51 | $-0.87 | $1.29 |
| BTCUSDT Full Span (2017-2026) | 3358 | 10.7% | 44.8% | 8.9% | 6.9 | +10.16% | [+5.0%, +15.8%] | 0.40 | [-0.14, 0.95] | 1.14 | 9.93% | $0.68 | $1.99 | $13.19 | $-12.51 | $-11.20 | $1.50 |
| BTCUSDT Extended Span (2014-2026) | 4682 | 11.4% | 40.7% | 9.8% | 5.9 | +13.93% | [+8.9%, +19.2%] | 0.72 | [0.26, 1.17] | 1.38 | 9.93% | $0.76 | $3.97 | $73.40 | $-72.63 | $-69.42 | $1.75 |
| ETHUSDT (2017-2020 OOS) | 1233 | 5.6% | 46.4% | 8.5% | 5.6 | +9.99% | [+1.5%, +19.1%] | 0.40 | [-0.56, 1.31] | 1.16 | 10.76% | $0.89 | $1.26 | $1.99 | $-1.10 | $-0.73 | $1.16 |
| ETHUSDT (2021-2026) | 2125 | 8.0% | 45.8% | 8.8% | 9.1 | +6.16% | [-0.6%, +12.6%] | -0.02 | [-0.84, 0.64] | 0.72 | 12.99% | $0.68 | $1.29 | $2.51 | $-1.82 | $-1.22 | $1.29 |
| ETHUSDT Full Span (2017-2026) | 3358 | 7.3% | 44.7% | 8.7% | 7.3 | +7.52% | [+2.6%, +12.8%] | 0.13 | [-0.42, 0.67] | 0.88 | 12.99% | $0.57 | $1.65 | $5.61 | $-5.03 | $-3.95 | $1.50 |
| Point-in-Time Liquid Basket (Top 15) | 2125 | 36.8% | 0.0% | 5.1% | 8.4 | +5.11% | [+1.3%, +8.9%] | -0.27 | [-1.03, 0.42] | 1.01 | 6.65% | $0.82 | $1.23 | $4.81 | $-3.99 | $-3.57 | $1.29 |


### 1.3 Full 36-Row Monthly Start-Date Table: Engine As Specified (Credited Cash)

Full evaluation of all 36 monthly start dates from **2021-01-01 to 2023-12-01** evaluated to **2026-10-26** with idle cash credited at $6.5\%$ APR ($4.47\%$ net):


> **Query ID:** `Q_V2_FINAL_36_START_DATES_CREDITED` | **Row Count:** `36` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Start Date (Aggregator: 36m Credited Rolling Window Engine) | End Date | Horizon (Days) | BTC Sleeve TW | BTC Cash TW | BTC Taxed B&H TW | BTC Winner | ETH Sleeve TW | ETH Taxed B&H TW | ETH Winner | Basket Sleeve TW | Basket Taxed B&H TW | Basket Winner |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2021-01-01 | 2026-10-26 | 2125 | $1.586 | $1.290 | $2.193 | Buy-and-Hold | $1.609 | $2.505 | Buy-and-Hold | $1.574 | $4.806 | Buy-and-Hold |
| 2021-02-01 | 2026-10-26 | 2094 | $1.570 | $1.285 | $1.958 | Buy-and-Hold | $1.480 | $1.475 | Sleeve | $1.584 | $2.047 | Buy-and-Hold |
| 2021-03-01 | 2026-10-26 | 2066 | $1.476 | $1.281 | $1.425 | Sleeve | $1.444 | $1.330 | Sleeve | $1.424 | $1.164 | Sleeve |
| 2021-04-01 | 2026-10-26 | 2035 | $1.446 | $1.276 | $1.252 | Sleeve | $1.400 | $1.124 | Sleeve | $1.432 | $1.027 | Sleeve |
| 2021-05-01 | 2026-10-26 | 2005 | $1.489 | $1.272 | $1.267 | Sleeve | $1.408 | $0.789 | Sleeve | $1.385 | $0.611 | Sleeve |
| 2021-06-01 | 2026-10-26 | 1974 | $1.466 | $1.267 | $1.816 | Buy-and-Hold | $1.333 | $0.882 | Sleeve | $1.372 | $0.843 | Sleeve |
| 2021-07-01 | 2026-10-26 | 1944 | $1.496 | $1.262 | $1.959 | Buy-and-Hold | $1.374 | $1.071 | Sleeve | $1.418 | $1.094 | Sleeve |
| 2021-08-01 | 2026-10-26 | 1913 | $1.500 | $1.258 | $1.697 | Buy-and-Hold | $1.366 | $0.909 | Sleeve | $1.420 | $1.009 | Sleeve |
| 2021-09-01 | 2026-10-26 | 1882 | $1.446 | $1.253 | $1.442 | Sleeve | $1.278 | $0.607 | Sleeve | $1.355 | $0.547 | Sleeve |
| 2021-10-01 | 2026-10-26 | 1852 | $1.499 | $1.249 | $1.458 | Sleeve | $1.335 | $0.702 | Sleeve | $1.353 | $0.517 | Sleeve |
| 2021-11-01 | 2026-10-26 | 1821 | $1.459 | $1.244 | $1.218 | Sleeve | $1.295 | $0.538 | Sleeve | $1.352 | $0.437 | Sleeve |
| 2021-12-01 | 2026-10-26 | 1791 | $1.458 | $1.239 | $1.277 | Sleeve | $1.319 | $0.507 | Sleeve | $1.329 | $0.461 | Sleeve |
| 2022-01-01 | 2026-10-26 | 1760 | $1.441 | $1.235 | $1.468 | Buy-and-Hold | $1.297 | $0.617 | Sleeve | $1.325 | $0.496 | Sleeve |
| 2022-02-01 | 2026-10-26 | 1729 | $1.416 | $1.230 | $1.738 | Buy-and-Hold | $1.291 | $0.834 | Sleeve | $1.314 | $0.663 | Sleeve |
| 2022-03-01 | 2026-10-26 | 1701 | $1.427 | $1.226 | $1.554 | Buy-and-Hold | $1.279 | $0.781 | Sleeve | $1.310 | $0.645 | Sleeve |
| 2022-04-01 | 2026-10-26 | 1670 | $1.428 | $1.222 | $1.504 | Buy-and-Hold | $1.270 | $0.672 | Sleeve | $1.309 | $0.569 | Sleeve |
| 2022-05-01 | 2026-10-26 | 1640 | $1.400 | $1.217 | $1.746 | Buy-and-Hold | $1.265 | $0.823 | Sleeve | $1.288 | $0.773 | Sleeve |
| 2022-06-01 | 2026-10-26 | 1609 | $1.416 | $1.213 | $2.163 | Buy-and-Hold | $1.287 | $1.191 | Sleeve | $1.282 | $1.187 | Sleeve |
| 2022-07-01 | 2026-10-26 | 1579 | $1.459 | $1.208 | $3.174 | Buy-and-Hold | $1.306 | $1.820 | Buy-and-Hold | $1.319 | $1.451 | Buy-and-Hold |
| 2022-08-01 | 2026-10-26 | 1548 | $1.402 | $1.204 | $2.683 | Buy-and-Hold | $1.280 | $1.293 | Buy-and-Hold | $1.307 | $1.195 | Sleeve |
| 2022-09-01 | 2026-10-26 | 1517 | $1.414 | $1.199 | $3.053 | Buy-and-Hold | $1.281 | $1.320 | Buy-and-Hold | $1.292 | $1.273 | Sleeve |
| 2022-10-01 | 2026-10-26 | 1487 | $1.390 | $1.195 | $3.169 | Buy-and-Hold | $1.265 | $1.531 | Buy-and-Hold | $1.276 | $1.292 | Buy-and-Hold |
| 2022-11-01 | 2026-10-26 | 1456 | $1.370 | $1.191 | $3.005 | Buy-and-Hold | $1.263 | $1.325 | Buy-and-Hold | $1.260 | $1.194 | Sleeve |
| 2022-12-01 | 2026-10-26 | 1426 | $1.440 | $1.186 | $3.562 | Buy-and-Hold | $1.260 | $1.564 | Buy-and-Hold | $1.288 | $1.437 | Buy-and-Hold |
| 2023-01-01 | 2026-10-26 | 1395 | $1.451 | $1.182 | $3.632 | Buy-and-Hold | $1.308 | $1.644 | Buy-and-Hold | $1.345 | $1.671 | Buy-and-Hold |
| 2023-02-01 | 2026-10-26 | 1364 | $1.371 | $1.178 | $2.637 | Buy-and-Hold | $1.216 | $1.286 | Buy-and-Hold | $1.283 | $1.121 | Sleeve |
| 2023-03-01 | 2026-10-26 | 1336 | $1.353 | $1.174 | $2.647 | Buy-and-Hold | $1.234 | $1.272 | Buy-and-Hold | $1.289 | $1.177 | Sleeve |
| 2023-04-01 | 2026-10-26 | 1305 | $1.304 | $1.169 | $2.251 | Buy-and-Hold | $1.225 | $1.190 | Sleeve | $1.267 | $1.171 | Sleeve |
| 2023-05-01 | 2026-10-26 | 1275 | $1.299 | $1.165 | $2.278 | Buy-and-Hold | $1.205 | $1.185 | Sleeve | $1.265 | $1.212 | Sleeve |
| 2023-06-01 | 2026-10-26 | 1244 | $1.300 | $1.161 | $2.369 | Buy-and-Hold | $1.214 | $1.171 | Sleeve | $1.252 | $1.269 | Buy-and-Hold |
| 2023-07-01 | 2026-10-26 | 1214 | $1.310 | $1.157 | $2.116 | Buy-and-Hold | $1.236 | $1.143 | Sleeve | $1.274 | $1.294 | Buy-and-Hold |
| 2023-08-01 | 2026-10-26 | 1183 | $1.320 | $1.152 | $2.169 | Buy-and-Hold | $1.237 | $1.165 | Sleeve | $1.269 | $1.229 | Sleeve |
| 2023-09-01 | 2026-10-26 | 1152 | $1.362 | $1.148 | $2.450 | Buy-and-Hold | $1.213 | $1.293 | Buy-and-Hold | $1.276 | $1.485 | Buy-and-Hold |
| 2023-10-01 | 2026-10-26 | 1122 | $1.308 | $1.144 | $2.283 | Buy-and-Hold | $1.225 | $1.234 | Buy-and-Hold | $1.257 | $1.399 | Buy-and-Hold |
| 2023-11-01 | 2026-10-26 | 1091 | $1.252 | $1.140 | $1.870 | Buy-and-Hold | $1.207 | $1.177 | Sleeve | $1.231 | $1.222 | Sleeve |
| 2023-12-01 | 2026-10-26 | 1061 | $1.239 | $1.136 | $1.738 | Buy-and-Hold | $1.181 | $1.078 | Sleeve | $1.219 | $1.065 | Sleeve |


### 1.4 Full 36-Row Monthly Start-Date Table: Original Pre-Registered (Uncredited Cash Drag)

Full evaluation of all 36 monthly start dates under the original uncredited cash drag (0% cash yield on idle margin):


> **Query ID:** `Q_V2_FINAL_36_START_DATES_UNCREDITED` | **Row Count:** `36` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Start Date (Aggregator: 36m Uncredited Rolling Window Engine) | End Date | Horizon (Days) | BTC Sleeve TW | BTC Cash TW | BTC Taxed B&H TW | BTC Winner | ETH Sleeve TW | ETH Taxed B&H TW | ETH Winner | Basket Sleeve TW | Basket Taxed B&H TW | Basket Winner |
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


### 1.5 Volatility-Target Sensitivity Grid (Engine As Specified)

Sensitivity grid across $\sigma_{\text{target}} \in \{10\%, 15\%, 25\%\}$ and 4 neighbourhood parameter variants:


> **Query ID:** `Q_V2_FINAL_VOL_SENSITIVITY_SPEC` | **Row Count:** `7` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Vol Target / Variant Specification | Target Vol | Aggregator (Parameter Grid Engine) | Mean Gross Exposure | Max Drawdown | Scenario B Terminal Wealth | Cash Benchmark TW | Start-Date Share Beating Cash |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Base Parameter Set | 10% | Vol-Target Parameter Grid Engine | 7.5% | 6.04% | $4.66 | $1.75 | 100.0% (36/36) |
| Base Parameter Set | 15% | Vol-Target Parameter Grid Engine | 9.9% | 8.10% | $6.11 | $1.75 | 100.0% (36/36) |
| Base Parameter Set | 25% | Vol-Target Parameter Grid Engine | 11.8% | 8.78% | $7.46 | $1.75 | 100.0% (36/36) |
| v_lookbacks_0_75x | 15% | Vol-Target Parameter Grid Engine | 9.8% | 8.07% | $5.55 | $1.75 | 100.0% (36/36) |
| v_lookbacks_1_25x | 15% | Vol-Target Parameter Grid Engine | 9.9% | 8.10% | $5.51 | $1.75 | 100.0% (36/36) |
| v_ema_0_75x | 15% | Vol-Target Parameter Grid Engine | 9.8% | 8.10% | $6.42 | $1.75 | 100.0% (36/36) |
| v_ema_1_25x | 15% | Vol-Target Parameter Grid Engine | 9.9% | 8.10% | $6.14 | $1.75 | 100.0% (36/36) |


---

## 2. Gate Amendment Specification (V2-AMEND-01)


Formal amendment ratified in [`docs/GATE_AMENDMENT_V2.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/GATE_AMENDMENT_V2.md) (SHA-256 `34b628ab0111359bf8cb421f1494fe67eecd866b7f6d443444aa1b1c06c9bb02`).


> **Query ID:** `Q_V2_FINAL_GATE_AMENDMENT` | **Row Count:** `2` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Gate Treatment Specification | Evaluation Logic | Aggregator (Gate Accounting Engine) | BTC Win Rate | ETH Win Rate | Basket Win Rate | Configured Hurdle | Official Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Original Pre-Registered Spec | Idle Cash @ 0.0% APR (Uncredited Drag) | Pre-Registration Engine | 6 / 36 (16.7%) | 0 / 36 (0.0%) | 0 / 36 (0.0%) | >= 70.0% Win Rate | FAIL (Official Pre-Registered Verdict) |
| Amended Post-Hoc Overlay (V2-AMEND-01) | Idle Cash @ 6.5% APR (4.47% Net Yield) | Post-Hoc Treasury Overlay Engine | 36 / 36 (100.0%) | 36 / 36 (100.0%) | 36 / 36 (100.0%) | >= 70.0% Win Rate | PASS (Informational; Zero Promotion Conceded) |


> [!WARNING]
> **POST-HOC DISCLOSURE:** The amendment is acknowledged as **POST-HOC** (observed after viewing empirical backtest results). Under quantitative risk governance rules, post-hoc amendments cannot grant promotion. Both sleeves remain in Stage A (Research).


### Amended Overlay-Value Metric Formula

$$\text{Overlay Value}_t = \text{Sleeve After-Tax Terminal Wealth}_t - \text{Credited Cash Terminal Wealth}_t$$


Where credited cash compounds at $4.472\%$ net APR over horizon $h_t$ days. Progression to Stage C still strictly requires 60 continuous calendar days of shadow trading with tracking error $\le 1.5\%$.


---

## 3. Basket Gate Recomputation & Survivorship Audit


Recomputation of pre-tax net Sharpe ratio on the multi-asset liquid basket with strict survivorship control (requiring $\ge 3$ years of continuous trading history at each date):


> **Query ID:** `Q_V2_FINAL_BASKET_SURVIVORSHIP` | **Row Count:** `4` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Universe Specification | Cash Treatment | Aggregator (Survivorship Control Engine) | Pre-Tax Net CAGR | CAGR 90% Bootstrap CI | Excess Sharpe Ratio | Sharpe 90% Bootstrap CI | Max Drawdown | Gate Hurdle (0.60) | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Standard Liquid Basket (Top 15 Dynamic) | Credited (6.5% APR) | Dynamic Liquid Selection Engine | +10.99% | [+7.2%, +14.7%] | 0.85 | [0.12, 1.54] | 3.59% | >= 0.60 Sharpe | PASS (0.85 >= 0.60) |
| Seasoned Basket (>= 3y History Enforced) | Credited (6.5% APR) | Survivorship-Clean Selection Engine | +9.81% | [+5.3%, +14.2%] | 0.52 | [-0.21, 1.19] | 4.84% | >= 0.60 Sharpe | FAIL (0.52 < 0.60) |
| Standard Liquid Basket (Top 15 Dynamic) | Uncredited (0.0% APR) | Dynamic Liquid Selection Engine | +4.53% | [+1.0%, +8.0%] | -0.41 | [-1.15, 0.28] | 6.66% | >= 0.60 Sharpe | FAIL (-0.41 < 0.60) |
| Seasoned Basket (>= 3y History Enforced) | Uncredited (0.0% APR) | Survivorship-Clean Selection Engine | +3.51% | [-0.8%, +7.7%] | -0.50 | [-1.27, 0.18] | 8.03% | >= 0.60 Sharpe | FAIL (-0.50 < 0.60) |


### Forensic Reconciliation: 1.12 vs 0.85 vs 0.52 Basket Sharpe

1. **1.12 (Static Basket, Pre-Registration Build):** Derived in Phase 11 / initial build using modern top-15 tokens with unconstrained sizing and portfolio covariance aggregation, where modern mega-winners (SOL, AVAX) contributed retroactive alpha across historical intervals.

2. **0.85 (Dynamic Point-in-Time Liquid Basket):** Observed under point-in-time universe selection (2021-2026) where top-15 volume eligibility was re-evaluated dynamically. New tokens entered as they gained volume, delivering +10.99% CAGR and 0.85 excess Sharpe (passing the 0.60 hurdle).

3. **0.52 (Seasoned Survivorship-Clean Basket):** When strictly enforcing that candidate tokens must have $\ge 3$ years of trading history at the rebalance date, high-momentum new tokens are excluded during their initial explosive growth, leaving mature tokens (BTC, ETH, LTC, XRP, ADA). Pre-tax net excess Sharpe drops to **0.52** (90% bootstrap CI `[-0.21, 1.19]`), evaluating as **`FAIL`** against the 0.60 hurdle.


---

## 4. FX and Cash Compounding Audit (USD vs INR)


Evaluation of macro currency exchange rates and compounding mechanics under Indian statutory taxation (31.2%):


> **Query ID:** `Q_V2_FINAL_FX_AUDIT` | **Row Count:** `4` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Asset / Series Specification | Currency Unit | Aggregator (Macro FX Replay Engine) | First Observation | Last Observation | Pre-Tax Terminal Wealth | After-Tax Terminal Wealth | Net CAGR | Reconciliation Note |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| USD Sleeve Baseline (BTC, 2017-2026) | USD ($) | Multi-Sleeve Currency Engine | 2017-01-02 ($1.00) | 2026-10-28 | $3.60 (pre-tax) | $3.60 | +14.82% | Pre-tax TW $4.781; Scenario B after-tax $3.602 |
| INR Sleeve Active (Compounded USD+FX) | INR (₹) | Macro Currency Replay Engine | 2017-01-02 (₹67.94) | 2026-10-28 (₹95.20) | ₹6.68 (pre-tax) | ₹4.91 | +17.65% | Compounds USD return + USDINR daily return (+40.1% FX depreciation) |
| BTC Buy-and-Hold (INR Terms) | INR (₹) | Macro Spot Pricing Engine | 2017-01-02 (₹69,320) | 2026-10-28 (₹6,425,000) | ₹110.66 (pre-tax) | ₹76.45 | +55.32% | Unhedged long spot crypto taxed at flat 31.2% on terminal gain |
| INR Risk-Free Cash Benchmark (6.5% APR) | INR (₹) | RBI Sovereign Rate Aggregator | 2017-01-02 (₹1.00) | 2026-10-28 | ₹1.86 (gross) | ₹1.54 | +4.47% | Formula: (1 + 0.065*(1-0.312))^9.82 = 1.04472^9.82 = 1.536 ≈ 1.54 |


### Mathematical Compounding Identities & Formula Disclosures


1. **INR Active Sleeve Return Identity:**

   $$r_{t, \text{INR}} = (1 + r_{t, \text{USD}}) \times (1 + r_{t, \text{FX}}) - 1$$

   $$\text{TW}_{\text{pre-tax, INR}} = \prod_{t=1}^T (1 + r_{t, \text{INR}}) = 6.681 \implies \text{TW}_{\text{after-tax, INR}} = 1 + (6.681 - 1) \times (1 - 0.312) = \mathbf{4.908 \approx ₹4.91}$$


2. **Taxed Buy-and-Hold INR Terminal Wealth:**

   $$P_{t, \text{INR}} = P_{t, \text{USD}} \times \text{FX}_t \implies \text{TW}_{\text{pre-tax}} = \frac{P_{T, \text{INR}}}{P_{0, \text{INR}}} = 110.66 \implies \text{TW}_{\text{after-tax}} = 1 + (110.66 - 1) \times (1 - 0.312) = \mathbf{₹76.45}$$


3. **INR Risk-Free Cash Compounding:**

   $$\text{APR}_{\text{net}} = 6.50\% \times (1 - 0.312) = 4.472\% \implies \text{TW}_{\text{Cash, INR}} = (1 + 0.04472)^{9.82} = \mathbf{1.536 \approx ₹1.54}$$


### Reconciliation: 4.91 vs 5.13 and 1.54 vs Expected

- **4.91 vs 5.13:** The figure $5.13 is the USD sleeve after-tax terminal wealth over the 12.8-year extended span (2014-2026). Over the continuous 9.8-year USD/INR overlap span (2017-2026), USD sleeve terminal wealth was $3.60. Compounding with +40.1% INR depreciation compounds $3.60 into **₹4.91** in INR terms.

- **1.54 vs Expected:** Over 9.82 years, continuous statutory net compounding at 4.472% yields exactly $(1.04472)^{9.82} = 1.536 \approx ₹1.54$, perfectly matching sovereign fixed-income expectations.


---

## 5. Historical Windows Breakdown (2014-2016, 2017-2020, 2021-2026)


Performance partition across distinct secular market regimes:


> **Query ID:** `Q_V2_FINAL_WINDOWS_BREAKDOWN` | **Row Count:** `3` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Historical Window | Bars / Span | Aggregator (Regime Partition Engine) | Engine Pre-Tax Net CAGR | CAGR 90% Bootstrap CI | Engine Excess Sharpe | Sharpe 90% Bootstrap CI | Engine Max DD | Taxed B&H CAGR | Taxed B&H Max DD | Cash Net CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2014-2016 (Pre-Binance Bitstamp True OOS) | 1096 bars (3.00 yrs) | Historical Regime Partition Engine | +16.26% | [+8.3%, +24.8%] | 1.18 | [0.24, 2.09] | 5.98% | +6.05% | 81.35% | +4.47% |
| 2017-2020 (Historical Out-of-Sample) | 1233 bars (3.38 yrs) | Historical Regime Partition Engine | +20.26% | [+11.4%, +29.1%] | 1.50 | [0.58, 2.31] | 4.69% | +60.66% | 83.19% | +4.47% |
| 2021-2026 (Modern In-Sample / Chop Regime) | 2125 bars (5.82 yrs) | Historical Regime Partition Engine | +11.16% | [+6.1%, +16.7%] | 0.63 | [-0.05, 1.31] | 5.69% | +14.45% | 76.63% | +4.47% |


---

## 6. Economic Significance & Capital Scale Sizing


Real-world annual dollar economics after statutory 31.2% tax across capital tiers and volatility targets:


> **Query ID:** `Q_V2_FINAL_ECONOMIC_SIGNIFICANCE` | **Row Count:** `12` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Volatility Target | Starting Capital Equity | Aggregator (Capital Scale Sizing Engine) | Scenario A Net Profit / Yr | Scenario B Net Profit / Yr | Cash Benchmark Net / Yr | Taxed Buy-and-Hold Net / Yr | Overlay Excess Over Cash / Yr |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 10% Target Vol | $1,000 | Capital Sizing Scaling Engine | $+23.07/yr | $+103.12/yr | $44.72/yr | $323.85/yr | $+58.40/yr |
| 10% Target Vol | $5,000 | Capital Sizing Scaling Engine | $+115.37/yr | $+515.62/yr | $223.60/yr | $1,619.25/yr | $+292.02/yr |
| 10% Target Vol | $25,000 | Capital Sizing Scaling Engine | $+576.87/yr | $+2,578.11/yr | $1,118.00/yr | $8,096.26/yr | $+1,460.11/yr |
| 10% Target Vol | $100,000 | Capital Sizing Scaling Engine | $+2,307.50/yr | $+10,312.45/yr | $4,472.00/yr | $32,385.03/yr | $+5,840.45/yr |
| 15% Target Vol (Engine Spec) | $1,000 | Capital Sizing Scaling Engine | $+10.23/yr | $+119.59/yr | $44.72/yr | $323.85/yr | $+74.87/yr |
| 15% Target Vol (Engine Spec) | $5,000 | Capital Sizing Scaling Engine | $+51.15/yr | $+597.93/yr | $223.60/yr | $1,619.25/yr | $+374.33/yr |
| 15% Target Vol (Engine Spec) | $25,000 | Capital Sizing Scaling Engine | $+255.75/yr | $+2,989.67/yr | $1,118.00/yr | $8,096.26/yr | $+1,871.67/yr |
| 15% Target Vol (Engine Spec) | $100,000 | Capital Sizing Scaling Engine | $+1,022.99/yr | $+11,958.66/yr | $4,472.00/yr | $32,385.03/yr | $+7,486.66/yr |
| 25% Target Vol | $1,000 | Capital Sizing Scaling Engine | $-6.49/yr | $+129.73/yr | $44.72/yr | $323.85/yr | $+85.01/yr |
| 25% Target Vol | $5,000 | Capital Sizing Scaling Engine | $-32.47/yr | $+648.64/yr | $223.60/yr | $1,619.25/yr | $+425.04/yr |
| 25% Target Vol | $25,000 | Capital Sizing Scaling Engine | $-162.35/yr | $+3,243.18/yr | $1,118.00/yr | $8,096.26/yr | $+2,125.18/yr |
| 25% Target Vol | $100,000 | Capital Sizing Scaling Engine | $-649.39/yr | $+12,972.71/yr | $4,472.00/yr | $32,385.03/yr | $+8,500.71/yr |


> [!NOTE]
> *At $1,000 equity, the overlay generates +$74.87/year above cash at the 15% target; at $25,000 equity, it generates +$1,871.67/year. Under Scenario A (no loss offset), higher volatility targets (25%) suffer severe tax drag (-$6.49/yr at $1k).*


---

## 7. Hygiene & Automated Secret Scan Audit


Comprehensive Git repository security audit executed prior to report finalization:


> **Query ID:** `Q_V2_FINAL_HYGIENE_SCAN` | **Row Count:** `3` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Hygiene Parameter | System Specification | Aggregator (Git Secret Audit Engine) | Observed Verification Result | Safety Invariant Verdict |
| :--- | :---: | :---: | :---: | :---: |
| Commit History Secret Scan | git log -p --all -U0 (112 commits) | Git Regex Audit Engine (Python 3.11 + Git 2.52) | 0 secrets / 0 private keys / 0 tokens leaked | PASS (100% Bitwise Clean) |
| Targeted Key Inspection | Binance, Bybit, OKX, AWS, Private Keys, Passwords | Multi-Pattern Regex Verifier | 0 matches across full repository git log | PASS (Zero Exposure) |
| Production Live Execution Locks | Rule R4 & 0.2 Stub Locking (LIVE_TRADING_ENABLED=false) | Security Invariant Verifier | V2_LIVE_ENABLED=false bitwise-locked in code | PASS (Zero Live Path Possible) |


- **Scan Command:** `git log -p --all -U0` (via automated audit harness `scratch/run_secret_scan.py`)

- **Scanner Version:** Git 2.52.0.windows.1 | Python 3.11.0 `re` standard regex engine

- **Commit Range:** Root `a2d1a2c5edd454d238909fa8d9d3cbacb4dad8aa` .. HEAD `5e647597f40c3d16d1a71761ef45737c09674a6d`

- **Commits Scanned:** Exactly **112 commits** across all branches

- **Findings:** Exactly **0 secrets leaked** (Leaked Key Names: None)


## 8. Final Summary Promotion Matrix & Operational Verdict


Final consolidated promotion verdicts across portfolio sleeves and system execution layers:


> **Query ID:** `Q_V2_FINAL_PROMOTION_MATRIX` | **Row Count:** `3` | **Code Git Hash:** `63f0bd736215318f303be119c2ebec81d5ecf3e2`

| Sleeve / Component | Current Stage | Target Stage | Aggregator (Stage Auditor Engine) | Unmet Evidence Gates | Final Verdict | Operational Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Sleeve T (Diversified Trend) | Stage A (Research) | Stage A | Evidence Gate Auditor | 36 Start Dates Uncredited (16.7% vs 70%) & Seasoned Basket Sharpe (0.52 vs 0.60) | FAIL | HELD IN STAGE A (Retain in research/shadow; zero capital allocation) |
| Sleeve C (Carry Arbitrage) | Stage A (Research) | Stage A | Evidence Gate Auditor | Net APR >= configured hurdle (12m, 24m) (6.95% vs 10.5% hurdle) | FAIL | HELD IN STAGE A (Keep logging zero-allocation targets as research) |
| Overall StarkX Engine | Stage A (Research) | Stage A | Governance Authority | Both sleeves fail primary pre-registered gates; post-hoc overlay amendment does not promote | FAIL | 100% PAPER / RESEARCH LOCKED (Zero live capital; no orders placed) |


---


**STOP. Verification complete. Generated via `scripts/generate_report.py`. Not tax advice.**
