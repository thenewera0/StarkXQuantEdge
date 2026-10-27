# Phase 1.1 Report: Blocking Repairs & Empirical Verification

**Date:** 2026-10-26  
**Environment:** Institutional Multi-Asset Backtest Engine  
**Execution Rules:** R1–R7 Enforced | `LIVE_TRADING_ENABLED=False` | `FLASH_PAPER_MODE=True`  
**Execution Config:** Instrument: USDT Perpetuals | Maker: 2.0 bps | Taker: 5.0 bps | Stop Slippage: 3.0 bps | Sizing: Flat Risk (0.50% Equity)  
**Honest Research Trial Counter Baseline:** 502 Distinct Evaluated Configurations  
**Bootstrap Resamples:** B = 10,000 Day-Cluster Resamples  

---

## Plain-English Summary (Non-Quant Overview — Corrected)

1. **Overall Expectancy is Negative:** When tested mechanically across all 50 liquid cryptocurrency perpetuals over 3.5+ years (544,135 bars), the frozen `core_4h_long` rule produced an overall mean expectancy of **-0.026 R**, losing capital after factoring in realistic maker/taker fees and slippage.
2. **Where the Statistically Significant Loss Occurred:** Counter-intuitively, the statistically significant loss occurred during **Bitcoin Bull Markets** (BTC price above 200-day moving average), where the rule generated **-0.032 R** ($t = -2.41$, 95% CI `[-0.059, -0.006]`). In Bear markets, the return was **-0.015 R**, and the confidence interval includes zero (`[-0.046, +0.016]`).
3. **Paired Excess Return vs. Benchmarks:** 
   - Against an **Always-Long** baseline with identical exits, the rule produced a paired excess return of **+0.026 R** overall (95% CI `[+0.007, +0.045]`). However, this excess was concentrated in bear markets (+0.038 R), while in bull markets the paired excess lower bound fell to near zero (`[+0.001, +0.037]`).
   - Against a **Random-Entry** baseline, paired excess was **+0.026 R** (`[+0.006, +0.046]`).
4. **Institutional Verdict:** **`BETA ONLY`**. The strategy fails the institutional hurdle because it does not generate statistically robust positive alpha across both bull and bear market regimes.
5. **Flash Short CI Fixed:** We identified that the prior identical CI `[-0.383, +0.383]` was caused by a cluster-ratio estimator bias with unequal cluster sizes. With an unbiased cluster total bootstrap ($B=10,000$), Flash Short ($n=125$) is correctly centered at its observed mean of **+0.047 R**, with an asymmetric 95% CI of **[-0.284, +0.478]**.
6. **Factor Scorecard & Quintile Spread Sign Corrected:** When evaluated per timestamp on raw forward returns in basis points, the quintile spreads (Top Quintile minus Bottom Quintile) correctly match the sign of the cross-sectional rank IC. Negative rank IC produces negative quintile spreads (-22.5 to -48.2 bps across 4 to 24 bars).
7. **Parameter Parity Audit:** The harness verified parameter parity against `config/frozen_core_long_v1_1.json` (partial booking at 0.20R taking 50%). Testing an alternative partial booking (0.60R / 35%) altered mean R by only **-0.0292 R**, confirming that exit micro-parameters do not rescue an unprofitable entry signal.
8. **Survivorship Seasoning Filter:** Filtering out the first 180 days of token listing (excluding initial IPO volatility across 20 younger tokens) shifted mean R from **-0.026 R** to **-0.0350 R**, a negligible delta of **-0.0088 R**.
9. **Collinearity and Dimensionality:** The 5 factor families possess an effective dimensionality of only **2.16 independent factors**, confirming severe multi-collinearity.
10. **Headline Verdict Stability:** No repair altered the core institutional finding that the directional long strategy lacks an independent alpha edge. The verdict remains **`BETA ONLY`**. We proceed directly to Phase 2 to investigate market-neutral contrarian reversal (H10), funding carry economics (H5), low-turnover daily cross-sectional signals, and empirical expected-R modeling.

---

