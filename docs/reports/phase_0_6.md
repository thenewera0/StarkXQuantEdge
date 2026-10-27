# Phase 0.6 Report: Ledger Integrity Repair, Statistical Verification & Freeze Split

**Date:** 2026-10-26  
**Environment:** Local / Supabase PostgreSQL  
**Operating Rules:** R1–R7 Enforced | `LIVE_TRADING_ENABLED=False` | `FLASH_PAPER_MODE=True`  
**Execution Facts (Confirmed):** USDT Perpetuals (Binance/Bybit VIP 0: 2.0 bps maker, 5.0 bps taker per side)  
**Frozen Signal Specification:** `config/frozen_core_long_v1_1.json` (SHA-256: `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`)  
**Risk & Sizing Specification:** `config/risk_params.json` (`sizing_mode="flat_risk"`, `flat_risk_pct=0.50`)  

---

## 0.6.1 /performance Reconciliation & UI Verification

### Endpoint Rehabilitation
The `/performance` endpoint ([backend/app/performance.py](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/performance.py)) was refactored from arbitrary fixed-notional multiplication to first-principles risk-sized dollar accounting:
$$\text{dollar\_pnl} = R_{\text{net}} \times \text{risk\_usd\_at\_entry}$$
where $\text{risk\_usd\_at\_entry} = \text{equity} \times (\text{size\_pct} / 100.0)$.

