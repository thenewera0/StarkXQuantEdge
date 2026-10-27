# STARKX QUANTEDGE: PRE-REGISTRATION AMENDMENT 1
**Document Type:** Formal Research Pre-Registration Amendment  
**Effective Timestamp (UTC):** 2026-10-27T10:00:00Z  
**Frozen Signal Specification SHA-256:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`  
**Amendment Canonical Body SHA-256:** `c5c6a816e74306724b820a41277a8ab1f81b1c68a799f235b0ade52449ab2dfd`  

---

## 1. Executive Summary & Purpose
This document formally records **Pre-Registration Amendment 1** to the StarkX QuantEdge forward research evaluation protocol established in Phase 0.5–Phase 8. This amendment is registered **strictly prior to the evaluation of any forward out-of-sample data**.

**Core Invariants Retained:**
- **Zero Signal Parameter Changes:** The frozen parameter configuration remains bit-for-bit identical to cryptographic hash `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` (`config/frozen_core_long_v1_1.json`).
- **Live Trading Kill-Switch:** `live_trading_enabled = False` remains permanently in force (Rule R4).
- **PASS Rule Unchanged:** The candidate strategy passes if and only if:
  1. $\text{Mean Net } R \ge +0.1500$ R.
  2. $95\%$ Stationary Day-Block Bootstrap CI Lower Bound $> 0.0000$ R ($B = 10,000$ resamples).
  3. Top-5 positive R trades contribute $\le 20.0\%$ of cumulative positive R.
- **Interim Decision Prohibition:** Strictly **NO** interim decisions are permitted. The operational status remains exclusively `INCONCLUSIVE` before the evaluation trigger fires.
- **Timing & Horizon Only:** This amendment changes **timing and sample size definition only**.

---

## 2. Rationale for Metric Clarification (active_days vs N_eff)
Forensic audit across Phases 6, 7, and 8 revealed critical mathematical divergence across competing estimators of "effective sample size" ($N_{\text{eff}}$):
1. **Trade-Level Autocorrelation ($N_{\text{eff}} = 111.7$):** Adjusted for intra-day return correlation $\rho = 0.1655$, but obscured non-independent calendar clustering.
2. **Calendar Days ($N_{\text{eff}} = 48$ vs True 26):** A historical transcription error mistook maximum trade duration `TIMEOUT_BARS = 48` for active calendar days, whereas the database ledger contained exactly 26 distinct trading dates.
3. **Cluster Herfindahl ($N_{\text{eff}} = 9$):** Normalized cluster variance degrees of freedom, which excessively penalized high-activity burst days.

Because $N_{\text{eff}}$ introduces discretionary estimator choice and ambiguity into pre-registered governance, **$N_{\text{eff}}$ is permanently retired from forward decision rules and forward reports**. 

Moving forward, sample size is defined exclusively by two verifiable, deterministic integers:
- **`active_days`**: Distinct UTC calendar dates ($YYYY-MM-DD$) containing $\ge 1$ unique forward trade.
- **`n_trades`**: Total count of unique, sized trades executed.

---

## 3. Amended Evaluation Trigger
The forward evaluation trigger is formally amended to the **earliest of**:
1. **`active_days >= 60`** distinct UTC calendar dates with $\ge 1$ unique crypto `core_4h_long` trade; OR
2. **`2027-10-26`** (exactly 12 calendar months from the post-freeze lock timestamp `2026-10-26T12:45:00Z`).

### Statistical Power Justification (Phase 9.2 Power Table)
At $K = 60$ active days (averaging $\approx 360$ trades at $6.0$ trades/day):
- Standard Error of the Mean: $\text{SE}(60) = \frac{\sigma_{\text{day}}}{\sqrt{60}} = 0.2154$ R.
- Minimum Sample Mean required to clear the 95% CI lower bound ($1.96 \times \text{SE}$): $+0.4221$ R.
- Statistical Power $P(\text{PASS})$:
  - If true mean $\mu = 0.0$ R: $1.28\%$ (Type I error rate strictly bounded).
  - If true mean $\mu = +0.10$ R: $5.12\%$.
  - If true mean $\mu = +0.20$ R: $12.88\%$.
  - If true mean $\mu = +0.40$ R (observed corrected ledger $+0.4076$ R): $45.26\%$ (rising to $68.60\%$ at 90 days).

---

## 4. Status Protocol
Prior to the moment the evaluation trigger fires (`active_days >= 60` or `date >= 2027-10-26`), the automated evaluation pipeline (`scripts/evaluate_forward.py`) must output **ONLY**:
$$\mathbf{STATUS: INCONCLUSIVE}$$

No capital allocation, discretionary overrides, live deployment, or interim performance-based stopping is permitted.
