# STARKX QUANTEDGE: CONTROLLED PAPER-TRADING VALIDATION PLAN

> **Audit Phase:** Phase 9 & Phase 10  
> **Status:** PROTOCOL FROZEN & ACTIVE  
> **Target Evaluation Period:** 30–60 Days ($N \ge 100$ Resolved Trades)  
> **Strategy Candidate:** Core Crypto 4h Swing Longs (Trend & Range-Fade)  
> **Execution Mode:** Shadow Paper Trading (Zero Real Capital at Risk)

---

## 1. OBJECTIVE & MANDATE

The quantitative audit conducted across Phases 1 through 8 established that:
1. **The Core Alpha Engine is Valid:** 4h Crypto Longs produced **+$2,129.79 net P&L across 162 trades** (+94.86 R, 61.73% hit rate, 2.51 profit factor), with a wide break-even transaction cost margin of **135.5 bps**.
2. **Account Drawdowns Came From Known Sources:** Forex stops (-134.01 R), crypto shorts (-42.80 R, 4.4% hit rate), and unconstrained gross leverage (up to 16.2x) completely masked the crypto long edge.
3. **Simulation Defects Existed:** `resolver.py` previously contained a lookahead excursion fill (`mfe_early >= 0.05`), and `meta_model.py` had an overfitted in-sample PAVA calibration pegging probabilities at 98%.

The mandate of this Paper-Trading Validation Plan is to observe and evaluate the **frozen, repaired strategy** in forward-running, out-of-sample paper market conditions under rigorous institutional standards.

**Passing a historical backtest is not permission to trade real money. Live execution remains strictly FROZEN.**

---

## 2. CANDIDATE ISOLATION & SELECTION MATRIX

| Component | Audit Ruling | Forward Paper Status | Operational Parameters |
| :--- | :--- | :--- | :--- |
| **Crypto 4h Longs** | **PROVEN ALPHA** | **PRIMARY ACTIVE CANDIDATE** | 4h timeframe, ATR-based limit entries, TP at 1.5R–3.0R, partial book at 0.40R |
| **Crypto Shorts** | **DEFECTIVE / LOSING** | **GATED SHADOW MODE** | Blocked unless passing 5-point gate (Trend, Slope, Structure, HTF, Conviction $\ge 50$) |
| **Flash Bot (5m/15m)** | **UNVIABLE (0.49 PF)** | **SUSPENDED FROM CAPITAL** | Runs in isolated paper incubator only; zero allocation from main book |
| **Forex / Rates** | **NEGATIVE R EDGE** | **SUSPENDED FROM CAPITAL** | Re-evaluation deferred until volatility-adjusted stop models are built |
| **Meta-Model Gating** | **OVERFITTED PAVA** | **SHADOW EVALUATION ONLY** | `meta_gate_enabled = False`; logs `meta_p` without overriding `win_prob` in EV |
| **LLM Multi-Agent** | **ADVISORY ONLY** | **UI DECISION SUPPORT ONLY** | Decoupled from automated background scanning; cannot expand risk |

---

## 3. REALISTIC EXECUTION & TRANSACTION COST PROTOCOL

Paper trading must simulate execution frictions with high fidelity. Every fill, cancel, fee, and partial execution must follow verified rules:

### 3.1 Order Fill Protocol (`resolver.py` & `execution.py`)
1. **Resting Maker Limit Orders:**
   - Long entries sit at `price - offset_atr * ATR` below the signal close.
   - Limit order expiration window: `limit_expiry_bars = 4` (16 hours on 4h bars).
   - **No Lookahead Fills:** The order is filled **only if** subsequent bar lows actually trade through the limit price ($Low_t \le Limit$). The defective $MFE \ge 5\%$ retroactive fill logic is permanently removed.
   - If unfilled after 4 bars, the order is marked `result = 'unfilled'` and closed without P&L distortion.
2. **Partial Profit Taking:**
   - 35% of position closed at $+0.40 R$ to derisk (`partial_book_at_r = 0.40`).
   - Stop-loss trailed to breakeven (`entry`) once partial is booked.
   - Remaining 65% runs to target ($1.5 R - 3.0 R$) or trailed stop.

### 3.2 Baseline Cost Schedule
All paper trades must automatically deduct realistic transaction frictions from gross P&L:
- **Crypto Maker Fee:** $4.0\text{ bps}$ ($0.04\%$)
- **Crypto Taker Fee:** $10.0\text{ bps}$ ($0.10\%$)
- **Bid-Ask Half-Spread:** $1.0\text{ bps}$
- **Simulated Slippage:** $2.0\text{ bps}$ entry, $2.0\text{ bps}$ exit
- **Round-Trip Base Case Cost:** **$14.0\text{ bps}$** (maker limit entry + maker partial exit + taker stop exit)