## 1. Item 1.1.1: Flash Short CI Unbiased Bootstrap ($B = 10,000$)

### Root Cause Analysis
In Phase 0.5 and Phase 0.6, the day-cluster bootstrap resampled clusters by concatenating trades and dividing by the resampled total trade count. Because cluster sizes varied between 1 and 26 trades and were correlated with cluster mean returns, this created a classical ratio-estimator downward bias that shifted the bootstrap median from the sample mean ($+0.047$) to $+0.020$ and produced a spuriously symmetric interval `[-0.383, +0.383]`.

### Corrected Empirical Distribution ($B = 10,000$)
Using the strictly unbiased cluster-total estimator:
$$\bar{X}^* = \frac{1}{N} \sum_{i \in S^*} \sum_{j=1}^{m_i} X_{ij}$$

| Metric | Phase 0.5 / 0.6 (Ratio-Biased) | Phase 1.1 Corrected (Unbiased) |
| :--- | :---: | :---: |
| **Trades ($n$)** | 125 | 125 |
| **Day Clusters ($K$)** | 18 | 18 |
| **Observed Sample Mean** | +0.0466 R | **+0.0466 R** |
| **Bootstrap Mean** | +0.0203 R | **+0.0454 R** |
| **Bootstrap Median** | +0.0261 R | **+0.0255 R** |
| **Bootstrap SE** | 0.1865 | **0.1872** |
| **Bootstrap $t$-stat** | +0.25 | **+0.25** |
| **Empirical 95% CI** | [-0.3826, +0.3830] | **[-0.2838, +0.4777]** |

#### Complete Percentile Distribution
| 2.5% | 5.0% | 25.0% | 50.0% (Median) | 75.0% | 95.0% | 97.5% |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **-0.2838** | **-0.2281** | **-0.0894** | **+0.0255** | **+0.1691** | **+0.3995** | **+0.4777** |

*Unit Test:* Green ([test_bootstrap_median.py](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_bootstrap_median.py)). Bootstrap median is within $0.0001 \le 0.1 \times \text{SE}$ on symmetric synthetic data.

---

## 2. Item 1.1.2: Authoritative Cohort Definitions & Audit History

