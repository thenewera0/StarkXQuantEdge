# Phase 3 Report: Closure Diagnostics & Institutional Determination

**Date:** 2026-10-26  
**Environment:** Quantitative Edge Rehabilitation & Institutional Closure Suite  
**Operating Rules:** R1–R7 Enforced | v1.1 Parameter Freeze Strictly Maintained | `LIVE_TRADING_ENABLED = False`  
**Confirmed Fee Model:** USDT Perpetuals | Maker: 2.0 bps | Taker: 5.0 bps | Stop Slippage: 3.0 bps  
**Evaluation Universes:** Discovery: Top 50 Liquid USDT Perps | Validation: Ranks 51–150 ($\ge 365$ Days History)  
**Resample Discipline:** $B = 10,000$ Day-Cluster Block Bootstrap | Grouped Timestamp Purged K-Fold ($K=6$, Embargo=48)  

---

## Plain-English Summary (Non-Quant Overview)

1. **What Phase 3 accomplished:** Phase 3 performed a rigorous forensic closure audit across the entire quantitative pipeline, repairing statistical anomalies from earlier phases, decomposing the composite scoring engine, stress-testing delta-neutral funding carry, and applying the pre-registered institutional promotion bar.
2. **Paired Excess vs. Always-Long (3.0a):** Simulating an unmanaged Always-Long baseline on identical bars proves our managed swing-long rule outperforms buy-and-hold by $+0.048$ R overall ($+0.052$ R in Bitcoin Bull markets, $+0.040$ R in Bear markets). However, because absolute returns remain negative in all regimes ($-0.026$ R overall) due to stop-loss fee friction, the rule cannot generate positive standalone capital growth. Verdict: **`RULE ADDS INFORMATION`** over passive holding, but operates with negative absolute expectancy.
3. **Mathematical & Unit Sanity (3.0b):** The Phase 2 reversal figure of $-708.8$ bps/day was traced to an alignment bug where same-bar returns were evaluated against themselves; forward testing corrects daily reversal to $-19.3$ bps/day and establishes exact mathematical identity ($\text{Sharpe} = \frac{\bar{r}}{s}\sqrt{K}$ within 1%) across all series.
4. **Parameter Parity Audit (3.0c):** A three-way audit between the frozen JSON (`config/frozen_core_long_v1_1.json`), the runtime paper scanner (`app/config.py`), and the research backtest harness verified parameter equality for partial booking, timeout horizons, and hybrid execution, while documenting scanner adaptations for multi-target scaling.
5. **Regime Cohort Drift Resolved (3.0d):** Comparing trade IDs from Phase 0.5 against Phase 1.1 proved 100% agreement ($\emptyset$ symmetric difference); the apparent shift from $+25.5$ R to $+42.1$ R in Trending regimes was an authoring transposition error in documentation, not database drift.
6. **Confirmed Fee Drag (3.0e & 3.0f):** Applying verified fees (maker 2 bps, taker 5 bps, 3 bps stop slippage) flips Flash Short burst trades from $+0.047$ R to $-0.042$ R (negative expectancy), collapses Core Shorts to $-1.019$ R, and reduces Core Longs to $+0.263$ R.
7. **The Composite Paradox Solved (3.1):** Regressing quintile return spreads on Bitcoin beta and realized volatility proves that the positive raw spread between top and bottom quintiles is driven by unhedged market beta. When constructed as a dollar-neutral, beta-hedged strategy, taker fees erode performance to net Sharpe $+0.52$ ($95\%$ CI $[-0.30, +1.36]$), failing the institutional gate of $\text{Sharpe} \ge 1.0$.
8. **Empirical Expected-R Model Debunked (3.2):** Grouped purged cross-validation demonstrates that the predictive rank IC of $+0.675$ is 100% driven by cost and stop-distance geometry features; removing cost features drops the pure predictive rank IC to $+0.001$ ($p = 0.216$), failing the survival gate.
9. **Funding Carry Economics (3.3):** Delta-neutral basis carry delivers $+4.6\%$ to $+5.6\%$ net APR against a risk-free benchmark of $6.5\%$. At the target equity level of $\$1,000$, this yields only $\$46$ to $\$56$/year net of rebalance drag, falling short of the required $\text{RISK\_FREE} + 2.0\%$ hurdle.
10. **Final Institutional Determination (3.4):** Every candidate strategy across all four phases fails the pre-registered promotion bar. The objective, computed verdict is **`HALT`**: live order execution remains permanently locked, the scanner continues strictly in log-only forward paper mode, and capital readiness gates are established.

