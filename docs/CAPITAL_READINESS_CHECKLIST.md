# Capital Readiness Checklist: Mandatory Conditions for Live Deployment

**System:** StarkX QuantEdge  
**Document Status:** Institutional Quality Assurance Gate  
**Current Enforcement:** `LIVE_TRADING_ENABLED = False` (Permanently Locked)  
**Governance Authority:** Quantitative Risk & Edge Rehabilitation Board  

---

## Purpose & Operating Policy

Under no circumstances may the feature flag `LIVE_TRADING_ENABLED` in `backend/app/config.py` be set to `True` until **EVERY SINGLE CONDITION** in this checklist has been mathematically verified, logged with raw empirical numbers, and signed off in CI.

This checklist is designed to prevent premature capital allocation to under-validated, overfitted, or fee-negative trading architectures.

---

## 1. Out-of-Sample Forward Paper Track Record Gate

Before live capital may be committed, the strategy must generate a verifiable, continuous forward paper trading track record executing in real-time under live order-book conditions:

- [ ] **Condition 1.1: Minimum Forward Sample Size ($N \ge 100$)**  
  The strategy must execute at least $100$ independent forward paper signals after the freeze timestamp (`2026-10-26T16:00:00Z`).
- [ ] **Condition 1.2: Minimum Effective Sample Size ($N_{\text{eff}} \ge 85$)**  
  Accounting for day-clustering and intra-cluster correlation ($\rho_{\text{ICC}}$), the effective number of independent trading days must satisfy $N_{\text{eff}} \ge 85$.
- [ ] **Condition 1.3: Positive Realized Net Mean ($R_{\text{net}} > 0$)**  
  The realized sample mean across all post-freeze paper trades must be strictly positive: $\bar{R}_{\text{net}} \ge +0.15$ R after full deduction of exchange fees (maker 2 bps, taker 5 bps, 3 bps slippage).
- [ ] **Condition 1.4: Statistically Significant Day-Block CI ($CI_{\text{low}} > 0$)**  
  A $10,000$-resample day-block bootstrap of the post-freeze paper trade series must yield a 2.5th percentile lower bound strictly greater than zero ($CI_{\text{low}} > +0.02$ R).

---

## 2. Statistical Edge & Multiple Testing Correction Gate

Any candidate strategy proposed for live promotion must demonstrate genuine predictive alpha surviving rigorous multiple-testing deflation:

- [ ] **Condition 2.1: Deflated Sharpe Ratio Hurdle ($\text{DSR} \ge 0.95$)**  
  The strategy must achieve an annualized Net Sharpe ratio $\ge 1.0$ that survives the Bailey & López de Prado Deflated Sharpe Ratio test ($\text{DSR} \ge 0.95$) computed against the honest trial registry count ($N_{\text{trials}} \ge 500$).
- [ ] **Condition 2.2: Out-of-Sample Placebo Significance ($p < 0.01$)**  
  In a $1,000$-iteration cross-sectional score shuffle placebo test, the strategy's empirical Sharpe ratio must rank in the 99th percentile ($p < 0.01$).
- [ ] **Condition 2.3: Zero Gross-R Feature Contamination**  
  If the strategy uses machine learning or statistical scoring, the out-of-sample rank IC on gross R must remain statistically significant ($p < 0.05$) when all cost, stop-distance, and volatility features are completely removed.
- [ ] **Condition 2.4: Outperformance vs. Always-Long in Both Regimes**  
  The strategy must demonstrate positive paired excess return over unmanaged Always-Long holding in BOTH Bitcoin Bull regimes ($CI_{\text{low}} > 0$) and Bitcoin Bear regimes ($CI_{\text{low}} > 0$).

---

## 3. Realized Broker Execution & Slippage Parity Gate

Paper-traded simulations often assume optimistic fills. Realized broker execution must match modeled assumptions:

- [ ] **Condition 3.1: Realized Limit Fill Rate ($\ge 70\%$)**  
  For limit orders placed at or inside the spread, the realized fill rate prior to the 2-bar timeout must equal or exceed $70.0\%$.
- [ ] **Condition 3.2: Adverse Selection Gap ($< 1.5$ bps)**  
  The average price movement 1 bar after limit order execution must demonstrate no more than $1.5$ bps of immediate adverse selection.
- [ ] **Condition 3.3: Stop-Loss Slippage Cap ($\le 3.0$ bps)**  
  Realized slippage on market stop-loss triggers across liquid perps must not exceed $3.0$ bps under normal market volatility.

---

## 4. Capital Efficiency & Account Scale Gate

- [ ] **Condition 4.1: Minimum Capital Sizing Feasibility**  
  Account equity must be sufficient such that fixed exchange minimum order sizes (e.g. $\$5.00$ to $\$10.00$ per contract) represent no more than $20\%$ of the target risk budget per trade.
- [ ] **Condition 4.2: Maximum Portfolio Value-at-Risk ($\text{VaR}_{99} \le 5\%$)**  
  Combined portfolio leverage across all open concurrent positions must not exceed $2.5\times$ net equity, ensuring zero liquidation risk during historical stress drawdowns (such as 2021-05-19).
- [ ] **Condition 4.3: Economic Return Exceeding Risk-Free Benchmark**  
  Net projected dollar return after all exchange commissions, borrowing/funding costs, and server infrastructure expenses must exceed the risk-free rate plus $2.0\%$ APR on the allocated capital base.

---

## 5. Architectural & Governance Safety Locks

- [ ] **Condition 5.1: Database-to-Ledger Reconciliation Delta $\equiv \$0.00$**  
  [`backend/scripts/test_performance_reconciliation.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_performance_reconciliation.py) must pass with zero cents delta between ground truth outcomes and the `/performance` endpoint.
- [ ] **Condition 5.2: Lookahead Invariance Check Clean**  
  [`backend/scripts/test_lookahead.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lookahead.py) must verify exact bitwise truncation invariance across all active indicator and scoring functions.
- [ ] **Condition 5.3: Parameter Checksum Verified**  
  [`backend/scripts/test_freeze_hash.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_freeze_hash.py) must verify that live scanner parameters match the frozen parameter set with SHA-256 checksum `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`.
- [ ] **Condition 5.4: Formal Board Sign-Off**  
  Written sign-off from both the Quantitative Engineering Lead and the Risk Manager must be recorded in `docs/CHANGELOG.md`.

---

## Current Operational State

```
[X] 1. Out-of-Sample Paper Track Record: INCOMPLETE (Awaiting N >= 100 paper trades)
[X] 2. Statistical Edge Deflation:       FAILED (Net Sharpe < 1.0; DSR < 0.95 across candidates)
[X] 3. Realized Execution Parity:        PENDING (Awaiting forward paper fill analytics)
[X] 4. Capital Scale Hurdle:             UNECONOMIC at $1,000 equity
[✓] 5. Architectural Safety Checks:      PASSED (Tests green; Hash locked; Reconciled)

CURRENT MANDATORY STATUS: LIVE_TRADING_ENABLED MUST REMAIN FALSE.
```
