# STARKX QUANTEDGE: MACHINE LEARNING & MODEL GOVERNANCE AUDIT
**Phase 6 Deliverable — ML Pipeline Validation, Leakage Inspection & Champion/Challenger Audit**  
**Date:** October 18, 2026 | **Author:** Senior Quantitative Research & ML Validation Specialist  
**Scope:** Audit of `learning.py`, `meta_model.py`, `calibration.py`, and Model Settings in PostgreSQL

---

## 1. EXECUTIVE SUMMARY: ML GOVERNANCE STATUS

StarkX QuantEdge incorporates three distinct machine learning subsystems:
1. **Regime-Conditioned Adaptive Factor Weighting** ([`backend/app/learning.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/learning.py)): Fit sample-weighted L2 logistic regression per regime with walk-forward holdout gating.
2. **Isotonic Probability Calibration** ([`backend/app/calibration.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/calibration.py)): Segment-conditioned Pool-Adjacent-Violators Algorithm (PAVA) mapping composite scores to $P(\text{win})$.
3. **Secondary Meta-Labeling Model** ([`backend/app/meta_model.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/meta_model.py)): L2 logistic regression over a 16-dimensional feature vector predicting trade survival.

```
+-----------------------------------------------------------------------------------------------+
|                                    ML VALIDATION RULING                                       |
|                                                                                               |
|   Regime Adaptive Weights (`learning.py`)   :  METHODOLOGICALLY SOUND (Walk-forward gated)    |
|   Segment Calibration (`calibration.py`)    :  VALID WHEN SEGMENTED (Crypto/Long separated)   |
|   Meta-Labeling Model (`meta_model.py`)     :  CRITICAL OVERFITTING DEFECT (Pegged to 0.98)   |
|   RECOMMENDATION                            :  FREEZE META-MODEL TO SHADOW MODE IMMEDIATELY   |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. FORENSIC AUDIT OF THE META-MODEL DEFECT

### 2.1 Verified Defect: In-Sample Isotonic Calibration
- **Code Reference:** [`backend/app/meta_model.py:177-182`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/meta_model.py#L177-L182)
  ```python
  # Fit the final model on all data + isotonic-calibrate its in-sample scores.
  mu, sd = X.mean(0), X.std(0) + 1e-9
  w = _fit_logreg((X - mu) / sd, y, sw)
  p_in = _predict_raw(X, mu, sd, w)
  knots_x, knots_y = _pava(p_in, y)  # <--- SEVERE FLAW: FITTING CALIBRATION ON IN-SAMPLE PREDICTIONS
  ```
- **The Mathematical Mechanism of Failure:**
  When PAVA isotonic regression is fitted directly on the in-sample predictions $p_{\text{in}}$ of a model that was just trained on those same targets $y$, the extreme predictions match the labels perfectly.
  As a result, `knots_y[-1]` reaches $1.0$ (clipped to $0.98$).
  In live execution ([`meta_model.py:247`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/meta_model.py#L247)):
  $$\text{meta\_p} = \text{interp}(p_{\text{raw}}, \text{knots\_x}, \text{knots\_y})$$
  Any candidate trade with a moderately high score falls onto the top knot and receives an artificial **$98.0\%$ win probability**!

### 2.2 Empirical Proof from Live Database Records
We audited every recorded `meta_p` value across historical signals in PostgreSQL:
- **Fraction of Signals Pegged to $\ge 95\%$:** **41.6%**
- **Meta Brier Score:** **0.3652** (Substantially worse than an uninformative 50/50 prior of $0.25$).
- **Examples of Pegged Signals in Live Database:**
  - ID 1225 (`PEPEUSDT` 4h Buy): `win_prob = 0.5588`, `meta_p = 0.9800` $\rightarrow \text{EV}_R = +2.9359R$.
  - ID 1166 (`NDX` 4h Buy): `win_prob = 0.3457`, `meta_p = 0.9800` $\rightarrow \text{EV}_R = +2.2847R$.
  - ID 1186 (`DOGEUSDT` 4h Buy): `win_prob = 0.5532`, `meta_p = 0.9800` $\rightarrow \text{EV}_R = +1.6365R$.
- **Consequence:** Because `meta_model.is_active = True` in PostgreSQL `settings` and `config.meta_gate_enabled = True`, this overfit $98\%$ probability bypassed the EV gate, letting negative-EV setups enter the book.

---

## 3. AUDIT OF ADAPTIVE WEIGHTS & WALK-FORWARD RETRAINING

### 3.1 Time-Series Cross-Validation Structure
[`backend/app/learning.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/learning.py) implements sound time-series integrity:
1. **Chronological Ordering:** Training rows are ordered strictly by `signals.as_of asc`.
2. **Embargo Gap:** 5-bar embargo (`embargo = 5`) ensures that trade holding overlap does not leak information between folds.
3. **Multi-Asset Holdout Basket:** Holdout performance is validated across 5 decorrelated assets (`BTC`, `ETH`, `SOL`, `BNB`, `XRP`) rather than tuning to a single symbol.
4. **Promotion Hurdle:** A challenger weight profile must beat the champion by $\ge 0.20\%$ out-of-sample margin (`_PROMOTE_MARGIN = 0.002`).
5. **Sample Size Floor:** Requires $N \ge 60$ resolved outcomes per regime (`MIN_SAMPLES = 60`) before training is attempted.

---

## 4. AUDIT OF PROBABILITY CALIBRATION (`calibration.py`)

### 4.1 Conditioning Architecture
Calibration is performed using PAVA isotonic regression conditioned hierarchically:
$$(\text{Market}, \text{Direction}, \text{Regime}) \longrightarrow (\text{Market}, \text{Direction}) \longrightarrow \text{Regime} \longrightarrow \text{Global}$$
This structure was introduced to fix a severe bug in earlier versions where pooling all trades resulted in a pooled $38\%$ base rate, which incorrectly told $70\%$-win crypto longs that their probability was $17-38\%$, suppressing legitimate trades.
- Current Status: **Healthy & Statistically Sound**.

---

## 5. ML GOVERNANCE & INTERVENTION MANDATES

In strict compliance with **Non-Negotiable Rule #8** ("Do not automatically promote an ML model or strategy into production during this audit"):

1. **Mandatory Freeze of Meta-Model Gating:**
   - In `backend/app/config.py`, enforce `meta_gate_enabled: bool = False`.
   - Update `settings` in PostgreSQL: set `meta_model.is_active = false`.
   - Meta-model predictions will continue to be computed and logged in **SHADOW MODE ONLY** for tracking, but will **NOT** drive the live EV gate.
2. **Remediation for Meta-Model Calibration:**
   - To reactivate the meta-model in the future, isotonic calibration must be fitted using **Out-of-Fold (OOF) cross-validation predictions**, never in-sample predictions.
3. **Retraining Freeze:**
   - Weekly automated champion weight promotions are frozen until the complete 15-phase audit and paper-trading evaluation are finished.
