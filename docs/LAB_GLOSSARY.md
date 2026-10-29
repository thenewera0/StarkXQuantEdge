# StarkX LAB: Terminology & Mathematical Glossary

> Comprehensive reference defining key statistical, architectural, and statutory concepts used across StarkX Lab.

---

### 1. Evidence Tiers
- **T0 (Collecting):** Initial incubation stage. Variants have `< 30` completed forward trades or `< 20` active forward days. All historical replay bars are explicitly labelled `BACKFILL` and excluded from tier advancement. T0 variants receive a fixed floor weight (2%) in the Lab Portfolio.
- **T1 (Measured):** Intermediate statistical stage. Variants have accumulated `>= 30` forward trades and `>= 20` active days. Eligible for risk allocation above the 2% floor.
- **T2 (Candidate):** Statistically significant positive edge. Requires `>= 100` forward trades, `>= 40` active days, mean net R `> 0`, lower 80% stationary day-block bootstrap bound `> 0`, and beats its paired RandomEntryControl (`ci_low_80 > 0`).
- **T3 (Paper-Proven):** Proven long-term forward performance. Requires `>= 120` active days, lower 95% day-block bound `> 0`, Deflated Sharpe Ratio (DSR) `>= 0.95` incorporating the honest research trial counter, positive mean return in `>= 2` of 3 BTC market regimes (bull, bear, range), positive return in `>= 2` of the last three 30-day blocks, and execution twin gap documented. Only T3 variants may enter manual Capital Readiness review.

---

### 2. Execution Twins (Section 4)
- **Taker Baseline:** Primary conservative baseline. Simulates immediate entry on the next bar open with realistic market-impact slippage (3, 6, or 10 bps based on 30-day USD volume rank) and 5 bps taker fee plus 18% GST.
- **Maker Twin:** Limit-order alternative model. Places limit orders inside the spread (or at close $- 0.15$ ATR for flush strategies) with a strict "through-by-1-tick" fill rule and a 50% queue haircut at 2 bps maker fee plus 18% GST.
- **Twin Invariant:** Both P&L series are recorded in parallel so maker execution benefits are never assumed without empirical verification.

---

### 3. Execution & Risk Rules
- **Stop-First Collision:** Rule 0.4 invariant. If a 1-minute candle's high touches the target price and its low touches the stop price in the exact same minute, the engine strictly resolves the trade as a **stop loss** at `current_stop`.
- **Immutable Initial Stop:** Rule 0.4 invariant. The original stop loss established at entry cannot be modified or widened. All dynamic trailing logic operates strictly on `trailing_stop`.
- **Cost Gate:** Rule 1 invariant. Any strategy or timeframe whose median transaction cost (fees + 18% GST + slippage + funding) exceeds $0.25\text{ R}$ is automatically disabled.

---

### 4. Allocation & Statistical Algorithms
- **Hedge Algorithm:** Multiplicative weights update algorithm for virtual risk share allocation:
  $$w_i \propto \exp\left(\eta \cdot \hat{R}_i\right)$$
  with learning rate $\eta = 0.10$, subject to a minimum floor of 2% ($0.02$) and a maximum cap of 30% ($0.30$), normalized such that $\sum w_i = 1.0$.
- **James-Stein Shrinkage:** Shrinkage estimator applied to mean returns when trade sample size $n < 100$:
  $$\hat{R}_{\text{shrunk}} = \hat{R} \cdot \max\left(0, 1 - \frac{10}{n}\right)$$
  Prevents over-allocating to noisy short-term streaks.
- **Deflated Sharpe Ratio (DSR):** Multiple-testing adjustment (Bailey & López de Prado, 2014) evaluating whether an observed Sharpe ratio is statistically distinct from zero given $N$ total research trials:
  $$DSR = \Phi\left(\frac{SR - E[\max_N SR]}{\sigma_{SR}}\right)$$
- **Expected False Positives:** Calculated conservatively as:
  $$E[FP] = 0.05 \times N_{T2/T3}$$
  displayed directly in the Lab Health Strip to guard against selection bias.

---

### 5. Statutory Tax Regimes (India)
- **Scenario A (VDA Section 115BBH):** Flat 30% tax on every profitable trade + 4% Health & Education Cess ($31.2\%$ total tax liability) with strictly zero loss offset across trades and zero deduction for expenses or platform fees. 1% TDS withheld on gross turnover.
- **Scenario B (Ordinary Business Income):** Corporate/LLP trading business model taxing net gains at 20% (plus cess) with full deduction of trading losses, depreciation, server infrastructure, and exchange fees.
- **Mandatory Notice:** *Not tax advice; consult a qualified Chartered Accountant.*