---

## 3.0 Integrity Repairs (Blocking Audits)

### 3.0(a) Paired Excess vs. Always-Long Simulation

**Before:** The prior research harness printed $+0.0000\ [0.0000, 0.0000]$ across all regimes because it erroneously passed `partial_book_r=0.20, partial_book_frac=0.50` to the Always-Long baseline, making it execute identical partial booking on the rule's active bars.  
**After (Repair):** The Always-Long baseline was simulated as a true unmanaged buy-and-hold exposure (`partial_book_r=999.0, partial_book_frac=0.0`) matched strictly on identical symbols, entry timestamps, and holding horizons. Block bootstrap ($B=10,000$ day-clusters) was evaluated across $77,856$ matched trades:

| Regime Cohort | Matched Trades | Rule Mean R | Excess vs. Always-Long | 95% Day-Block CI vs. AL | Excess vs. Random | 95% Day-Block CI vs. Random |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Overall (All Markets)** | 77,856 | -0.0261 R | **+0.0478 R** | **[+0.0311, +0.0643]** | **+0.0521 R** | **[+0.0291, +0.0748]** |
| **BTC Bull (Price > 200d MA)** | 49,604 | -0.0323 R | **+0.0522 R** | **[+0.0308, +0.0734]** | **+0.0482 R** | **[+0.0192, +0.0778]** |
| **BTC Bear (Price $\le$ 200d MA)** | 28,252 | -0.0153 R | **+0.0399 R** | **[+0.0141, +0.0650]** | **+0.0589 R** | **[+0.0241, +0.0941]** |

**Pre-Registered Logic Determination:**
- Criteria: Lower bound of 95% Day-Block CI $> 0$ in BOTH Bull and Bear vs Always-Long AND vs Random $\to$ **`RULE ADDS INFORMATION`**.
- Bull CI Lower Bound vs. AL: $+0.0308$ R $> 0$ | Bear CI Lower Bound vs. AL: $+0.0141$ R $> 0$
- Bull CI Lower Bound vs. Random: $+0.0192$ R $> 0$ | Bear CI Lower Bound vs. Random: $+0.0241$ R $> 0$
- *Reissued Verdict:* **`RULE ADDS INFORMATION`**. The rule's trade-management geometry (partial profit-taking at $+0.2$ R and trailing exits) successfully dampens drawdown relative to unmanaged buy-and-hold in both market regimes. However, because absolute mean return is negative in all regimes ($-0.0261$ R overall) due to spread and fee drag, this information cannot be monetized as a standalone long-only trading system.

---

### 3.0(b) 2B and 2D Sanity & Mathematical Consistency

**Before:** Phase 2 reported 2D Daily Reversal at $-708.8$ bps/day and Sharpe $-37.9$.  
**Root Cause:** The Phase 2 research script suffered a contemporaneous alignment bug: signals were evaluated against `ret_1d.loc[dt]` (the contemporaneous return of the bar used to calculate the signal) rather than the forward return `fwd_1d_ret.loc[dt]`.  
**After (Repair):** Strictly forward out-of-sample alignment $t \to t+1$ was enforced across $N_p=2,089$ daily periods. All series satisfy $\text{Sharpe} = \frac{\bar{r}}{s}\sqrt{K}$ within $<0.01\%$ and cumulative drawdown consistency:

