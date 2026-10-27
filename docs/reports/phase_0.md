# Phase 0 Report: Institutional Measurement & Truth-First Edge Rehabilitation

**Date:** 2026-10-25  
**Environment:** Local / Supabase PostgreSQL  
**Commit Status:** Clean / Verified  
**Operating Rules:** Rule R1-R7 Enforced | `LIVE_TRADING_ENABLED=False` | `FLASH_PAPER_MODE=True`  

---

## Executive Summary

Phase 0 resolves all historical measurement defects across StarkX QuantEdge before any new strategy or hypothesis research can proceed. Prior metrics suffered from four major distortions:
1. **P&L Unit Distortion:** Historical outcomes mixed percentage returns with R-multiples, and prior backtest scripts had divided already-fractional decimals by 100, artificially deflating performance metrics by 100x while masking true risk-adjusted expectancy.
2. **Resolver Optimism:** Same-bar dual touches of both target and stop were previously subject to 1m subbar replay rather than conservative risk resolution.
3. **Fill Model Leakage:** Resting limit orders were considered filled upon mere touching (`low <= limit`), ignoring matching-engine priority and market micro-structure.
4. **Timeframe Lookahead in HTF:** Resampling of higher-timeframe candles evaluated the in-progress evolving bar, introducing lookahead into lower-timeframe trend filters.

All four distortions have been repaired, measured, unit-tested, and backfilled.

---

## 0.1 R-Unit Reconciliation

Realized R was recomputed from first principles for all $1,032$ resolved historical outcomes:
$$R = \frac{\text{exit\_price} - \text{entry\_fill}}{\text{entry\_fill} - \text{stop}} \times \text{direction\_sign} - \text{cost\_R}$$
with partial profit-taking ($35\%$ at $0.60R$) and the runner ($65\%$) at the final exit.

### Overall Reconciliation Metrics (n = 1,032)
| Metric | Value |
| :--- | :--- |
| **Total Resolved Outcomes** | 1,032 |
| **Mean Delta ($R_{\text{net}} - \text{Stored P&L \%}$)** | -0.1131 R |
| **Median Delta** | -0.0539 R |
| **Max Absolute Delta** | 26.3854 R |
| **Count Where Sign Differs** | 17 / 1,032 (1.6%) |

### Sample Reconciliation Table
| Signal ID | Stored P&L % | Recomputed $R_{\text{net}}$ | $Cost_R$ | Delta | Result |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | +2.1000% | +1.5100 R | 0.0000 R | -0.5900 | target |
| 11 | -0.1923% | -0.5483 R | 0.1083 R | -0.3560 | stop |
| 12 | -0.2317% | -1.0759 R | 0.0759 R | -0.8442 | stop |
| 10 | -0.2405% | -1.0712 R | 0.0712 R | -0.8307 | stop |
| 13 | -0.2210% | -1.0826 R | 0.0826 R | -0.8616 | stop |
| 16 | -0.2405% | -1.0712 R | 0.0712 R | -0.8307 | stop |
| 17 | -0.2362% | -1.0734 R | 0.0734 R | -0.8372 | stop |
| 19 | -0.8245% | -1.0483 R | 0.0483 R | -0.2238 | stop |
| 20 | -0.2661% | -1.0602 R | 0.0602 R | -0.7941 | stop |
| 21 | -0.2657% | -1.0603 R | 0.0603 R | -0.7946 | stop |
| 14 | +0.0847% | +1.4017 R | 0.1083 R | +1.3170 | target |
| 18 | +0.1154% | +1.3836 R | 0.0903 R | +1.2682 | target |
| 8 | -2.9984% | -1.0765 R | 0.0765 R | +1.9219 | stop |
| 15 | -3.7156% | -1.0679 R | 0.0679 R | +2.6477 | stop |
| 28 | -2.3383% | -1.0997 R | 0.0997 R | +1.2386 | stop |

### Headline Stats Recomputation (10,000 Stationary Bootstrap Resamples)
Recomputation of the README Section 3 benchmark cohorts in **TRUE R**:

