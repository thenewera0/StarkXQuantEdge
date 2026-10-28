# StarkX QuantEdge v2: Gate Amendment Specification (V2-AMEND-01)

**Amendment Status:** FORMAL POST-HOC GOVERNANCE AMENDMENT  
**Timestamp:** `2026-10-28T13:45:00Z`  
**Governing Branch:** `feature/v2-portfolio`  
**Pre-Registration Baseline Spec Hash:** `3704e9e742e5ee9bcaa491df0c919fba0af23e65417ce106369e09a3803f6497`  
**Baseline Code Freeze Hash:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`  
**Amendment SHA-256:** `34b628ab0111359bf8cb421f1494fe67eecd866b7f6d443444aa1b1c06c9bb02`  
**Mandatory Tax Disclaimer:** *Not tax advice; consult a CA. All tax scenarios modelled under Section 115BBH & 194S.*

---

## 1. Context & Original Pre-Registered Idle Cash Treatment

In the pre-registered V2 specification (`config/v2_spec.json`, SHA-256 `3704e9e7...`), Promotion Evidence Gate 5 mandated:
> *"After-tax terminal wealth beats cash in >= 70% of 36 monthly start dates (2021-01-01 to 2023-12-01) forward to end of history."*

In that initial implementation (`evaluate_sleeve_trend` in `backend/app/v2/sleeve_trend.py`), idle margin $(1 - w_t)$ was assigned a return of **0.0% APR** (uncredited cash drag). 

Because Sleeve T targets 15% annualized portfolio volatility with an EWMA vol floor of 20% and a 25% single-asset cap, mean gross exposure across daily bars is only **~9.3%**, with **~44% of days fully flat**. Consequently, over 90% of portfolio equity sat in zero-yield uncredited cash, competing against a cash benchmark yielding 6.5% APR (4.47% net after 31.2% statutory tax).

Under this uncredited treatment, Sleeve T beaten cash in only:
- **BTC:** 6 / 36 start dates (**16.7%** -> **`FAIL`** vs 70.0% hurdle)
- **ETH:** 0 / 36 start dates (**0.0%** -> **`FAIL`** vs 70.0% hurdle)
- **Basket:** 0 / 36 start dates (**0.0%** -> **`FAIL`** vs 70.0% hurdle)

---

## 2. Explicit Post-Hoc Disclosure (Results Seen)

> [!WARNING]
> **POST-HOC DISCLOSURE:** This amendment is formulated **POST-HOC** after observing empirical backtest results and diagnosing the mathematical root cause of the 16.7% failure. Under strict scientific methodology, post-hoc amendments cannot overturn pre-registered failure verdicts for promotion purposes. The official pre-registered verdict remains **`FAIL`**.

The observed failure was not an absence of trend signal alpha, but a structural accounting distortion: evaluating a trend overlay without recognizing that unencumbered cash in an institutional multi-sleeve architecture is swept daily into sovereign risk-free yield (Treasury Bills / RBI Reverse Repo / SOFR cash deposits).

---

## 3. Amended Overlay-Value Metric Specification

For all post-hoc and forward shadow accounting, the sleeve evaluation metric is amended from absolute uncredited terminal wealth to **Overlay Value**:

$$\text{Overlay Value}_t = \text{Sleeve After-Tax Terminal Wealth}_t - \text{Credited Cash Terminal Wealth}_t$$

Where:
- $\text{Sleeve After-Tax Terminal Wealth}_t$ represents the terminal wealth of an actively managed sleeve where unallocated margin $(1 - w_t)$ is continuously swept into risk-free cash earning $\text{RISK\_FREE\_APR} = 6.50\%$ APR, taxed at $31.2\%$ ($4.472\%$ net CAGR).
- $\text{Credited Cash Terminal Wealth}_t$ represents 100% of the identical starting capital deposited in the risk-free cash benchmark over the same horizon $h_t$ days:
  $$\text{Cash TW}_t = (1 + 0.04472)^{h_t / 365.25}$$
- $\text{Overlay Value}_t > 0$ demonstrates positive economic value-add above the interest-bearing cash benchmark.

---

## 4. Reconciled 36-Start-Date Results Under Both Treatments

The 36 monthly start dates from **2021-01-01 to 2023-12-01** evaluated to **2026-10-26** (horizons of 1,060 to 2,125 days) produce the following comparative empirical performance:

| Treatment Specification | Evaluation Logic | BTC Win Rate | ETH Win Rate | Basket Win Rate | Gate Hurdle | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Original Pre-Registered** | Idle Cash @ 0.0% APR (Pure Drag) | 6 / 36 (16.7%) | 0 / 36 (0.0%) | 0 / 36 (0.0%) | $\ge 70.0\%$ | **FAIL** |
| **Amended Post-Hoc Overlay** | Idle Cash @ 6.5% APR (4.47% Net) | 36 / 36 (100.0%) | 36 / 36 (100.0%) | 36 / 36 (100.0%) | $\ge 70.0\%$ | **PASS (Informational)** |

---

## 5. Governance Decision: Neither Sleeve Promotes

In strict compliance with Operating Rules R1, R4, and 0.2:
1. **Zero Promotion Conceded:** Because this correction was identified after viewing the data, the amended 100% pass rate is classified as **SECONDARY AND INFORMATIONAL ONLY**.
2. **Stage A Retention Enforced:** Sleeve T (Diversified Trend) and Sleeve C (Carry Arbitrage) remain strictly **HELD IN STAGE A (RESEARCH)**.
3. **Stage C Prerequisite Invariant:** Progression to Stage B (Shadow) and subsequently Stage C (Paper-Executed) requires a minimum of **60 continuous calendar days of forward shadow trading** with realized tracking error $\le 1.5\%$ against backtest expectations and exactly zero reconciliation breaks.
4. **Live Trading Invariant:** `LIVE_TRADING_ENABLED=false` and `V2_LIVE_ENABLED=false` remain bitwise-locked in code and configuration. Zero capital is deployed.

---
**Ratified by StarkX Quantitative Governance Board. Not tax advice.**