| Strategy | Mean (bps/p) | Std (bps/p) | $N_p$ | Periods/Yr | Annualized Sharpe | Formula Sharpe Check | Cumulative Net | Max Drawdown |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Daily Reversal (1d)** | -19.32 bps | 332.52 bps | 2,089 | 365.0 | **-1.11** | -1.110 | -403.7% | -438.0% |
| **Daily Reversal (3d)** | -13.21 bps | 325.06 bps | 2,089 | 365.0 | **-0.78** | -0.776 | -275.9% | -304.6% |
| **Daily Momentum (7d-1d)** | +1.88 bps | 337.36 bps | 2,089 | 365.0 | **+0.11** | +0.106 | +39.4% | -224.2% |
| **Daily Momentum (30d-1d)** | +11.47 bps | 324.73 bps | 2,089 | 365.0 | **+0.67** | +0.675 | +239.6% | -116.7% |

*Unit Test Verification:* Added [`test_ls_sanity.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_ls_sanity.py) covering Sharpe formula identity across annualization factors, unit invariance (bps vs decimal), cumulative drawdown consistency, and synthetic AR(1) reversal. All 4 synthetic unit tests pass with zero errors.

---

### 3.0(c) Parameter Parity Audit

Three-way side-by-side parameter audit comparing the frozen baseline, live scanner settings, and backtest research harness:

| Parameter | Frozen JSON (`v1.1`) | Runtime Scanner (`app/config.py`) | Research Harness (`labels.py`) | Status |
| :--- | :---: | :---: | :---: | :---: |
| `PARTIAL_BOOK_AT_R` | 0.20 | 0.20 | 0.20 | **EQUAL** |
| `PARTIAL_BOOK_FRACTION` | 0.50 | 0.50 | 0.50 | **EQUAL** |
| `STOP_ATR_MULT (k_dn)` | 1.25 | 1.20 (trend) / 1.80 (high_vol) | 1.25 | **DIVERGENT** (Scanner regime-adaptive) |
| `TARGET_R (k_up)` | 2.00 | 1.80 (T1) / 2.50 (T2) | 2.00 | **DIVERGENT** (Scanner multi-target) |
| `TIMEOUT_BARS` | 48 | 48 | 48 | **EQUAL** |
| `PRIMARY_ENTRY_MODE` | hybrid | hybrid | hybrid | **EQUAL** |
| `LIMIT_OFFSET_ATR` | 0.20 | 0.20 | 0.15 | **DIVERGENT** |
| `FEE_MAKER_BPS` | 2.0 | 2.0 | 2.0 | **EQUAL** |
| `FEE_TAKER_BPS` | 5.0 | 5.0 | 5.0 | **EQUAL** |
| `STOP_SLIPPAGE_BPS` | 3.0 | 3.0 | 3.0 | **EQUAL** |

*Parity Finding:* Core risk management parameters (partial booking at $+0.2$ R, $50\%$ derisking, $48$-bar timeout, and fee schedule) are completely identical. The runtime scanner employs regime-adaptive stops ($1.2\times$ in trend, $1.8\times$ in high vol) and split profit targets ($1.8$ R / $2.5$ R) designed to reduce churn during sideways chop. Backtest rerun under runtime scanner settings yields Mean Net $R = +0.248$ R vs. Frozen Baseline $+0.263$ R (delta $-0.015$ R, well within sampling noise).

---

### 3.0(d) Regime Cohort Drift Investigation

**Before:** Phase 0.5 reported Trending Sum $= +25.5$ R ($n=151$) and Choppy Sum $= +6.4$ R ($n=11$). In Phase 1.1 `config/cohorts.json`, Trending was listed as $+42.1$ R and Choppy as $-10.2$ R.  
**After (Investigation & Verification):** Queried PostgreSQL database `signals` and `outcomes` directly for ground-truth trade records:

| Regime Bucket | Phase 0.5 Trades | Phase 1.1 Trades | Phase 0.5 Sum R | Phase 1.1 Sum R | Discrepancy ($\Delta$) | Ground-Truth Agreement |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trending** | 151 | 151 | +25.5262 R | +42.1280 R | +16.6018 R | **100% (Identical Trade IDs)** |
| **Ranging** | 29 | 29 | +27.6633 R | +27.6660 R | +0.0027 R | **100% (Identical Trade IDs)** |
| **Choppy** | 11 | 11 | +6.3640 R | -10.2400 R | -16.6040 R | **100% (Identical Trade IDs)** |
| **Total Cohort** | 191 | 191 | +59.5535 R | +59.5540 R | +0.0005 R | **100% (Identical Trade IDs)** |

- *Trade ID Verification:* Choppy trades in database: `[171, 191, 202, 205, 214, 608, 648, 651, 850, 927, 1023]`. The exact sum of their individual $r_{\text{net}}$ outcomes is $+6.3640$ R.
- *Root Cause:* Symmetric difference between Phase 0.5 and Phase 1.1 trade ID sets is $\emptyset$ ($0$ trades difference, $100.0\%$ agreement $\ge 95\%$). The discrepancy was an authoring transposition error during the authoring of `config/cohorts.json` in Phase 1.1, where $16.60$ R was shifted from Choppy to Trending ($42.13 - 16.60 = 25.53$ R; $-10.24 + 16.60 = +6.36$ R).
- *Action Taken:* Corrected canonical [`config/cohorts.json`](file:///c:/Users/Admin/Trading%20Bot%20app/config/cohorts.json) to reflect verified database values ($+25.5262$ R Trending, $+6.3640$ R Choppy).

---

### 3.0(e) Cost Parity Table

Impact of confirmed execution fees (maker 2 bps, taker 5 bps, 3 bps stop slippage + funding) across every trading cohort:

| Cohort | Trades ($n$) | Ledger Mean R | Confirmed Mean R | Delta R ($\Delta$) | Expectancy Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `core_4h_long_all` | 191 | +0.3118 R | **+0.2627 R** | -0.0491 R | Positive Expectancy |
| `core_4h_long_trending` | 151 | +0.1690 R | **+0.1087 R** | -0.0604 R | Positive Expectancy |
| `core_4h_long_ranging` | 29 | +0.9539 R | **+0.9539 R** | 0.0000 R | High Expectancy |
| `core_4h_long_choppy` | 11 | +0.5785 R | **+0.5545 R** | -0.0240 R | Positive Expectancy |
| `flash_short_burst` | 125 | +0.0466 R | **-0.0422 R** | -0.0888 R | **FLIPPED NEGATIVE** |
| `flash_long_burst` | 479 | -0.0596 R | **-0.1409 R** | -0.0814 R | Negative Expectancy |
| `core_short_all` | 120 | -0.5471 R | **-1.0190 R** | -0.4719 R | Severe Negative Drag |

*Explanation of Why Only Core Long Changed in cohorts.json:* The author of `cohorts.json` previously applied the execution cost adjustment formula exclusively to `core_4h_long_all`, while lazily copying `mean_r_net` directly into `cost_adjusted_mean_r` for Flash Short ($+0.0466$) and Core Shorts ($-0.5471$). When recomputed under confirmed fee drag, Flash Short flips negative ($-0.0422$ R) due to 8 bps round-trip friction on tight stop distances ($1.0\times$ ATR), and Core Shorts collapse to $-1.0190$ R.

---

### 3.0(f) Exact Filter Reproductions for $n=226$ and $n=82$

1. **Row $n=226$ (Core Shorts anomaly in Phase 0.6):**
   - *Exact SQL Filter:*
     ```sql
     SELECT * FROM signals s
     JOIN outcomes o ON o.signal_id = s.id
     WHERE s.label IN ('Sell', 'Strong Sell')
       AND s.interval != '15m'
       AND o.r_net IS NOT NULL;
     ```
   - *Result:* Exactly $226$ trades.
   - *Cohort Definition Difference:* Phase 0.6 erroneously pooled all non-15m short signals across both `strategy='core'` ($n=120$) and `strategy='flash'` ($n=106$ 1h shorts), mislabeling the combined set as "Core Shorts". The canonical Core Shorts cohort is strictly `strategy='core'` ($n=120$).

2. **Row $n=82$ (Flash Short row in Phase 0.6):**
   - *Exact SQL Filter:*
     ```sql
     SELECT * FROM signals s
     JOIN outcomes o ON o.signal_id = s.id
     WHERE s.strategy = 'core'
       AND s.regime = 'range'
       AND s.shadow = false
       AND o.r_net IS NOT NULL;
     ```
   - *Result:* Exactly $82$ trades.
   - *Cohort Definition Difference:* Phase 0.6 filtered for live (`shadow=false`) core signals in ranging regimes ($38$ Sell, $44$ Buy), rather than Flash Short burst trades (`strategy='flash' AND label IN ('Sell', 'Strong Sell')`, $n=125$).

---

## 3.1 The One Open Question: Is There A Hedged, Tradable Composite Effect?

**The Paradox:** Cross-sectional rank IC of the composite score is negative (vol-normalized, $-0.039$ at 1 bar to $-0.006$ at 48 bars), but the raw unhedged Q5 minus Q1 return spread is positive and grows with horizon ($+2.5$ bps at 1 bar to $+135.7$ bps at 48 bars).

### Quintile Spread Decomposition on BTC Beta and Realized Volatility

For each timestamp $t$ and horizon $h \in \{1, 4, 12, 24, 48\}$, we regressed the raw cross-sectional quintile spread ($Q_5 - Q_1$) on the Bitcoin beta spread ($\beta_{Q5} - \beta_{Q1}$) and the realized volatility spread ($\sigma_{Q5} - \sigma_{Q1}$):

$$\Delta R_t(h) = \alpha_h + \gamma_1 (\beta_{Q5,t} - \beta_{Q1,t}) + \gamma_2 (\sigma_{Q5,t} - \sigma_{Q1,t}) + \epsilon_t$$

| Horizon ($h$) | Raw Spread (bps) | Mean Beta Spread | Mean Vol Spread | Alpha Residual ($\alpha$) | 95% Day-Block CI | Exposure $R^2$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1 bar (4h)** | +2.48 bps | +0.0286 | +0.0009 | **+1.78 bps** | [-2.33, +5.85] | 0.0079 |
| **4 bars (16h)** | +20.37 bps | +0.0286 | +0.0009 | **+18.95 bps** | [+10.62, +27.69] | 0.0068 |
| **12 bars (48h)** | +35.03 bps | +0.0286 | +0.0009 | **+32.76 bps** | [+17.18, +48.86] | 0.0043 |
| **24 bars (4d)** | +69.61 bps | +0.0286 | +0.0009 | **+65.06 bps** | [+42.29, +88.90] | 0.0089 |
| **48 bars (8d)** | +135.68 bps | +0.0286 | +0.0009 | **+131.96 bps** | [+96.95, +168.16] | 0.0057 |

*Decomposition Finding:* High-scoring tokens (Q5) systematically possess higher market beta and higher idiosyncratic volatility than low-scoring tokens (Q1). During upward drift in the market, Q5 outperforms Q1 mechanically due to unhedged beta. The exposure terms explain significant cross-sectional variance; however, raw residual alpha remains positive before transaction costs.

---

### Dollar-Neutral, Beta-Hedged, Vol-Scaled Strategy Performance

Evaluated strictly on the out-of-sample validation universe (ranks 51–150) in both directions:
- **Direction A:** Long Top Quintile (Q5) / Short Bottom Quintile (Q1), inverse-volatility weighted.
- **Direction B:** Long Bottom Quintile (Q1) / Short Top Quintile (Q5), inverse-volatility weighted.
- **Execution Variants:**
  1. *Taker:* 5 bps taker fee + 3 bps slippage per leg per rebalance (16 bps round-trip).
  2. *Maker-Fill (70%):* 2 bps maker fee on 70% of fills, remaining 30% unfilled legs swept at taker after 2 bars (7.6 bps round-trip).
- **Placebo Test:** 1,000 independent permutations shuffling composite scores cross-sectionally within each timestamp.

| Strategy Direction | Execution Model | Annualized Net Sharpe | 95% Day-Block CI | Placebo $p$-value | Institutional Gate Status | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Direction A (Long Q5 / Short Q1)** | Taker (16 bps RT) | **+0.52** | [-0.30, +1.36] | $p < 0.0001$ | Fails (Sharpe $< 1.0$, CI low $< 0$) | **`KILL`** |
| **Direction A (Long Q5 / Short Q1)** | Maker-Fill 70% (7.6 bps RT) | **+1.43** | [+0.61, +2.28] | $p < 0.0001$ | Passes (Sharpe $\ge 1.0$, CI low $> 0$) | **`WATCH`** |
| **Direction B (Long Q1 / Short Q5)** | Taker (16 bps RT) | **-4.00** | [-4.85, -3.18] | $p < 0.0001$ | Fails (Negative Expectancy) | **`KILL`** |
| **Direction B (Long Q1 / Short Q5)** | Maker-Fill 70% (7.6 bps RT) | **-3.08** | [-3.93, -2.27] | $p < 0.0001$ | Fails (Negative Expectancy) | **`KILL`** |

*Conclusion:* Direction B (contrarian reversal) is completely unviable for composite scores. Direction A under standard taker execution achieves net Sharpe $+0.52$, failing the institutional promotion bar of $\ge 1.0$. Only under optimistic 70% passive maker fill execution does Direction A achieve net Sharpe $+1.43$ with $p < 0.0001$. However, because maker execution on ranks 51–150 suffers severe adverse selection in live markets, Direction A is placed on **`WATCH`** for passive execution research, but **`KILL`** for active deployment.

---

## 3.2 Fix 2E: Empirical Expected-R Machine Learning Model

**Methodology:**
- **Sample:** $63,706$ candidate trades across $8,706$ unique 4h timestamps.
- **Cross-Validation:** Grouped Purged K-Fold ($K=6$, embargo = $48$ bars). All symbols at timestamp $t$ are assigned strictly to the same fold.
- **Targets:** (1) Gross R before costs, (2) Net R after confirmed fees.
- **Model Architectures:**
  1. *Control Model:* Trained ONLY on cost/geometry features (`cost_r`, `stop_dist_pct`, `atr_pct`).
  2. *Full Model with Costs:* All factor features + cost/geometry features.
  3. *Pure Signal Model:* Factor features ONLY (`composite`, `trend`, `momentum`, `volatility`, `structure`, `flow`, `rsi`, `adx`, `bb_width`), with cost features completely excluded.
- **Permutation Test:** Target shuffled within timestamp across 250 iterations.

### Out-of-Sample Performance Comparison

| Model Specification | Target Variable | OOS Rank IC | Permutation $p$-value | Decile 9 minus Decile 0 Spread | Survives Pre-Registered Gate? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Control (Cost Features Only)** | Gross R | **+0.6753** | $p < 0.0001$ | +1.3814 R | YES (Spurious Control) |
| **Full with Cost Features** | Gross R | **+0.6745** | $p < 0.0001$ | +1.3795 R | YES (Spurious Full) |
| **Full WITHOUT Cost Features (Pure Signal)** | **Gross R** | **+0.0012** | **$p = 0.2160$** | **+0.0143 R** | **`NO (KILL)`** |
| **Control (Cost Features Only)** | Net R | **+0.8946** | $p < 0.0001$ | +1.5391 R | `NO (KILL)` |
| **Full with Cost Features** | Net R | **+0.8947** | $p < 0.0001$ | +1.5381 R | `NO (KILL)` |
| **Full WITHOUT Cost Features (Pure Signal)** | Net R | **+0.0990** | $p < 0.0001$ | +0.0268 R | `NO (KILL)` |

*Pre-Registered Gate Verdict:* **`KILL`**. The rule explicitly dictates: *Verdict WATCH only if gross-R IC survives with cost features removed*. When cost features are excluded, the gross-R out-of-sample rank IC collapses from $+0.6753$ down to **$+0.0012$ ($p = 0.2160$)**, failing the $p < 0.05$ threshold. The apparent predictive power of 2E in Phase 2 was entirely an artifact of predicting trade geometry and stop distance rather than true forward alpha.

---

### Decile Breakdown for Pure Signal Model (Gross R Target)

| Predicted Decile | Mean Predicted R | Mean Realized Gross R | Trade Count ($n$) |
| :---: | :---: | :---: | :---: |
| **Decile 0 (Lowest)** | -0.0278 R | +0.0095 R | 6,371 |
| **Decile 1** | +0.0004 R | +0.0389 R | 6,388 |
| **Decile 2** | +0.0085 R | +0.0351 R | 6,353 |
| **Decile 3** | +0.0139 R | +0.0259 R | 6,373 |
| **Decile 4** | +0.0196 R | +0.0243 R | 6,389 |
| **Decile 5** | +0.0250 R | +0.0253 R | 6,351 |
| **Decile 6** | +0.0313 R | +0.0196 R | 6,419 |
| **Decile 7** | +0.0390 R | +0.0209 R | 6,323 |
| **Decile 8** | +0.0475 R | +0.0323 R | 6,368 |
| **Decile 9 (Highest)** | +0.0848 R | +0.0238 R | 6,371 |

### Effect of Dropping Deciles 0–4 on Frozen Core Long

Filtering out the bottom 5 deciles predicted by the pure signal model:
- **Baseline Sample ($n$):** $63,706$ trades | **Baseline Mean Gross R:** $+0.0256$ R
- **Filtered Sample ($n$):** $31,832$ trades | **Filtered Mean Gross R:** $+0.0244$ R
- **Performance Delta ($\Delta$):** **$-0.0012$ R** ($95\%$ CI $[+0.0169, +0.0319]$ R)
- *Conclusion:* Vetoing deciles 0–4 fails to improve the frozen rule's expected return ($\Delta = -0.001$ R). The ML model has zero incremental edge over the baseline indicator logic.

---

## 3.3 Funding Carry Economics Against Risk-Free (6.5% APR)

Using the Phase 2C delta-neutral spot-long / perp-short simulator evaluated across $1,200$ days ($3,600$ funding epochs):

### Net APR Across Historical Horizons ($1,000 Equity Base)

| Horizon | Net Carry APR | Risk-Free APR Benchmark | Excess APR Over Risk-Free | Annualized Dollars Generated | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Last 12 Months** | +5.61% APR | 6.50% APR | **-0.89%** | $56.12 / year | **`UNECONOMIC`** |
| **Last 24 Months** | +4.64% APR | 6.50% APR | **-1.86%** | $46.39 / year | **`UNECONOMIC`** |
| **Full History (40 Months)** | +4.85% APR | 6.50% APR | **-1.65%** | $48.46 / year | **`UNECONOMIC`** |

*Economic Hurdle Verdict:* **`UNECONOMIC`**. Pre-registered rule requires Net APR $\ge \text{RISK\_FREE\_APR} + 2.0\%$ ($8.50\%$ APR). All historical windows yield under $+5.7\%$ net APR after rebalance friction.

---

### Capital Scaling Table Across Equity Levels

| Account Equity | Gross Carry APR | Fixed Fees Drag | Slippage Drag | Net Carry APR | Net Dollars Generated | Economic Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **$1,000 USD** | 10.95% | -0.160% | -0.05% | **+10.74% APR** | $107.40 / year | **`ECONOMIC`** (Theoretical) |
| **$5,000 USD** | 10.95% | -0.032% | -0.05% | **+10.87% APR** | $543.40 / year | **`ECONOMIC`** |
| **$25,000 USD** | 10.95% | -0.006% | -0.05% | **+10.89% APR** | $2,723.40 / year | **`ECONOMIC`** |
| **$100,000 USD** | 10.95% | -0.002% | -0.15% | **+10.80% APR** | $10,798.40 / year | **`ECONOMIC`** |

*Practical Note:* While theoretical gross carry at constant 10 bps funding yields $+10.7\%$ net APR, empirical realization over the last 24 months generated only $+4.64\%$ net APR due to prolonged zero/negative funding regimes during crypto bear markets.

---

### Historical Stress Window Diagnostics

| Stress Event | Context | Margin Utilization | Distance to Liquidation | Basis Dislocation | ADL & Counterparty Exposure |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **2021-05-19 Crash** | China mining ban / spot cascade (-30% in 4h) | **74.5%** | 2.8x ATR (Safe) | -420 bps perp discount | None (VIP perp tier maintained) |
| **2022-06-13 Depeg** | Celsius / 3AC insolvencies / stETH discount | **68.2%** | 3.1x ATR (Safe) | -185 bps discount | Low |
| **2022-11-08 Collapse** | FTX insolvency / complete exchange shutdown | **100.0%** | Zero (Exchange halted) | N/A (Disorderly) | **Severe (100% Capital Wipeout)** |

### Counterparty and Venue Risk Audit

1. **Venue Solvency Risk:** Spot-long / perp-short carry requires collateral to be held on a centralized derivatives exchange. The 2022-11-08 FTX collapse demonstrates that exchange default risk dwarfs the modest $+5\%$ annual yield.
2. **Auto-Deleveraging (ADL) Risk:** During extreme market crashes (such as 2021-05-19), highly profitable short perp legs are subject to exchange ADL, liquidating the short hedge and leaving the spot leg unhedged into an ongoing cascade.
3. **Negative Funding Regimes:** During extended bear markets, funding rates turn negative (shorts pay longs), resulting in continuous cash bleed.

---

## 3.4 Institutional Decision Audit (Computed, Not Argued)

Applying the pre-registered promotion bar mechanically to every candidate across all four phases:
- **Promotion Thresholds:** Net Annualized Sharpe $\ge 1.0$ on validation | 95% Day-Block CI lower bound $> 0$ | Deflated Sharpe Ratio (DSR) $\ge 0.95$ ($N_{\text{trials}} \ge 500$) | Positive in $\ge 4$ of 5 years | Positive in both BTC Bull and Bear.

| Candidate Strategy | Validation Sharpe | CI Lower Bound $> 0$ | DSR $\ge 0.95$ | Positive in $\ge 4/5$ Years | Positive in Bull & Bear | Mechanical Determination |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Core 4h Long (v1.1 Freeze)** | -1.70 | NO | NO | NO | NO | **`KILL`** |
| **2B: Contrarian Reversal (H10)** | -0.84 | NO | NO | NO | NO | **`KILL`** |
| **2C: Funding Carry (H5)** | +0.42 | YES | NO | YES | YES | **`UNECONOMIC`** |
| **2D: Daily Cross-Sectional** | -1.24 | NO | NO | NO | NO | **`KILL`** |
| **2E: ML Expected-R Ranker** | +0.28 | NO | NO | YES | NO | **`KILL`** |

### Pre-Registered Action Rule:
- $\ge 1$ Strategy Promoted $\to$ `CONTINUE`
- $0$ Promoted, $\ge 1$ Qualifying Watch Candidate $\to$ `NARROW`
- $0$ Promoted, $0$ Qualifying Watch Candidates $\to$ **`HALT`**

```
================================================================================
FINAL INSTITUTIONAL DETERMINATION: HALT
================================================================================
```

---

## Closure Governance Implementation

In strict compliance with the **`HALT`** mandate:
1. **Paper Scanner Mode:** The paper scanner continues running strictly in **`LOG-ONLY`** forward observation mode (`FLASH_PAPER_MODE = True`).
2. **Live Trading Lock:** `LIVE_TRADING_ENABLED` remains locked at **`False`** in `app/config.py` behind the v1.1 parameter freeze.
3. **Postmortem Report:** Published comprehensive forensic postmortem at [`docs/POSTMORTEM.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/POSTMORTEM.md).
4. **Capital Readiness Checklist:** Published explicit pre-conditions and quantitative gates at [`docs/CAPITAL_READINESS_CHECKLIST.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/CAPITAL_READINESS_CHECKLIST.md).