| Strategy Cohort | n | WR % | Profit Factor | Mean R / trade | Std R | t-stat | 95% Bootstrap CI | Proven Edge? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Core 4h Long (All Regimes)** | **191** | **57.1%** | **1.84** | **+0.312 R** | **1.316** | **3.28** | **[+0.132, +0.510]** | **YES** |
| - *Regime: Trending* | 78 | 61.5% | 2.12 | +0.428 R | 1.284 | 2.94 | [+0.148, +0.718] | YES |
| - *Regime: Ranging* | 62 | 56.5% | 1.76 | +0.281 R | 1.302 | 1.70 | [-0.041, +0.608] | NO (CI <= 0) |
| - *Regime: Choppy* | 51 | 51.0% | 1.48 | +0.174 R | 1.365 | 0.91 | [-0.201, +0.549] | NO (CI <= 0) |
| **Flash Short Burst (1h/15m)** | **125** | **69.6%** | **1.14** | **+0.047 R** | **0.874** | **0.60** | **[-0.104, +0.204]** | **NO (CI <= 0)** |
| **Core Shorts (All)** | **120** | **15.8%** | **0.27** | **-0.547 R** | **0.829** | **-7.23** | **[-0.693, -0.396]** | **NO (Proven Loser)** |

#### Key Finding on "Proven" Cells:
- **Flash Short Burst (1h/15m):** Despite a high nominal hit rate ($69.6\%$), the mean payoff is only $+0.047R$ with $t = 0.60$ and a $95\%$ bootstrap confidence interval of $[-0.104, +0.204]$. **Its CI lower bound is $\le 0$. It does NOT possess a statistically validated edge.**
- **Core 4h Longs in Ranging / Choppy regimes:** Lower confidence bound crosses zero ($[-0.041, +0.608]$ and $[-0.201, +0.549]$). Only the trending regime has a statistically robust edge ($[+0.148, +0.718]$, $t=2.94$).

