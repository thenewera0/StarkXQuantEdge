# StarkX QuantEdge: Forensic Institutional Postmortem

**Date:** 2026-10-27  
**Program Status:** **`HALT`** (Research Closed, Live Trading Permanently Disabled)  
**Frozen Baseline Checksum:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`  
**Direction A Checksum:** `119d7245491f5df601d0159310e775a0e76a21514a643b183372660ab4977664`  
**Execution Config:** Instrument: USDT Perpetuals | Maker: 2.0 bps | Taker: 5.0 bps | Stop Slippage: 3.0 bps  

---

## Executive Summary

Across five consecutive quantitative audit phases (Phases 0.5, 0.6, 1.1, 2, 3, and 4), StarkX QuantEdge underwent exhaustive forensic deconstruction. The trading pipeline was evaluated for lookahead contamination, ledger-to-equity reconciliation discrepancies, clustering autocorrelation, execution friction, and out-of-sample statistical significance.

The empirical finding across all candidate strategies is unequivocal:
**The system possessed zero genuine directional alpha.** Apparent historical profits were artifacts of market beta drift, underestimated stop-loss friction, contemporaneous return alignment errors, and model feature leakage. In accordance with pre-registered institutional governance, live order execution is permanently locked, and the research program is closed.

---

## The Seven Process Errors Found in Phases 3–4 & Their Automated Tests

During Phases 3 and 4, forensic audits identified seven distinct methodological and process errors. Each error has been diagnosed, documented, and paired with an automated test designed to prevent recurrence.

### Error 1: Contemporaneous Return Alignment Bug (Candidate 2B/2D)
- **What Was Wrong:** In Phase 2, cross-sectional daily strategies evaluated signals against the contemporaneous return of the signal bar (`ret_1d.loc[dt]`) rather than strictly forward out-of-sample returns (`fwd_ret.loc[dt+1]`).
- **Empirical Impact:** Artificially generated an impossible reversal metric of $-708.8$ bps/day and an annualized Sharpe of $-37.9$.
- **Automated Detection Test:** [`test_ls_sanity.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_ls_sanity.py). Asserts mathematical Sharpe identity within $0.01\%$, verifies contemporaneous correlation $\text{corr}(\text{signal}_t, \text{ret}_t) = 0$ on shifted series, and validates forward alignment on synthetic AR(1) processes.

### Error 2: Double-Deduction of Transaction Costs (Phase 0.6 / 1.1 Core Long)
- **What Was Wrong:** The database outcome field `outcomes.r_net` was already net of stored transaction costs (`r_net = gross_r - cost_r`). In Phase 0.6 and Phase 1.1, the author re-subtracted confirmed cost fractions from `r_net`, deducting transaction costs twice.
- **Empirical Impact:** Artificially depressed Core 4h Long expectancy from $+0.2627$ R (and ledger $+0.3118$ R) down to $+0.1702$ R in `config/cohorts.json` (a delta of $-0.1416$ R).
- **Automated Detection Test:** `test_cost_accounting_identity.py`. Asserts that for 100% of database records, $\text{gross\_r} - \text{cost\_r} \equiv \text{r\_net}$ within $10^{-6}$ and forbids secondary deductions on net fields.

### Error 3: Cohort Transposition in Configuration Files (Phase 1.1 `cohorts.json`)
- **What Was Wrong:** During the authoring of `config/cohorts.json` in Phase 1.1, $16.60$ R was manually transposed from Choppy to Trending regimes ($42.13$ R Trending / $-10.24$ R Choppy vs true database ground truth $+25.53$ R Trending / $+6.36$ R Choppy).
- **Empirical Impact:** Created the illusion of severe regime cohort drift despite $100\%$ trade ID agreement and a null symmetric difference ($\emptyset$).
- **Automated Detection Test:** `test_cohort_db_parity.py`. Directly queries PostgreSQL for every cohort definition and asserts bitwise equality against `config/cohorts.json` before any commit is accepted.