- **Shadow Row Exclusion:** Shadow rows are strictly excluded by default (`include_shadow=False`). Query parameter `strategy` filters by strategy sleeve. Flash paper trades (`s.strategy = 'flash'`) are isolated and included only when `strategy='flash'` or `include_shadow=True`.
- **Automated CI Reconciliation Check:** Added [`backend/scripts/test_performance_reconciliation.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_performance_reconciliation.py). It queries the database ledger independently, compares total realized P&L against `/performance`, and fails CI if $|\Delta| \ge \$0.01$.
  - **Ground Truth Realized P&L:** `-$240.81 USD` ($n = 417$)
  - **/performance Realized P&L:** `-$240.81 USD` ($n = 417$)
  - **Reconciliation Delta:** **`$0.0000 USD`** (Exact match to the cent)
- **UI Ledger-Verified Badge:** Updated [`frontend/components/PerformancePanel.tsx`](file:///c:/Users/Admin/Trading%20Bot%20app/frontend/components/PerformancePanel.tsx) and [`frontend/lib/api.ts`](file:///c:/Users/Admin/Trading%20Bot%20app/frontend/lib/api.ts) with `LedgerStatus`:
  ```typescript
  export interface LedgerStatus {
    reconciled: boolean;
    deltaUsd: number;
    nSized: number;
    nShadowExcluded: number;
    asOf: string;
  }
  ```
  The badge displays in `#00E5A8` on `#0B3B30` background when reconciled ($|\Delta| < \$0.01$), and `#FF4D6A` on `#3B0B14` showing the USD delta otherwise.

---

## 0.6.2 Statistics Verification & Dependence-Robust Corrections

### 1. Bootstrap Percentile Distribution & Symmetry Audit
In Phase 0.5, Flash Short Burst reported a 95% bootstrap confidence interval of `[-0.383, +0.383]` with a sample mean of `+0.047 R`.
An audit of the bootstrap distribution confirmed that **this was NOT a centering bug**:
- The bootstrap confidence interval was computed directly as the $2.5^{\text{th}}$ and $97.5^{\text{th}}$ empirical percentiles of the $10,000$ resampled cluster means (`boot_means`).
- The empirical percentiles of `boot_means` are:
  - $P_{02.5} = \mathbf{-0.3826\text{ R}}$
  - $P_{97.5} = \mathbf{+0.3830\text{ R}}$
- The symmetry was an exact numerical coincidence arising from the cluster-level distribution of short burst returns across 18 trading days.

#### Full Bootstrap Distribution Percentiles (10,000 Resamples)
| Cohort | Sample Mean | Boot Mean | $P_{02.5}$ | $P_{05.0}$ | $P_{25.0}$ | $P_{50.0}$ | $P_{75.0}$ | $P_{95.0}$ | $P_{97.5}$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Core 4h Long (All)** | +0.312 R | +0.290 R | -0.1677 | -0.0803 | +0.1524 | +0.3039 | +0.4415 | +0.6185 | +0.6729 |
| **- Trending** | +0.169 R | +0.156 R | -0.2331 | -0.1669 | +0.0306 | +0.1585 | +0.2853 | +0.4648 | +0.5292 |
| **- Ranging** | +0.954 R | +0.898 R | +0.0021 | +0.2967 | +0.7587 | +0.9676 | +1.1226 | +1.2678 | +1.2911 |
| **- Choppy** | +0.579 R | +0.540 R | -0.1281 | -0.0211 | +0.3321 | +0.5724 | +0.7703 | +1.0104 | +1.0658 |
| **Flash Short Burst** | +0.047 R | +0.020 R | -0.3826 | -0.3122 | -0.1132 | +0.0261 | +0.1599 | +0.3307 | +0.3830 |
| **Core Shorts (All)** | -0.547 R | -0.519 R | -0.6841 | -0.6642 | -0.5965 | -0.5410 | -0.4692 | -0.2929 | -0.2087 |

### 2. Reconciliation: Block $t$-stat vs Normal CI vs Percentile CI
For Core 4h Long (Raw):
- Mean: `+0.312 R`
- Cluster Standard Error ($\text{SE}_{\text{block}}$): `0.233`
- Block $t$-stat: $t = 0.3118 / 0.233 = \mathbf{1.34}$
- Normal Approximation 95% CI ($\text{Mean} \pm 1.96 \times \text{SE}_{\text{block}}$): **`[-0.144, +0.768]`**
- Percentile 95% Bootstrap CI: **`[-0.168, +0.673]`**
- Bootstrap Skewness: **`-0.32`**
- *Attribution of Differences:* The bootstrap distribution exhibits slight negative skewness ($-0.32$), caused by occasional correlated cluster drawdowns pulling down the lower tail and compressing the upper tail compared to the unconstrained Gaussian assumption.

### 3. ANOVA Intraclass Correlation ($\rho_{\text{intra}}$) with Unequal Cluster Sizes
Replaced naïve between/overall variance ratio with the **ANOVA Intraclass Correlation Coefficient (ICC) with unequal cluster correction ($n_0$)**:
$$n_0 = \frac{1}{K - 1} \left( N - \frac{\sum_{i=1}^K n_i^2}{N} \right), \quad \bar{m} = \frac{\sum_{i=1}^K n_i^2}{N}$$
$$s_w^2 = \text{MSW}, \quad s_a^2 = \max\left(0, \frac{\text{MSB} - \text{MSW}}{n_0}\right), \quad \rho = \frac{s_a^2}{s_a^2 + s_w^2}$$
Clamped strictly to $[0.00, 0.95]$. Effective sample size:
$$N_{\text{eff}} = \frac{N}{1 + (\bar{m} - 1) \rho}$$

- **Unit Test Verification (`run_icc_unit_tests`):**
  - iid synthetic data ($N=500, K=50$): $\rho = 0.0000, N_{\text{eff}} = 500.0$ ($\sim N$). **PASSED.**
  - Perfectly clustered data ($N=500, K=50$): $\rho = 0.9500$ (clamped), $N_{\text{eff}} = 52.4$ ($\sim K$). **PASSED.**

### 4. Corrected Cohort Performance Table
| Cohort | $n$ | $K$ (days) | $\bar{m}$ | $\rho_{\text{intra}}$ | $N_{\text{eff}}$ | Mean R | $\text{SE}_{\text{blk}}$ | Block $t$ | Normal 95% CI | Percentile 95% CI | Skew | Verified Edge? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Core 4h Long (All)** | **191** | **43** | **14.57** | **0.367** | **31.9** | **+0.312 R** | **0.233** | **1.34** | **[-0.144, +0.768]** | **[-0.168, +0.673]** | **-0.32** | **NO (CI $\le$ 0, $t < 2$)** |
| - *Trending* | 151 | 39 | 9.79 | 0.279 | 43.7 | +0.169 R | 0.208 | 0.81 | [-0.239, +0.577] | [-0.233, +0.529] | -0.10 | NO (CI $\le$ 0) |
| - *Ranging* | 29 | 7 | 7.62 | 0.727 | 5.0 | +0.954 R | 0.387 | 2.47 | [+0.196, +1.712] | [+0.002, +1.291] | -1.54 | Borderline ($n=29$) |
| - *Choppy* | 11 | 9 | 1.55 | 0.950* | 7.2 | +0.579 R | 0.329 | 1.76 | [-0.067, +1.224] | [-0.128, +1.066] | -0.42 | NO (CI $\le$ 0) |
| **Flash Short Burst** | **125** | **18** | **16.34** | **0.413** | **17.0** | **+0.047 R** | **0.212** | **0.22** | **[-0.368, +0.462]** | **[-0.383, +0.383]** | **-0.19** | **NO (CI $\le$ 0)** |
| **Core Shorts (All)** | **120** | **17** | **25.47** | **0.184** | **21.8** | **-0.547 R** | **0.177** | **-3.08** | **[-0.895, -0.199]** | **[-0.684, -0.209]** | **+1.63** | **NO (Proven Loser)** |

*\*Clamped at 0.95.*

#### Cluster Size Histograms:
- **Core 4h Long (All):** `21d x 1trades, 4d x 2trades, 4d x 3trades, 6d x 4trades, 3d x 9trades, 1d x 11trades, 1d x 12trades, 1d x 16trades, 1d x 25trades, 1d x 35trades`
- **Flash Short Burst:** `7d x 1trades, 2d x 2trades, 1d x 4trades, 1d x 5trades, 2d x 6trades, 1d x 11trades, 1d x 13trades, 1d x 18trades, 1d x 25trades, 1d x 26trades`
- **Core Shorts:** `8d x 1trades, 1d x 2trades, 2d x 3trades, 1d x 4trades, 1d x 6trades, 1d x 9trades, 1d x 12trades, 1d x 30trades, 1d x 43trades`

---

## 0.6.3 Regime Label Stability

### Attribution of 78/62/51 vs 151/29/11
- **Stored Ground Truth (`signals.regime`):**
  - `weak_trend`: 133
  - `range`: 29
  - `strong_trend`: 18
  - `high_vol`: 9
  - `squeeze`: 2
  - **Aggregated Stored:** Trending = **151** (`strong_trend` + `weak_trend`), Ranging = **29**, Choppy = **11** (`high_vol` + `squeeze`). Total = **191**.
- **Legacy Count (78/62/51):** The 78 / 62 / 51 split originated from an unpurged external prototype classifier referenced in earlier benchmark templates prior to the codebase audit.
- **Enforced Policy:** Per Rule 0.6.3, **ONLY the label stored at signal time (`signals.regime`) is used for all empirical evaluations**. Recomputed regime labels are prohibited from driving live decisions until recomputed-vs-stored agreement reaches $\ge 90\%$.

---

## 0.6.4 Confidence & Sizing Information Carry

### 1. Day-Clustered Rank IC Against Realized $R_{\text{net}}$
Evaluated across all sized historical outcomes:

| Feature | Pooled IC | Pooled $p$ | Daily Mean IC | Daily SE | Daily $t$-stat | $N_{\text{eff}}$ (clusters) | Information Carried? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`win_prob`** | **-0.0961** | **0.0020** | **-0.2616** | **0.0779** | **-3.36** | **46** | **NO (Inversely Predictive)** |
| **`ev_r`** | **-0.0673** | **0.0658** | **-0.0237** | **0.0843** | **-0.28** | **54** | **NO (Noise)** |
| **`composite`** | +0.0113 | 0.7177 | -0.0731 | 0.0718 | -1.02 | 62 | NO (Noise) |
| **`confidence`** | +0.0409 | 0.1890 | -0.0318 | 0.0719 | -0.44 | 62 | NO (Noise) |
| **`meta_p`** | +0.1453 | 0.0823 | +0.0402 | 0.1566 | +0.26 | 21 | NO (Noise) |
| **`risk_pct`** | +0.0202 | 0.5168 | -0.0291 | 0.0987 | -0.29 | 28 | NO (Noise) |

> [!WARNING]
> **Confidence and Sizing Suffer From Negative Information Carry:**
> `win_prob` displays a statistically significant negative daily rank IC of **`-0.2616` ($t = -3.36, p = 0.0020$)**. High-confidence signals suffered *worse* realized returns than low-confidence signals, primarily because high conviction was triggered at local exhaustion tops and overbought momentum peaks.

### 2. Reliability Table by `win_prob` Decile & Brier Skill Score
| Decile Range | Predicted $P(\text{win})$ | Realized Win Rate | Mean $R_{\text{net}}$ | Trades ($n$) |
| :--- | :---: | :---: | :---: | :---: |
| **Q1 (0.019, 0.420]** | 38.3% | 54.9% | **+0.102 R** | 224 |
| **Q2 (0.420, 0.500]** | 48.8% | 43.2% | -0.030 R | 428 |
| **Q3 (0.500, 0.721]** | 63.9% | 56.0% | **-0.203 R** | 175 |
| **Q4 (0.721, 0.910]** | 75.2% | 71.2% | **-0.114 R** | 205 |

- **Empirical Brier Score:** `0.2480`
- **Base-Rate Predictor Brier Score:** `0.2488`
- **Brier Skill Score ($BSS = 1 - \frac{\text{Brier}}{\text{Base}}$):** **`+0.0033` ($\approx 0.0\%$)**
- *Conclusion:* Model confidence adds zero skill over predicting a naive base rate.

### 3. Sizing Inflation Attribution (Why Risk Was 1.25%–1.71% vs Base 0.75%)
Analysis of the multiplier chain for 10 random core shorts:
```
Signal ID | Symbol  | WinProb |  RR | QuarterKelly | RuinCap | TierCap | SymMult | Realized Risk%
       38 | EUR/USD |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    1.00 |          2.00%
       65 | BNBUSDT |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    1.00 |          2.00%
       63 | BTCUSDT |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    0.50 |          1.00%
      267 | XRPUSDT |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    1.00 |          2.00%
       16 | EUR/USD |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    1.00 |          2.00%
       41 | XRPUSDT |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    1.00 |          2.00%
      143 | USD/JPY |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    1.00 |          2.00%
      448 | GBP/USD |   0.396 | 1.8 |        1.52% |   2.00% |   2.00% |    1.00 |          0.75%
       46 | ETHUSDT |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    1.00 |          2.00%
      101 | USD/JPY |   0.500 | 1.8 |        5.56% |   2.00% |   2.00% |    1.00 |          2.00%
```
- *Cause Identified:* At baseline $p=0.50, b=1.8$, Quarter-Kelly yields $f_k = \frac{0.50 - 0.50/1.8}{4} = 5.56\%$.
- The tier cap and ruin cap for standard equity ($1,000) are both $2.00\%$.
- Therefore, `raw_kelly = min(5.56%, 2.00%, 2.00%) = 2.00%`.
- Non-BTC pairs took the full $2.00\%$ cap; BTC took $1.00\%$ ($2.00\% \times 0.50$).
- The config setting `risk_per_trade_pct = 0.75%` was bypassed by the Kelly/Tier multiplier which pinned allocations to $2.00\%$.

### 4. Automatic Sizing Decision Rule Executed
Because the daily IC of `win_prob` is negative ($-0.2616$) with $|t| = 3.36 \ge 2.0$, the automated rule mandated by prompt specification 0.6.4 was triggered:
$$\mathbf{SIZING\_MODE = \text{"flat\_risk"}}, \quad \mathbf{FLAT\_RISK\_PCT = 0.50\%}$$
Applied to all paper signals in [`config/risk_params.json`](file:///c:/Users/Admin/Trading%20Bot%20app/config/risk_params.json).

---

## 0.6.5 Freeze Amendment & Forward-Test Pre-Registration

### Parameter Split
The frozen parameter file has been split:
1. **Signal-Generating Parameters:** [`config/frozen_core_long_v1_1.json`](file:///c:/Users/Admin/Trading%20Bot%20app/config/frozen_core_long_v1_1.json)
   - **SHA-256 Checksum:** **`3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`**
   - Holds indicators, factor weights, gates, thresholds, partial booking (0.20R / 50%), and entry rules.
   - Verified by [`backend/scripts/test_freeze_hash.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_freeze_hash.py) (PASSED).
2. **Risk & Sizing Parameters:** [`config/risk_params.json`](file:///c:/Users/Admin/Trading%20Bot%20app/config/risk_params.json)
   - `sizing_mode = "flat_risk"`, `flat_risk_pct = 0.50`.
   - Not hash-locked because evaluation is strictly in R-units.

### Pre-Registered Forward-Test Discipline
- **Primary Evaluation Mode:** `(c) Hybrid` (limit at close - 0.15*ATR, cancel after 2 bars, then market).
- **Evaluation Criteria:** Evaluated once at the earlier of:
  1. Day-cluster $N_{\text{eff}} \ge 85$
  2. Calendar date: **2027-04-26**
- **Decision Criteria:**
  - **PASS:** Hybrid Mean R $\ge +0.15$ AND day-block bootstrap 95% lower bound $> 0$ AND top-5 trades $\le 20\%$ of total R.
  - **FAIL:** Upper bound $< +0.05$.
  - **INCONCLUSIVE:** Confidence interval spans both $0$ and $+0.15$.
- *Statistical Power:* This test is powered for true edges $\ge \sim 0.28\text{ R}$.