### Database Migration & Backfill
- Migration [`db/migrations/010_r_units.sql`](file:///c:/Users/Admin/Trading%20Bot%20app/db/migrations/010_r_units.sql) was created and applied.
- Added `outcomes.r_net NUMERIC` and `outcomes.cost_r NUMERIC`.
- Successfully backfilled 1,032 rows from first principles.
- Updated [`backend/app/resolver.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/resolver.py) and [`backend/app/persistence.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/persistence.py) to write `r_net` and `cost_r` natively on all future signal resolutions.

---

## 0.2 Resolver Pessimism Audit

- Implemented `RESOLVER_SAME_BAR_RULE = "stop_first"` behind configurable flag `resolver_same_bar_rule: str = "stop_first"` in [`config.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/config.py).
- When target and stop are touched inside the same candle, the outcome resolves strictly as `stop` (conservative).
- **Historical Impact:**
  - Historical outcomes flipping from target to stop: **1**
  - Net R impact: **-2.5100 R**
  - All future same-bar ambiguities default to stop first.

---

## 0.3 Fill Model Audit & Adverse Selection Quantification

- In [`backend/app/execution.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/execution.py), resting limit orders fill **ONLY** if a subsequent candle's low (long) / high (short) trades **THROUGH** the limit price by $\ge 1$ tick (`tick_size(price)`), and never on the signal candle (`start + 1` onward).
- **Comparative Fill Model Metrics (n = 1,143 signals):**
  - **Old Fill Rate (touching limit):** $90.29\%$ (1,032 / 1,143)
  - **New Fill Rate (trades through by $\ge 1$ tick):** $83.81\%$ (958 / 1,143)
  - **Marginal Touch Orders Rejected:** 74 orders ($6.47\%$ of signal flow)
  - **Expectancy of Filled-Only (Limit Maker):** $-0.0474$ R / trade
  - **Expectancy of Market-Entry Counterfactual:** $-0.1594$ R / signal
- **Adverse Selection Quantification (3-Bar Post-Fill MAE in R):**
  - Average 3-bar post-fill adverse move for filled orders: **$0.716$ R**
  - Average adverse move for unfilled orders that would have hit target: **$0.000$ R** (price immediately departed favorably without dipping)
  - **Adverse Selection Penalty:** **$+0.716$ R deeper drawdown** incurred on resting limits that fill versus immediate market entries.

---

## 0.4 Cost Model Audit

Configured venue- and product-specific fee parameters in [`config.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/config.py) and [`costs.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/costs.py):
- `FEE_SPOT_MAKER_BPS = 10.0` ($0.10\%$)
- `FEE_SPOT_TAKER_BPS = 10.0` ($0.10\%$)
- `FEE_PERP_MAKER_BPS = 2.0` ($0.02\%$)
- `FEE_PERP_TAKER_BPS = 5.0` ($0.05\%$)
- `STOP_EXTRA_SLIPPAGE_BPS = 3.0` ($0.03\%$)
- Taker stops/timeouts slippage: $\max(\text{depth\_model\_slippage}, 0.5 \times \text{spread}) + \text{STOP\_EXTRA\_SLIPPAGE\_BPS}$.
- Perp funding: accrued across 8h settlement periods based on holding duration and trade direction.

> [!IMPORTANT]
> **Operator Tier Confirmation Requested:** The fee model currently assumes standard retail/VIP-0 tiers (2 bps perp maker, 5 bps perp taker, 10 bps spot). If your actual exchange account tier has custom VIP or BNB fee discounts, please confirm your exact tier in response to this report so the config parameters can be calibrated to your exact execution rates.

### Cost Distribution in R by Interval
| Interval | Count | Mean $Cost_R$ | Median $Cost_R$ | Max $Cost_R$ | Tradable Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **15m** | 49 | 0.1311 R | 0.1371 R | 0.2172 R | **TRADABLE** (Median $\le 0.25R$) |
| **1h** | 726 | 0.1159 R | 0.1074 R | 1.7367 R | **TRADABLE** (Median $\le 0.25R$) |
| **4h** | 242 | 0.0939 R | 0.0683 R | 1.8687 R | **TRADABLE** (Median $\le 0.25R$) |
| **1d** | 15 | 0.0294 R | 0.0170 R | 0.1000 R | **TRADABLE** (Median $\le 0.25R$) |

*Criteria:* Any strategy/timeframe where median $Cost_R > 0.25$ is classified as **UNTRADABLE**. All four intervals currently satisfy the tradability threshold.

---

## 0.5 Lookahead Audit & Truncation Invariance

Script [`backend/scripts/test_lookahead.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_lookahead.py) tests truncation invariance:
$$f(\text{data}[:t+1]) == f(\text{data}[:t+1+k]) \quad \text{at index } t, \quad \forall k \in \{1, 10, 50\}$$

### Audit Results:
1. **Macro / Fear & Greed Publication Joins:** Tested publication timestamp ordering. Verified that `pd.merge_asof(direction="backward")` prevents future daily releases from leaking into previous hourly candles. **PASSED.**
2. **20-Symbol Universe Truncation Invariance:**
   - Evaluated 20 symbols (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `ADAUSDT`, `DOGEUSDT`, `AVAXUSDT`, `LINKUSDT`, `LTCUSDT`, `DOTUSDT`, `TRXUSDT`, `ATOMUSDT`, `UNIUSDT`, `NEARUSDT`, `APTUSDT`, `ARBUSDT`, `OPUSDT`, `FILUSDT`, `INJUSDT`) across 10 test points each and $k \in \{1, 10, 50\}$.
   - All 36 computed indicators, statistical features, and composite factor scores evaluated identically at $t$ ($\text{relative error} < 10^{-9}$). **PASSED across all 20 symbols.**
3. **HTF Closed-Bar Alignment:**
   - In [`backend/app/indicators/engine.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/app/indicators/engine.py), `htf_trend` resampled `close` had included the unclosed current bar.
   - Fixed by explicitly dropping the unclosed HTF bin (`htf = htf.iloc[:-1]`), ensuring only fully closed HTF bars inform the lower timeframe trend filter. Verified stable across future $k$ additions. **PASSED.**
4. **UT Bot / LuxAlgo MA Sabres:** Strictly sequential causal recurrence. Verified identical live vs recomputed. **PASSED.**

---

## Test Verification Suite Summary

All test suites pass cleanly:
```powershell
scripts/test_lookahead.py   -> PASSED (0 lookahead defects across 20 symbols x 3 lookaheads)
scripts/test_p0.py          -> PASSED (Costs, tiers, weights, validate_ohlcv)
scripts/test_p1.py          -> PASSED (PAVA, win_prob, EV math)
scripts/test_p2_sizing.py   -> PASSED (Kelly, ruin formulas, sizing tiers)
scripts/test_execution.py   -> PASSED (Maker/taker costs, fill_bar trade-through, partials)
scripts/test_gates_live.py  -> PASSED (Direction, regime, symbol gates)
scripts/test_price_action.py-> PASSED (Candle anatomy, S/R, patterns, sweeps)
scripts/audit_r_units.py    -> PASSED (1,032 outcomes backfilled)
scripts/audit_fill_model.py -> PASSED (Adverse selection quantified)
```

---

## STOP — Awaiting Approval

Phase 0 is complete. Per Rule R4, execution is stopped. **Do not begin Phase 1 until the user explicitly replies "approved".**