### Error 4: Benchmark Parameter Coupling in Always-Long Simulation
- **What Was Wrong:** In Phase 1.5, the Always-Long baseline simulator shared execution settings with the active trading rule, passing `partial_book_r=0.20, partial_book_frac=0.50` into what was intended to be an unmanaged buy-and-hold benchmark.
- **Empirical Impact:** Always-Long executed partial profit-taking on the rule's active bars, printing a paired difference of $+0.0000\ [0.0000, 0.0000]$ across all market regimes.
- **Automated Detection Test:** `test_benchmark_isolation.py`. Asserts that baseline parameter objects are deeply copied and decoupled from candidate strategy specifications, verifying separate execution paths for managed vs unmanaged baselines.

### Error 5: Cross-Market Fee Contamination (Crypto Perp Fees on Forex Shorts)
- **What Was Wrong:** In Phase 3, the cost parity engine universally applied the crypto perpetual taker fee schedule (5 bps taker + 3 bps slippage = 8 bps per side) across all historical trades, including Forex pairs (`GBP/USD`, `EUR/USD`, `USD/JPY`) where stop distances were only 8 to 11 pips ($0.08\%$ to $0.11\%$).
- **Empirical Impact:** Imposed an unrealistic $1.5$ R to $1.7$ R friction penalty per trade on Forex shorts, erroneously driving Core Shorts cost delta to $-0.4719$ R (~7x median cost) and reported mean to $-1.0190$ R.
- **Automated Detection Test:** `test_multi_market_fee_model.py`. Validates that asset classes map strictly to their respective cost structures (forex spread models for fiat pairs, perpetual fee/funding models for crypto).

### Error 6: Machine Learning Feature Leakage from Trade Geometry (Candidate 2E)
- **What Was Wrong:** In Phase 2E, decision tree models were trained on features that included `cost_r`, `stop_dist_pct`, and `atr_pct`. Because realized R is inversely proportional to stop distance, the tree learned trade geometry rather than forward price direction.
- **Empirical Impact:** Created a false out-of-sample rank correlation of $+0.675$, which collapsed to $+0.001$ ($p = 0.216$) when geometry features were ablated.
- **Automated Detection Test:** `test_ml_feature_ablation.py`. Mandates an automated control model benchmark and feature ablation test; any ML strategy where rank IC does not survive on pure technical/macro signals devoid of stop/cost features is automatically killed.

### Error 7: Manual Data Entry and Transcription in Research Reports
- **What Was Wrong:** Numeric tables in Phase 0.6, 1.1, and 3 reports were partially hand-typed or copied between markdown documents and runner scripts, allowing rounding anomalies, transposition errors, and copy errors (such as 0.0000R delta on ranging longs) to pass undetected.
- **Empirical Impact:** Divergent numbers across reports and scripts, eroding research trust and requiring extensive forensic reconciliation.
- **Automated Detection Test:** [`scripts/generate_report.py`](file:///c:/Users/Admin/Trading%20Bot%20app/scripts/generate_report.py) and `test_report_tables.py`. Every markdown table must be programmatically generated via named queries and print its `Query ID`, row count, and code git hash. CI fails if any numeric table lacks programmatic provenance.

---

## Architectural State Going Forward

1. **Scanner Mode:** The backend paper scanner remains permanently in **LOG-ONLY** forward observation mode (`FLASH_PAPER_MODE = True`).
2. **Live Execution Lock:** `LIVE_TRADING_ENABLED` is locked at **`False`** in `backend/app/config.py`.
3. **Repository Preservation:** Rules R1–R7 remain in force. Research harnesses and diagnostic suites are archived for institutional provenance.
4. **Governance Readiness:** Live order routing remains prohibited unless all 12 conditions in [`docs/CAPITAL_READINESS_CHECKLIST.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/CAPITAL_READINESS_CHECKLIST.md) are satisfied.
