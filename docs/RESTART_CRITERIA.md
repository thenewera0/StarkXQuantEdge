# StarkX QuantEdge: Research Restart Criteria & Pre-Registration Protocol

**Status:** PROGRAM HALTED  
**Effective Date:** 2026-10-27  
**Governance Authority:** Institutional Risk & Quantitative Review Committee  
**Operating Rules:** Permanent Enactment of Rules R1–R7  

---

## 1. Executive Mandate
Following five comprehensive audit phases (Phase 0 through Phase 4), zero quantitative alpha candidates achieved the pre-registered promotion bar. The research program is officially **HALTED**, all live order routing is disabled (`live_trading_enabled = False`), and the production engine operates solely as a log-only shadow forward-paper scanner.

No further hypothesis testing, parameter tweaking, indicator recombination, or live trading activation may take place unless a proposed strategy sleeve strictly fulfills all six mandatory restart criteria set forth below. Any pull request or commit violating these standards must fail CI immediately.

---

## 2. The Six Mandatory Restart Criteria

### Criterion 1: Pre-Registered Hypothesis & Cryptographic Specification Lock
- **Requirement:** Before accessing any historical or forward validation data, the candidate strategy's complete mathematical and execution specification must be serialized into a version-controlled configuration file (e.g. `config/<strategy>_spec.json`) and cryptographically hash-locked with SHA-256.
- **Specification Invariants:**
  - Exact signal score definitions, formulas, and lookback windows.
  - Rebalance horizons $H$, portfolio allocation rules, and weighting schemes (e.g. inverse realized volatility risk parity).
  - Explicit execution timing: strictly next-bar open ($t \to t+1$ open), with zero same-bar fill assumptions.
  - Explicit hedging rules (e.g. rolling beta hedge to BTC).
- **Prohibition:** Zero parameter optimization, grid search, or post-hoc threshold adjustment is permitted after the hash is registered.

### Criterion 2: Strictly Untouched Forward Hold-Out Data
- **Requirement:** Historical backtests alone can never justify program resumption. Any candidate strategy must be tested exclusively on data that printed **strictly after 2026-10-27T00:00:00Z**.
- **Minimum Evaluation Sample:**
  - Minimum elapsed calendar time: $\ge 180$ calendar days.
  - Minimum independent rebalance events: $N_{\text{eff}} \ge 120$ independent non-overlapping holding periods.
  - Pre-registered forward evaluation target date must be documented in [`docs/FORWARD_LOG.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/FORWARD_LOG.md) prior to observation.

### Criterion 3: Point-in-Time Universe Construction
- **Requirement:** Cross-sectional universes must be constructed dynamically at each historical and forward rebalance bar using strictly point-in-time information available at that bar:
  - Trailing 30-day USD volume ranking based only on closed bars up to bar $t$.
  - Minimum history filter: $\ge 90$ continuous days of trading history on the exchange.
  - Strict cohort separation: Discovery universe (ranks 1–50) vs Validation universe (ranks 51–100). Promotion evaluation is conducted **strictly on ranks 51–100**.
  - Delisted and late-rising token accounting: Tokens that subsequently rose into the top tier must be excluded from historical discovery, or survivorship drag must be explicitly accounted for.

### Criterion 4: Honest Multiple-Testing Penalization (Trial Count Tracking)
- **Requirement:** All statistical evaluation must account for the cumulative history of all trials conducted across the entire StarkX QuantEdge engagement:
  - Cumulative Engagement Trial Count: $N_{\text{trials}} \ge 512 + N_{\text{new\_trials}}$.
  - Deflated Sharpe Ratio (DSR): The strategy must achieve an annualized **$\text{DSR} \ge 0.95$** under Bailey-López de Prado deflated Sharpe methodology, taking into account sample length, return skewness, and return kurtosis.

### Criterion 5: Institutional Promotion Bar & Statistical Controls
On the out-of-sample validation universe (ranks 51–100), the strategy must satisfy all nine quantitative gates simultaneously:
1. **Taker-Only Net Sharpe $\ge 0.50$:** Must achieve positive economic return under full taker friction (5 bps fee + 10 bps adverse selection slippage per side).
2. **Maker-Model Net Sharpe $\ge 1.20$:** Under passive limit execution with through-by-1-tick fill rule (`execution.py`) and 2-bar timeout sweep.
3. **95% Day-Block Bootstrap CI Lower Bound $> 0$:** The lower bound of the stationary block bootstrap ($B = 10,000$ resamples) must be strictly positive.
4. **Consistency Across Regimes:** Net returns must be positive in $\ge 4$ of the last 5 calendar years, and positive in both BTC bull ($P > \text{SMA}_{200}$) and bear ($P \le \text{SMA}_{200}$) regimes.
5. **No Tail Concentration:** The top 5% highest returning days must account for $\le 25\%$ of total cumulative P&L.
6. **Placebo Test Significance ($p < 0.01$):** Score randomization test (1,000 within-timestamp score shuffles) must show the true strategy outperforms $\ge 99.0\%$ of placebo runs.
7. **Statistically Significant Incremental Alpha ($t \ge 2.0$):** In an OLS regression of strategy returns on BTC returns and the 30-day cross-sectional momentum factor, the intercept (alpha) $t$-statistic must satisfy $t \ge 2.00$.

### Criterion 6: Institutional Capacity & Execution Friction Sanity
- **Account Equity Capacity:** Validated at $\$1,000$, $\$25,000$, and $\$100,000$ USD account equity bases.
- **Participation Gate:** Average order size must satisfy both:
  - Exceed exchange minimum notional size ($\ge \$10.00$ per leg).
  - Consume $\le 1.0\%$ of trailing 30-day average 4h volume for every constituent instrument.
- **Carry Hurdle Gate (If Applicable):** For cash-management or funding-carry sleeves, net yield must exceed the risk-free rate by $\ge 2.0\%$ APR (minimum $+8.50\%$ net APR after all switching churn and negative funding bleed).

---

## 3. Review & Authorization Protocol
Even if all six quantitative criteria are empirically satisfied, program reactivation requires formal, written sign-off across four independent roles as codified in [`docs/HANDOVER.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/HANDOVER.md):

| Role | Sign-Off Responsibility | Verification Artifact |
| :--- | :--- | :--- |
| **Quantitative Lead** | Mathematical correctness, DSR $\ge 0.95$, incremental alpha $t \ge 2.0$ | Automated report matching `scripts/generate_report.py` |
| **Risk Lead** | Drawdown controls, margin buffer $\ge 3\times$ ATR, liquidation distance | Stress simulation audit report |
| **Engineering Lead** | Fill model verification, execution latencies, exchange rate limits | Production dry-run integration test |
| **Principal / PM** | Strategic alignment, capital allocation approval | Formal authorization memo |

Under no circumstances may live trading be enabled without this four-way cryptographic and administrative sign-off.
