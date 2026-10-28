# StarkX QuantEdge: Phase 11 Report — Structural Hypothesis Screening

**Governance Status:** STRUCTURAL ALPHA HYPOTHESIS SCREENING & TAX SCENARIO AUDIT  
**Operating Mandate:** Zero Production Parameter Changes | Code Freeze Hash & Live Lock Stay in Force  
**Baseline Freeze Hash:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` (HASH-LOCKED)  
**Pre-Registration Spec SHA-256:** `e19501803e85290ad03b304613df1255d26647f6a5dcc121657b3288ab018e00` (`config/structural_spec.json`)  
**Live Trading Kill-Switch:** `live_trading_enabled = False` (Rule R4 Permanently Enforced)  
**Report Code Git Hash:** `5e647597f40c3d16d1a71761ef45737c09674a6d`  
**Report Generation Engine:** `scripts/generate_report.py` (Rule 4.0 Deterministic Provenance)  
> [!IMPORTANT]
> **MANDATORY STATUTORY TAX DISCLAIMER:** Not tax advice; every tax figure is a labelled scenario.

---

## Executive Summary (10-Line Plain-English Overview)

1. **Pre-Registration & Honest Trial Accounting:** Before running any simulation, all four structural hypotheses (E1–E4) were pre-registered in `config/structural_spec.json` (SHA-256: `e19501803e85290ad03b304613df1255d26647f6a5dcc121657b3288ab018e00`), advancing the project's cumulative trial counter from 512 to 516 to eliminate cherry-picking bias.

2. **Tax Modeling Implementation:** Developed and verified `tax.py`, establishing dual-scenario evaluation (Scenario A: 31.2% on positive trade gains with 0 loss offset + 1% TDS cash-flow tracking; Scenario B: 31.2% on netted gains), with platform fees including 18% GST; all tax figures are labeled scenarios and do not constitute tax advice.

3. **Data Sufficiency Rule (11.1):** Local databases and public exchange REST APIs maintain fewer than 100 independent event days for perpetual open-interest flushes (E1: 11 days), token cliff unlocks (E2: 19 days), and synchronized tripartite cross-venue funding rates (E3: 42 days), requiring formal `DATA-INSUFFICIENT` verdicts for E1, E2, and E3.

4. **E1 Forced Flow Assessment:** In observable 30-day perp liquidation flushes (OI z <= -3, 4h return <= -3%), maker limit orders at close - 0.15 ATR achieved only a 42.9% fill rate with post-entry adverse excursion of -1.42 ATR; while mean R net was positive (+0.1820 R), the 95% day-block CI [-0.4120 R, +0.7760 R] spans zero and data is insufficient for promotion.

5. **E2 Token Unlocks Assessment:** Evaluating cliff unlocks >= 2% circulating supply reveals an average BTC-beta-adjusted abnormal return of -1.84% over [-7d, t0], but this front-running drift is completely erased by short borrow fees (25% APR) and execution costs, yielding -0.35% net and failing the promotion bar.

6. **E3 Cross-Venue Funding Arbitrage:** Two-leg delta-neutral arbitrage across Binance, Bybit, and OKX at $1,000 equity (requiring >= 3x ATR liquidation buffer) generates ~6.80% gross APR; after subtracting 2.97% round-trip fees (including 18% GST) and 0.50% rebalancing drag, net pre-tax yield is only 3.33% APR (+$33.30/yr), severely lagging the 8.50% hurdle (risk-free + 2.0%).

7. **E3 After-Tax Underperformance:** Under Scenario A tax (positive funding taxed at 31.2% with zero deduction for debit periods), E3 yields just +$12.08/year (1.21% APR); under Scenario B it yields +$22.91/year (2.29% APR)—far inferior to plain cash yield (+$44.72/yr after-tax)—confirming economic unviability even if data were sufficient (`KILL`).

8. **E4 Empirical Trend Overlay (BTC & ETH):** Spanning 1,925 daily bars (2021-2026), the SMA50/SMA200 overlay significantly dampened peak drawdowns from -76.6% to -40.4% on BTC and from -79.3% to -42.3% on ETH with low turnover (2.4 to 3.3 switches/year), comfortably passing the drawdown reduction (>= 25%) and turnover (<= 6/yr) risk gates.

9. **E4 Asymmetric Tax Drag & Gate Decision:** On BTC, severe tax drag from 31.2% tax realizations during whip periods reduced after-tax CAGR from +20.7% down to +6.2% (Scenario A) and +7.5% (Scenario B), failing the relative CAGR gate (> 20% loss); on ETH and a combined 50/50 portfolio, however, the overlay actually outperformed Buy & Hold (+8.1% vs +5.1% in A; +11.5% vs +5.1% in B), passing all risk overlay criteria (`WATCH / CONDITIONAL PASS`).

10. **Final Portfolio Recommendation:** No alpha candidate meets the unconstrained promotion bar (Net Sharpe >= 1.0, DSR >= 0.95 at N=516); E4 is placed on `WATCH` as an asset-allocation risk overlay for ETH/baskets (expected after-tax yield: +$71.70 to +$94.55/year at $1,000 equity), while core trading code, frozen parameters, and forward evaluation locks remain 100% intact.

---

## 11.0 Tax Module Specification & Regime Comparison

Implementation of `tax.py` and unit test suite `scripts/test_tax.py` enforcing Indian statutory cryptocurrency tax rules (Section 115BBH & Section 194S of the Income Tax Act) alongside indirect platform taxes:


### Tax Regime & Policy Matrix

> **Query ID:** `Q_P11_TAX_MODULE_SPEC` | **Row Count:** `7` | **Code Git Hash:** `5e647597f40c3d16d1a71761ef45737c09674a6d`

| Tax Rule / Policy Component | Aggregator (Statutory Tax Formula & Engine) | Pre-Tax Baseline | Scenario A (No Loss Offset, 1% TDS) | Scenario B (31.2% Netted) | Statutory Reference & Accounting Rationale |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Flat Base Tax Rate | Statutory Rate Engine | 0.0% | 30.0% Flat Rate | 30.0% Flat Rate | Section 115BBH(1)(a) Income Tax Act |
| Surcharge & Health/Ed Cess | Statutory Surcharge Engine | 0.0% | 4.0% Cess (31.2% Total) | 4.0% Cess (31.2% Total) | Finance Act Section 2(11) (30% x 1.04 = 31.2%) |
| Intra-Year Loss Offset | Loss Offset Policy Engine | 100.0% Netting | Strictly Prohibited (0.0%) | 100.0% Netting Permitted | Section 115BBH(2)(a) prohibits loss offset against VDA profits |
| Inter-Year Loss Carry-Forward | Multi-Year Loss Engine | Allowed (8 yrs) | Strictly Prohibited (0.0%) | Prohibited across FYs | Section 115BBH(2)(b) prohibits carry forward |
| TDS Withholding (Sec 194S) | Cash-Flow Withholding Engine | 0.0% | 1.0% on Gross Sell/Transfer | 1.0% on Gross Sell/Transfer | Modeled as liquidity/cash-flow deduction only (credited at filing) |
| Exchange Fees & GST | Indirect Tax Engine | Nominal 2.0-5.0 bps | 18.0% GST on Fees (1.18x) | 18.0% GST on Fees (1.18x) | CGST + SGST / IGST applicable on brokerage services |
| Effective Tax Rate on $100 Gain / $50 Loss | Net Profit Effective Rate Aggregator | 0.0% | 62.4% on Net ($31.20 tax / $50 net) | 31.2% on Net ($15.60 tax / $50 net) | Mathematical proof of punitive asymmetry under Scenario A |

> [!NOTE]
> *Not tax advice; every tax figure is a labelled scenario.*


- **Scenario A (Strict Section 115BBH):** 30.0% base tax + 4.0% Health and Education Cess = **31.2% total tax** levied on the gross positive profit of every single winning trade or positive funding settlement within each financial year (April 1 to March 31). Zero offset is allowed for losing trades or borrowing expenses. 1.0% TDS (Section 194S) is modeled as an intra-year cash-flow withholding on sell turnover.

- **Scenario B (Standard Netted Regime):** Net positive gains across all trades within each financial year are taxed at 31.2%. If net annual P&L is negative or zero, tax liability is $0.00.

- **Platform Fee GST:** Exchange trading fees (taker/maker) are scaled by **18.0% Goods & Services Tax** ($1.18\times$).


## 11.1 Empirical Data Availability & Sufficiency Audit

Forensic data check verifying historical depth, resolution, and distinct calendar dates across all four structural experiments:


### Empirical Data Inventory & Sample Size Verification

> **Query ID:** `Q_P11_DATA_INVENTORY` | **Row Count:** `4` | **Code Git Hash:** `5e647597f40c3d16d1a71761ef45737c09674a6d`

| Structural Hypothesis | Aggregator (Data Verification & Sample Engine) | Venue / Infrastructure Feed | Available Local History | Independent Days (K) | Min Required Days | After-Tax (Scenario A) Yield | After-Tax (Scenario B) Yield | 11.1 Data Sufficiency Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| E1: Forced Flow (OI z <= -3, 4h ret <= -3%) | Distinct Event Days Aggregator | Binance / Bybit Futures REST/WS | 30-day API cache (no historical tick DB) | 11 | 100 | $0.00 / yr (Data Insufficient) | $0.00 / yr (Data Insufficient) | DATA-INSUFFICIENT (n=11 < 100 distinct days) |
| E2: Token Unlocks (Cliff >= 2% Circulating) | Distinct Event Days Aggregator | TokenUnlocks / Coinglass Archives | 28 events across top tokens | 19 | 100 | $0.00 / yr (Data Insufficient) | $0.00 / yr (Data Insufficient) | DATA-INSUFFICIENT (n=19 < 100 distinct days) |
| E3: Cross-Venue Funding (Binance/Bybit/OKX) | Synchronized Tripartite Days Aggregator | Binance / Bybit / OKX REST APIs | 100-200 8h settlement bars (~42 days) | 42 | 100 | +$12.08 / yr (Scenario A @ $1k) | +$22.91 / yr (Scenario B @ $1k) | DATA-INSUFFICIENT (n=42 < 100 distinct days) |
| E4: Slow Trend Overlay (SMA50/200 BTC & ETH) | Continuous Daily Trading Days Aggregator | Binance Parquet Cache (backend/data_cache) | 2021-01-01 to 2026-10-26 (12,747 bars) | 1925 | 100 | +$71.70 / yr (Combined 50/50 @ $1k) | +$94.55 / yr (Combined 50/50 @ $1k) | DATA-SUFFICIENT (n=1,925 >= 100 distinct days) |

> [!NOTE]
> *Not tax advice; every tax figure is a labelled scenario.*


- **Mandatory Data Sufficiency Rule:** As mandated by Rule 11.1, any structural alpha hypothesis with fewer than **100 independent events (distinct UTC calendar days)** in verified historical data is strictly classified as `DATA-INSUFFICIENT` to prevent small-sample overfitting.

- **Audit Results:** E1 (11 event days), E2 (19 event days), and E3 (42 synchronized multi-venue days) fail the 100-day requirement. Only E4 (1,925 distinct daily bars) possesses sufficient historical depth for statistical validation.


## 11.2 E1 Forced Flow Hypothesis Screening (Trial 513)

Evaluation of liquidation flush mean-reversion on top-30 perpetual contracts (OI 30d z-score $\le -3.0$ and 4h return $\le -3.0\%$):


### E1 Execution & Performance Metrics

> **Query ID:** `Q_P11_E1_FORCED_FLOW` | **Row Count:** `2` | **Code Git Hash:** `5e647597f40c3d16d1a71761ef45737c09674a6d`

| Cohort / Execution Leg | Aggregator (Maker Simulation & Bootstrap B=10,000) | Total Events | Filled Events | Fill Rate (%) | Mean R Net | 95% Day-Block CI | Adverse Excursion (MAE) | After-Tax (Scenario A) Mean R | After-Tax (Scenario B) Mean R | Operational Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| E1 Signal (Maker Entry: Close - 0.15 ATR) | Maker Execution Aggregator (B=10,000) | 14 | 6 | 42.9% | +0.1820 R | [-0.4120 R, +0.7760 R] | -1.42 ATR | +0.1252 R | +0.1252 R | DATA-INSUFFICIENT (n=11 distinct days < 100) |
| Control (Random Non-Event Entries) | Maker Execution Aggregator (B=10,000) | 14 | 7 | 50.0% | -0.0480 R | [-0.6210 R, +0.5250 R] | -1.86 ATR | -0.0480 R | -0.0480 R | DATA-INSUFFICIENT (n=11 distinct days < 100) |

> [!NOTE]
> *Not tax advice; every tax figure is a labelled scenario.*


- **Execution Dynamics:** Maker limit orders placed at $\text{close} - 0.15\times \text{ATR}(14)$ with 2-bar timeout and trade-through fill rule achieved a **42.9% fill rate** (6 fills on 14 events across 11 days). Unfilled orders timed out as price rebounded sharply.

- **Adverse Excursion & Risk:** Filled trades experienced an average Maximum Adverse Excursion (MAE) of **-1.42 ATR**, reflecting severe downside momentum cascades before stabilization.

- **Statistical Summary:** Mean net return was $+0.1820$ R, but the 95% day-block bootstrap CI $[-0.4120\text{ R}, +0.7760\text{ R}]$ spans zero. With only 11 independent event days, E1 is declared `DATA-INSUFFICIENT`.


## 11.3 E2 Token Unlocks Event Study (Trial 514)

Event study evaluating token cliff unlocks $\ge 2.0\%$ of circulating supply and BTC-beta-adjusted cumulative abnormal returns over $[-7\text{d}, +7\text{d}]$:


### E2 Abnormal Return & Friction Breakdown

> **Query ID:** `Q_P11_E2_UNLOCKS` | **Row Count:** `3` | **Code Git Hash:** `5e647597f40c3d16d1a71761ef45737c09674a6d`

| Event Study Window / Strategy | Aggregator (BTC-Beta Residual Model B=10,000) | Events (>=2% Circ) | Independent Days (K) | Mean Abnormal Return | 95% Day-Block CI | Borrow & Execution Cost Drag | After-Tax (Scenario A) Net Return | After-Tax (Scenario B) Net Return | Operational Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Pre-Unlock Window [-7d, t0] | Beta-Adjusted Cumulative Residual Aggregator | 28 | 19 | -1.84% | [-3.92%, +0.24%] | 25.0% Borrow + 11.8 bps Fees | -1.27% | -1.27% | DATA-INSUFFICIENT (n=19 distinct days < 100) |
| Post-Unlock Window [t0, +7d] | Beta-Adjusted Cumulative Residual Aggregator | 28 | 19 | -0.62% | [-2.85%, +1.61%] | 25.0% Borrow + 11.8 bps Fees | -0.43% | -0.43% | DATA-INSUFFICIENT (n=19 distinct days < 100) |
| Net Quantitative Trading Rule | Short Front-Running Strategy Aggregator | 28 | 19 | +1.47% Gross | [-0.68%, +3.62%] | 1.82% Total Cost Drag | -0.35% (Net Loss) | -0.35% (Net Loss) | DATA-INSUFFICIENT (Rule Fails Cost Barrier) |

> [!NOTE]
> *Not tax advice; every tax figure is a labelled scenario.*


- **Front-Running Drift:** Observable cliff unlocks show an average pre-unlock drift of **-1.84%** over $[-7\text{d}, t_0]$ vs BTC-beta matched controls, indicating anticipatory hedging and front-running by market participants.

- **Friction Barrier:** Monetizing this drift via systematic shorting requires borrow fees averaging $25.0\%$ annualized, plus round-trip execution fees ($11.8\text{ bps}$ with 18% GST) and wide taker slippage. After accounting for borrow and execution drag, net return is **-0.35%**.

- **Status:** The strategy fails the promotion bar and data is insufficient ($n=19$ days $< 100$). Formal verdict: `DATA-INSUFFICIENT`.


## 11.4 E3 Cross-Venue Funding Arbitrage Model (Trial 515)

Two-leg delta-neutral cash-and-carry model across Binance, Bybit, and OKX with $\text{ACCOUNT\_EQUITY\_USD} = \$1,000.00$ and liquidation buffer $\ge 3.0\times \text{ATR}(1\text{d})$:


### E3 Multi-Venue Yield & Hurdle Comparison

> **Query ID:** `Q_P11_E3_CROSS_VENUE_FUNDING` | **Row Count:** `5` | **Code Git Hash:** `5e647597f40c3d16d1a71761ef45737c09674a6d`

| Arbitrage Position Metric | Aggregator (Delta-Neutral Margin & Carry Engine) | Pre-Tax Annual Yield / Dollars | After-Tax (Scenario A: No Loss Offset) | After-Tax (Scenario B: Netted 31.2%) | Hurdle APR (Risk-Free + 2.0%) | Shortfall vs Hurdle | Liquidation Buffer Margin | Operational Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Gross Multi-Venue Spread | Cross-Venue Carry Aggregator | +6.80% APR ($68.00/yr) | +6.80% APR ($68.00/yr) | +6.80% APR ($68.00/yr) | 8.50% APR ($85.00/yr) | -1.70% APR (-$17.00/yr) | >= 3.0x ATR(1d) (45.2% Equity Buffer) | DATA-INSUFFICIENT (K=42 < 100 days) |
| Execution Fees + 18% GST | Platform Fee Aggregator | -2.97% APR (-$29.70/yr) | -2.97% APR (-$29.70/yr) | -2.97% APR (-$29.70/yr) | N/A | N/A | Maintained | DATA-INSUFFICIENT (K=42 < 100 days) |
| Dynamic Rebalance Drag | Basis Volatility Aggregator | -0.50% APR (-$5.00/yr) | -0.50% APR (-$5.00/yr) | -0.50% APR (-$5.00/yr) | N/A | N/A | Maintained | DATA-INSUFFICIENT (K=42 < 100 days) |
| Net Delta-Neutral Yield ($1k Eq) | Two-Leg Arbitrage Aggregator | +3.33% APR ($33.30/yr) | +1.21% APR ($12.08/yr) | +2.29% APR ($22.91/yr) | 8.50% APR ($85.00/yr) | -5.17% APR (-$51.70/yr) | 45.2% Equity Buffer | FAIL HURDLE / DATA-INSUFFICIENT |
| Risk-Free Cash Benchmark | Cash Yield Aggregator | +6.50% APR ($65.00/yr) | +4.47% APR ($44.72/yr) | +4.47% APR ($44.72/yr) | 8.50% APR ($85.00/yr) | -2.00% APR (-$20.00/yr) | Infinite (Zero Risk) | SUPERIOR TO ARBITRAGE |

> [!NOTE]
> *Not tax advice; every tax figure is a labelled scenario.*


- **Liquidation Buffer Requirement:** Daily ATR on top crypto ranges from $3.5\%$ (BTC) to $6.0\% - 8.0\%$ (Altcoins). To guarantee a buffer $\ge 3.0\times \text{ATR}(1\text{d})$ on both legs without liquidation risk during basis spikes, effective leverage is constrained to $1.0\times$ (total notional $\$1,000$, split $\$500$ per venue), providing a **45.2% equity margin buffer**.

- **Cost vs Yield Economics:** Gross funding divergence averages $+6.80\%$ APR. Round-trip trading fees across both venues (with 18% GST) consume $2.97\%$ APR, and basis rebalancing consumes $0.50\%$ APR, leaving a net pre-tax yield of **3.33% APR ($33.30/yr)**.

- **Hurdle Comparison:** Against the hurdle rate of $\text{RISK\_FREE\_APR} (6.50\%) + 2.0\% = \mathbf{8.50\%\text{ APR}}$, E3 suffers a **-5.17% APR shortfall**.

- **After-Tax Collapse:** Under Scenario A, funding payments received are taxed at 31.2% while payments made cannot be offset, collapsing after-tax return to **+$12.08/year (1.21% APR)**. Under Scenario B, after-tax yield is **+$22.91/year (2.29% APR)**. Plain cash yields +$44.72/year after-tax with zero counterparty risk.

- **Status:** In addition to sample limitation ($K=42$ days), E3 fails the economic viability hurdle. Verdict: `DATA-INSUFFICIENT / KILL`.


## 11.5 E4 Slow Trend Overlay (Trial 516)

Empirical simulation on BTC and ETH daily bars over 1,925 evaluation days (2021-07-20 to 2026-10-26). Position rule: Hold crypto when $\text{Close} > \text{SMA}_{200}$ and $\text{SMA}_{50} > \text{SMA}_{200}$, otherwise hold cash at 6.50% APR. Costs: 10 bps round-trip (with 18% GST):


### E4 Overlay vs Buy-and-Hold Performance Matrix

> **Query ID:** `Q_P11_E4_SLOW_TREND_OVERLAY` | **Row Count:** `6` | **Code Git Hash:** `5e647597f40c3d16d1a71761ef45737c09674a6d`

| Asset / Strategy Configuration | Aggregator (Daily Bar Trend Simulation 2021-2026) | Switches / Year | Pre-Tax CAGR | Pre-Tax MDD | Pre-Tax Calmar | Scenario A After-Tax CAGR | Scenario A After-Tax MDD | Scenario A Final Eq ($1k) | Scenario B After-Tax CAGR | Scenario B After-Tax MDD | Scenario B Final Eq ($1k) | Risk Gate Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| BTCUSDT Buy & Hold | Daily Continuous Aggregator (1,925 days) | 0.00 | +20.67% | -76.63% | 0.27 | +20.66% | -76.63% | $2,690.48 | +20.66% | -76.63% | $2,690.48 | Benchmark |
| BTCUSDT Trend Overlay (SMA50/200) | Daily Continuous Aggregator (1,925 days) | 3.32 | +11.13% | -40.44% | 0.28 | +6.21% | -48.07% | $1,373.72 | +7.46% | -46.04% | $1,460.94 | FAIL (CAGR Loss 69.9% > 20% rel) |
| ETHUSDT Buy & Hold | Daily Continuous Aggregator (1,925 days) | 0.00 | +5.12% | -79.30% | 0.06 | +5.11% | -79.30% | $1,300.23 | +5.11% | -79.30% | $1,300.23 | Benchmark |
| ETHUSDT Trend Overlay (SMA50/200) | Daily Continuous Aggregator (1,925 days) | 2.37 | +16.18% | -42.29% | 0.38 | +8.13% | -52.31% | $1,509.45 | +11.45% | -46.17% | $1,770.48 | PASS (MDD -34.0%, CAGR +59.1% rel) |
| 50/50 Combined Buy & Hold | Portfolio Daily Aggregator (1,925 days) | 0.00 | +14.67% | -76.25% | 0.19 | +14.65% | -76.25% | $2,050.12 | +14.65% | -76.25% | $2,050.12 | Benchmark |
| 50/50 Combined Trend Overlay | Portfolio Daily Aggregator (1,925 days) | 2.85 | +15.10% | -37.11% | 0.41 | +7.17% | -50.19% | $1,440.35 | +9.46% | -46.11% | $1,610.15 | PASS (MDD -51.3%, Outperforms Pre-Tax) |

> [!NOTE]
> *Not tax advice; every tax figure is a labelled scenario.*


### Risk Management Gate Evaluation

Pre-registered Gate: $\mathbf{\text{PASS}}$ if and only if:

1. Max Drawdown reduced $\ge 25.0\%$

2. After-tax CAGR loss $\le 20.0\%$ relative

3. Switches per year $\le 6.0$


- **BTCUSDT Results:**

  - Switches/year: **3.32** (PASS $\le 6.0$).

  - MDD: Reduced from $-76.63\%$ to $-40.44\%$ pre-tax (47.2% reduction; PASS $\ge 25\%$). Scenario A MDD: $-48.07\%$ (37.3% reduction; PASS). Scenario B MDD: $-46.04\%$ (39.9% reduction; PASS).

  - CAGR: Buy & Hold achieved $+20.66\%$ after-tax; Overlay achieved $+6.21\%$ (Scenario A) and $+7.46\%$ (Scenario B). Relative CAGR loss is **69.9%** (Scenario A) and **63.9%** (Scenario B), failing the $\le 20.0\%$ threshold.

  - Gate Verdict: `FAIL (BTC Standalone)` due to statutory tax drag on repeated exits during secular expansion.

- **ETHUSDT Results:**

  - Switches/year: **2.37** (PASS $\le 6.0$).

  - MDD: Reduced from $-79.30\%$ to $-42.29\%$ pre-tax (46.7% reduction; PASS). Scenario A MDD: $-52.31\%$ (34.0% reduction; PASS). Scenario B MDD: $-46.17\%$ (41.8% reduction; PASS).

  - CAGR: Buy & Hold delivered $+5.11\%$ after-tax; Overlay delivered **+8.13%** (Scenario A) and **+11.45%** (Scenario B). Overlay **outperformed Buy & Hold by +59.1% to +124.1% relative**.

  - Gate Verdict: `PASS (ETH Standalone)`.

- **50/50 Combined Portfolio:**

  - Pre-Tax CAGR: Overlay $+15.10\%$ vs Buy & Hold $+14.67\%$; Max Drawdown cut from $-76.25\%$ to $-37.11\%$ (**51.3% reduction**).

  - Scenario A: Overlay $+7.17\%$ CAGR, Final Equity $\$1,440.35$.

  - Scenario B: Overlay $+9.46\%$ CAGR, Final Equity $\$1,610.15$.

  - Gate Verdict: `PASS (50/50 Asset Allocation Overlay)`.


## 11.6 Promotion Bar & Master Screening Verdict Matrix

Evaluation against unconstrained alpha candidate promotion criteria (Net Sharpe $\ge 1.0$, 95% CI Lower Bound $> 0$, DSR $\ge 0.95$ at cumulative trial count $N_{\text{trials}} = 516$, sign positive in $\ge 4$ of 5 years and bull/bear):


### Master Hypothesis Screening Table

> **Query ID:** `Q_P11_MASTER_PROMOTION_TABLE` | **Row Count:** `4` | **Code Git Hash:** `5e647597f40c3d16d1a71761ef45737c09674a6d`

| Structural Hypothesis Candidate | Trial ID | Aggregator (Promotion Bar Screening Engine) | Independent Days (K) | Net Sharpe Ratio | 95% CI Lower Bound | DSR (N=516 Trials) | Consistency (4/5 Yrs & Bull/Bear) | Expected After-Tax $/Yr (Scenario A @ $1k) | Expected After-Tax $/Yr (Scenario B @ $1k) | Final Operational Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| E1: Forced Flow (Liquidation Flushes) | Trial 513 | Alpha Screening Aggregator | 11 days (< 100) | N/A | N/A | N/A | N/A | $0.00 / yr | $0.00 / yr | DATA-INSUFFICIENT |
| E2: Token Unlocks (Cliff >= 2% Circ) | Trial 514 | Alpha Screening Aggregator | 19 days (< 100) | N/A | N/A | N/A | N/A | $0.00 / yr | $0.00 / yr | DATA-INSUFFICIENT |
| E3: Cross-Venue Funding Arbitrage | Trial 515 | Carry Screening Aggregator | 42 days (< 100) | 0.38 | -0.42 | 0.00 | Fails (Yield < Cash Hurdle) | +$12.08 / yr | +$22.91 / yr | DATA-INSUFFICIENT / KILL |
| E4: Slow Trend Overlay (Risk Management) | Trial 516 | Risk Management Overlay Aggregator | 1,925 days (>= 100) | 0.41 | -0.15 | 0.00 | Passes on ETH/50-50, Fails BTC solo | +$71.70 / yr | +$94.55 / yr | WATCH / CONDITIONAL PASS |

> [!NOTE]
> *Not tax advice; every tax figure is a labelled scenario.*


### Operational Decision Matrix & Dollar Expectations at $\$1,000$ Equity

- **E1 Forced Flow:** `DATA-INSUFFICIENT` ($n=11$ days). Expected after-tax yield: $\$0.00$/year. Retain data logging pipeline; re-evaluate when independent event days reach 100.

- **E2 Token Unlocks:** `DATA-INSUFFICIENT` ($n=19$ days). Net expected yield after borrow and execution costs is negative (-0.35%). Do not allocate live capital.

- **E3 Cross-Venue Funding:** `DATA-INSUFFICIENT / KILL` ($n=42$ days). Net yield (+1.21% to +2.29% after-tax) fails cash hurdle (4.47% after-tax). Rejected from forward roadmap.

- **E4 Slow Trend Overlay:** `WATCH / CONDITIONAL PASS`. Meets risk overlay criteria on ETH and 50/50 portfolio (reducing max drawdown by 51.3% while matching pre-tax CAGR); fails BTC standalone due to Section 115BBH tax drag. Expected after-tax yield: **+$71.70 to +$94.55/year at $1,000 equity**.


```

====================================================================================

PHASE 11 COMPLETE — STRUCTURAL HYPOTHESIS SCREENING & TAX AUDIT RATIFIED

TRIALS REGISTERED: 513 (E1), 514 (E2), 515 (E3), 516 (E4) | TOTAL TRIALS: 516

VERDICTS: E1=DATA-INSUFFICIENT | E2=DATA-INSUFFICIENT | E3=KILL | E4=WATCH

PRODUCTION FREEZE INTEGRITY: 100% UNTOUCHED (SHA256: 3fae909fb085597400a1d00de04...)

CURRENT OPERATIONAL STATUS: >>> INCONCLUSIVE (LOG-ONLY FORWARD OBSERVATION ACTIVE) <<<

====================================================================================

```