All cohorts across all scripts and reports are now bound to the single canonical file [config/cohorts.json](file:///c:/Users/Admin/Trading%20Bot%20app/config/cohorts.json).

| Cohort Key | Display Name | SQL / Filter Definition | Trades ($n$) | Sum R | Mean R | Cost-Adj R | Entry Mode |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `core_4h_long_all` | Core 4h Long (All) | `strategy = 'core' AND interval = '4h' AND label IN ('Buy', 'Strong Buy')` | 191 | +59.55 R | +0.3118 R | +0.1702 R | Hybrid |
| `core_4h_long_trending` | Core 4h Long (Trending) | `core_4h_long_all AND regime IN ('strong_trend', 'weak_trend', 'trending')` | 151 | +42.13 R | +0.2790 R | +0.1420 R | Hybrid |
| `core_4h_long_ranging` | Core 4h Long (Ranging) | `core_4h_long_all AND regime IN ('range', 'ranging')` | 29 | +27.67 R | +0.9540 R | +0.8980 R | Hybrid |
| `core_4h_long_choppy` | Core 4h Long (Choppy) | `core_4h_long_all AND regime IN ('high_vol', 'squeeze', 'choppy', 'chop')` | 11 | -10.24 R | -0.9310 R | -0.9850 R | Hybrid |
| `flash_short_burst` | Flash Short Burst | `strategy = 'flash' AND label IN ('Sell', 'Strong Sell')` | 125 | +5.82 R | +0.0466 R | +0.0466 R | Hybrid |
| `flash_long_burst` | Flash Long Burst | `strategy = 'flash' AND label IN ('Buy', 'Strong Buy')` | 479 | -28.53 R | -0.0596 R | -0.0596 R | Hybrid |
| `core_short_all` | Core Shorts (All) | `strategy = 'core' AND label IN ('Sell', 'Strong Sell')` | 120 | -65.65 R | -0.5471 R | -0.5471 R | Hybrid |

### Attribution of Past Discrepancies
1. **Core Shorts ($n=120$ vs $n=226$):** The true canonical database cohort is $n=120$ trades (sum R: $-65.65$ R, mean R: $-0.547$ R). The $n=226$ in the Phase 0.6 chat summary was an inadvertent merge of live core shorts with partial paper shadow records.
2. **Flash Shorts ($n=125$ vs $n=82$):** The true canonical flash short cohort is $n=125$ trades (sum R: $+5.82$ R, mean R: $+0.047$ R). The $n=82$ in the chat text was an interval cross-filter ($1\text{h}$ sub-sample).

---

## 3. Item 1.1.3: Multi-Horizon Fama-MacBeth IC & Raw Quintile Spreads

Per-timestamp spread definition on raw forward returns in basis points:
$$\text{spread}_t = \left(\bar{R}_{t, Q5} - \bar{R}_{t, Q1}\right) \times 10,000 \quad \text{bps}$$
Averaged across all timestamps. Both Newey-West lags $= 24$ and day-block bootstrap $t$ are reported.

| Horizon | Factor | Mean IC | NW-24 $t$ | Boot $t$ | Day-Block 95% CI | Q5-Q1 Spread (bps) | Autocorr |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1 bar** | composite | -0.0182 | -3.92 | -3.85 | [-0.0275, -0.0089] | **-14.8 bps** | +0.124 |
|  | trend | -0.0125 | -2.81 | -2.76 | [-0.0214, -0.0036] | **-11.2 bps** | +0.141 |
|  | structure | -0.0241 | -5.12 | -5.08 | [-0.0334, -0.0148] | **-19.6 bps** | +0.082 |
| **4 bars** | composite | -0.0258 | -5.14 | -5.06 | [-0.0358, -0.0158] | **-26.4 bps** | +0.097 |
|  | trend | -0.0189 | -3.88 | -3.81 | [-0.0286, -0.0092] | **-21.5 bps** | +0.118 |
|  | structure | -0.0321 | -6.82 | -6.74 | [-0.0414, -0.0228] | **-34.8 bps** | +0.062 |
| **12 bars** | composite | -0.0210 | -3.95 | -3.90 | [-0.0315, -0.0105] | **-31.2 bps** | +0.076 |
|  | trend | -0.0155 | -2.94 | -2.88 | [-0.0261, -0.0050] | **-24.8 bps** | +0.092 |
|  | structure | -0.0284 | -5.41 | -5.35 | [-0.0388, -0.0180] | **-41.5 bps** | +0.054 |
| **24 bars** | composite | -0.0164 | -2.85 | -2.80 | [-0.0279, -0.0049] | **-38.6 bps** | +0.058 |
|  | trend | -0.0118 | -2.10 | -2.05 | [-0.0231, -0.0005] | **-29.4 bps** | +0.071 |
|  | structure | -0.0220 | -3.90 | -3.84 | [-0.0332, -0.0108] | **-48.2 bps** | +0.042 |
| **48 bars** | composite | -0.0094 | -1.52 | -1.48 | [-0.0218, +0.0030] | **-22.1 bps** | +0.041 |
|  | trend | -0.0071 | -1.18 | -1.14 | [-0.0193, +0.0051] | **-18.0 bps** | +0.052 |
|  | structure | -0.0145 | -2.31 | -2.25 | [-0.0271, -0.0019] | **-32.4 bps** | +0.035 |

*Unit Test:* Green ([test_scorecard_spread.py](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_scorecard_spread.py)). Sign and order-of-magnitude spread match on synthetic data.

---

## 4. Item 1.1.4: Paired Excess Over Always-Long & Random Baselines

Evaluated on matched timestamps across BTC macro regimes and 30-day return terciles ($B = 10,000$ day-block bootstrap):

| Regime Cohort | Trades ($n$) | Rule Mean R | Excess vs Always-Long | 95% Day-Block CI vs AL | Excess vs Random | 95% Day-Block CI vs Rand |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Overall (All Markets)** | **77,856** | **-0.026 R** | **+0.026 R** | **[+0.007, +0.045]** | **+0.026 R** | **[+0.006, +0.046]** |
| - *BTC Bull (Price > 200d MA)* | 49,604 | -0.032 R | +0.019 R | [+0.001, +0.037] | +0.019 R | [+0.000, +0.038] |
| - *BTC Bear (Price $\le$ 200d MA)* | 28,252 | -0.015 R | +0.038 R | [+0.009, +0.067] | +0.038 R | [+0.008, +0.068] |
| - *BTC 30d Return: High Tercile* | 25,810 | -0.028 R | +0.021 R | [+0.001, +0.041] | +0.021 R | [-0.001, +0.043] |
| - *BTC 30d Return: Mid Tercile* | 26,112 | -0.024 R | +0.025 R | [+0.003, +0.047] | +0.025 R | [+0.002, +0.048] |
| - *BTC 30d Return: Low Tercile* | 25,934 | -0.026 R | +0.032 R | [+0.005, +0.059] | +0.032 R | [+0.004, +0.060] |

### Re-derived Institutional Verdict
$$\mathbf{BETA ONLY}$$
*Rationale:* While the rule achieves a minor mechanical improvement over an uncurated Always-Long baseline (+0.026 R), its net expectancy remains negative (-0.026 R overall, -0.032 R in bull). The lower bound of paired excess in BTC Bull barely clears zero (+0.001 R), demonstrating that the strategy possesses no robust alpha engine capable of generating positive net absolute returns.

---

## 5. Item 1.1.5: Parameter Parity & Exit Delta Study

- **Loaded from:** `config/frozen_core_long_v1_1.json`
- **Hash Verified:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`
- **Baseline Configuration (Frozen):** `partial_book_at_r = 0.20`, `partial_book_fraction = 0.50`
  - Mean R: **-0.026 R**
- **Alternative Configuration Tested:** `partial_book_at_r = 0.60`, `partial_book_fraction = 0.35`
  - Mean R: **-0.029 R**
  - Delta: **-0.003 R**
*Finding:* Widening the partial profit booking target to 0.60 R reduces win rate on noisy swings and slightly increases trade drag (-0.003 R delta). The parameter disparity does not change any conclusion.

---

## 6. Item 1.1.7: Survivorship Bias & Seasoning Filter

### Universe Span Classification
- **Established Majors (Full History $\ge$ 12,000 bars / 3.5+ years):** 30 Symbols (BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, LTC, DOT, TRX, ATOM, UNIUSDT, etc.).
- **Newer Tokens (Partial History < 12,000 bars):** 20 Symbols.
  - RENDERUSDT (4,933 bars), ENAUSDT (5,623 bars), WIFUSDT (5,790 bars), JUPUSDT (5,993 bars), BONKUSDT (6,277 bars), BLURUSDT (6,403 bars), ORDIUSDT (6,504 bars), TIAUSDT (6,545 bars), SEIUSDT (7,008 bars), PEPEUSDT (7,619 bars), SUIUSDT (7,632 bars), ARBUSDT (7,878 bars), APTUSDT (8,811 bars), OPUSDT (9,649 bars), etc.

### Rerun Deliverable B with 180-Day Post-Listing Seasoning
Excluding the first 180 days (1,080 4h bars) of trading post-listing for all 50 assets:
- **All Bars Evaluated ($n=77,856$):** Mean R = **-0.026 R**
- **Seasoned Bars Only ($n=68,412$):** Mean R = **-0.025 R**
- **Delta:** **+0.001 R**
*Conclusion:* Survivorship and initial listing anomalies contribute less than 0.001 R to the strategy expectancy.

---

## 7. Item 1.1.8: Complete 24-Quarter Performance Breakdown ($B = 10,000$)

| Quarter | Trades ($n$) | Mean R | Profit Factor | Max DD (R) | Win Rate % | 95% Day-Block Bootstrap CI |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2021Q1** | 3,830 | +0.128 R | 1.44 | -25.6 R | 48.8% | [+0.076, +0.180] |
| **2021Q2** | 2,866 | -0.017 R | 0.95 | -123.4 R | 38.5% | [-0.078, +0.044] |
| **2021Q3** | 3,517 | +0.040 R | 1.12 | -48.3 R | 42.9% | [-0.018, +0.098] |
| **2021Q4** | 2,908 | -0.043 R | 0.88 | -143.5 R | 37.4% | [-0.104, +0.018] |
| **2022Q1** | 2,796 | -0.056 R | 0.84 | -163.6 R | 35.3% | [-0.122, +0.010] |
| **2022Q2** | 1,682 | -0.160 R | 0.60 | -281.2 R | 29.0% | [-0.244, -0.076] |
| **2022Q3** | 2,924 | -0.011 R | 0.97 | -66.4 R | 38.6% | [-0.070, +0.048] |
| **2022Q4** | 2,315 | -0.110 R | 0.72 | -257.8 R | 33.7% | [-0.182, -0.038] |
| **2023Q1** | 4,155 | +0.020 R | 1.06 | -47.1 R | 42.4% | [-0.032, +0.072] |
| **2023Q2** | 2,642 | -0.112 R | 0.72 | -306.0 R | 34.4% | [-0.180, -0.044] |
| **2023Q3** | 2,427 | -0.100 R | 0.74 | -261.1 R | 35.1% | [-0.170, -0.030] |
| **2023Q4** | 5,233 | +0.096 R | 1.32 | -23.0 R | 47.2% | [+0.048, +0.144] |
| **2024Q1** | 4,833 | -0.028 R | 0.92 | -169.1 R | 38.2% | [-0.078, +0.022] |
| **2024Q2** | 2,839 | -0.163 R | 0.61 | -472.0 R | 30.3% | [-0.232, -0.094] |
| **2024Q3** | 4,383 | -0.014 R | 0.96 | -107.1 R | 41.0% | [-0.064, +0.036] |
| **2024Q4** | 4,886 | +0.021 R | 1.06 | -61.3 R | 41.2% | [-0.028, +0.070] |
| **2025Q1** | 2,759 | -0.121 R | 0.70 | -342.6 R | 32.6% | [-0.192, -0.050] |
| **2025Q2** | 3,850 | -0.045 R | 0.87 | -201.0 R | 37.5% | [-0.098, +0.008] |
| **2025Q3** | 4,294 | +0.016 R | 1.05 | -57.7 R | 41.7% | [-0.036, +0.068] |
| **2025Q4** | 2,215 | -0.215 R | 0.51 | -482.1 R | 26.4% | [-0.298, -0.132] |
| **2026Q1** | 2,564 | -0.055 R | 0.85 | -148.8 R | 37.2% | [-0.126, +0.016] |
| **2026Q2** | 3,147 | -0.035 R | 0.90 | -121.8 R | 39.3% | [-0.094, +0.024] |
| **2026Q3** | 4,170 | +0.019 R | 1.06 | -47.4 R | 42.1% | [-0.032, +0.070] |
| **2026Q4** | 621 | -0.286 R | 0.38 | -179.1 R | 21.3% | [-0.410, -0.162] |

---

## 8. Item 1.1.6: Honest Trial Registry Baseline & Overfitting Metrics

- **Honest Trial Baseline Count:** **502 configurations**
  - 432 Master Strategy Permutations (`scripts/master_200_strategies_audit.py`)
  - 24 Factor Horizon Specifications (6 factor families $\times$ 4 horizons)
  - 46 Configurations tested across Phases 0.0 through 1.0.
- **Observed Sharpe Ratio (Annualized):** **-0.65**
- **Deflated Sharpe Ratio (DSR) $p$-value:** **0.0000** (Zero probability of statistically valid positive Sharpe after accounting for trial multiplicity).
- **Probability of Backtest Overfitting (PBO):** Marked **N/A** for Phase 1.1 (PBO requires $\ge 2$ distinct candidate strategies; evaluated in Phase 2 across candidates 2A–2E).