---

## 4. SAMPLE-SIZE & STATISTICAL EVIDENCE POLICY

To prevent small-sample randomness from being mistaken for alpha:
- **Minimum Evaluation Sample:** $N = 100$ independent closed trades.
- **Minimum Evaluation Horizon:** 30 calendar days (60 days maximum).
- An arbitrary run of 15–20 winning trades will **not** trigger a live promotion.

### Formal Hypothesis Test:
$$H_0: \text{Net Expectancy } \mu_R \le 0.00 R \quad \text{vs.} \quad H_1: \text{Net Expectancy } \mu_R \ge +0.25 R$$

The candidate is accepted only if $H_0$ is rejected at the $\alpha = 0.01$ significance level ($t\text{-stat} \ge 2.58$).

---

## 5. QUANTITATIVE ACCEPTANCE & REJECTION CRITERIA

### 5.1 Acceptance Criteria (Must Satisfy ALL):
1. **Net Realized Expectancy:** $\ge +0.25 R$ per trade after base-case costs.
2. **Profit Factor:** $\ge 1.40$ (Gross Profits / Gross Losses).
3. **Win Rate:** $\ge 50.0\%$ (given minimum $1.5$ reward-to-risk).
4. **Maximum Portfolio Drawdown:** $\le 12.0\%$ under active capital-adaptive sizing.
5. **Realized Brier Score:** $\le 0.22$ (proving probability calibration quality).
6. **Limit Order Fill Rate:** $\ge 65.0\%$ of generated signals filled within 4 bars.
7. **Drift Stability:** Zero Page-Hinkley drift alarms during the final 40 trades.

### 5.2 Hard Rejection / Abort Criteria (ANY Triggers Immediate Suspension):
1. **Expectancy Failure:** Net expectancy drops below $0.00 R$ over any rolling 40-trade window.
2. **Catastrophic Drawdown:** Portfolio equity suffers a $\ge 18.0\%$ drawdown.
3. **Severe Circuit Breaker:** 24h circuit breaker ($-3.0 R$) trips more than twice in 14 days.
4. **Execution Discrepancy:** Limit order fill rate drops below $40\%$, indicating adverse selection.

---

## 6. SCHEDULED AUDIT CHECKPOINTS

```
[Day 0: Frozen Launch]
       |
       v
[Day 7 / Trade 20]  ---> Checkpoint 1: Ledger & Fill Verification
       |
       v
[Day 15 / Trade 45] ---> Checkpoint 2: Mid-Point Factor & Expectancy Audit
       |
       v
[Day 30 / Trade 100]---> Checkpoint 3: Comprehensive Statistical Review
       |
       +---> [PASS] ---> Eligible for Institutional Live Readiness Review
       +---> [FAIL] ---> Strategy Rejected / Quarantined to Research
```

### Checkpoint 1 (Day 7 / ~20 Trades):
- Reconcile database ledger (`signals` join `outcomes`).
- Verify no duplicate signals or phantom fills occurred.
- Check fill latency and ATR limit offset adherence.

### Checkpoint 2 (Day 15 / ~45 Trades):
- Measure realized $R$-distribution (mean, skewness, kurtosis).
- Confirm Macro ($F_7$) and Momentum ($F_2$) factor alignment.
- Verify that shadow `meta_p` probabilities match actual outcomes without in-sample overfitting.

### Checkpoint 3 (Day 30 / $\ge 100$ Trades):
- Compute complete statistical scorecard:
  - Net Expectancy ($R$) and $t$-statistic.
  - Annualized Sharpe Ratio and Sortino Ratio.
  - Maximum drawdown and recovery time.
  - Break-even cost tolerance.
- Issue formal recommendation: **REJECT**, **EXTEND**, or **ELIGIBLE FOR SEPARATE HUMAN LIVE REVIEW**.

---

## 7. GOVERNANCE & KILL SWITCH INVARIANTS

1. **Parameter Lock:** No hyperparameters (ATR multipliers, limit offsets, confluence weights, or exit rules) may be modified during the 30-day evaluation.
2. **Automated Kill Switch:** If account drawdown reaches $-18.0\%$, the global kill switch terminates all scanning and cancels pending orders.
3. **Independent Ledger Logging:** Every candidate signal, whether accepted, rejected by exposure budget, or cancelled unfilled, is permanently recorded in PostgreSQL for post-mortem analysis.
4. **No Real Capital:** Live routing remains strictly disabled (`shadow_mode = True`).
