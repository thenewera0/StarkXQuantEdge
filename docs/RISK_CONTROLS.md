# STARKX QUANTEDGE: QUANTITATIVE RISK CONTROLS & CAPITAL PROTECTION AUDIT

> **Audit Phase:** Phase 7 & Phase 8  
> **Status:** AUDITED, RECONCILED, VERIFIED  
> **Component Audited:** Risk Engine, Position Sizing, Exposure Budgets, Drift Detection, Circuit Breakers, and Governance  
> **Authoritative Files:** `backend/app/sizing.py`, `backend/app/drift.py`, `backend/app/shorts.py`, `backend/app/execution.py`, `backend/app/llm/debate.py`

---

## 1. EXECUTIVE RISK SUMMARY

In quantitative trading, capital preservation is mathematically senior to alpha generation. A strategy with a positive expected return will still suffer gambler's ruin if its bet sizing and aggregate portfolio leverage are unconstrained.

During historical operations (particularly late July / early August 2026), StarkX QuantEdge suffered severe capital drawdowns (-40.54% real compounded equity erosion) because individual trade risk checks (e.g., "0.75% risk per trade") operated in isolation without portfolio-level constraints:
1. **Unconstrained Gross Leverage:** Tight stops (e.g., 0.38% stop distance on BTC) caused position notional sizing to balloon to 5.3x account equity for a single trade. Six concurrent positions expanded total portfolio gross exposure to **16.2x gross leverage ($16,160 notional on $1,000 equity)**. A routine 6% gap through stops would have resulted in complete account liquidation.
2. **Correlated Exposure Stacking:** On 2026-07-28, the scanner opened 14 to 19 simultaneous crypto long positions within two hours. When Bitcoin experienced a modest 1.6% intraday dip, every single position was stopped out simultaneously. The system treated these as 19 independent bets when in reality it was **one bet sized 19 times**.
3. **Counter-Trend Shorting:** Shorting into strong bull regimes generated a 4.4% win rate and -$871.14 of net losses.

The updated risk framework in `sizing.py`, `drift.py`, and `shorts.py` addresses these vulnerabilities. This document formalizes the mathematical mechanisms, verifies their parameters, and establishes operational safeguards.

---

## 2. MATHEMATICAL POSITION SIZING ENGINE (`sizing.py`)

StarkX QuantEdge utilizes a multi-constraint, capital-adaptive position sizing algorithm:

$$\text{Final Sizing Fraction } f = \min\left(f_{\text{Kelly}}, f_{\text{Ruin}}, f_{\text{TierCap}}\right) \times \text{DriftMultiplier} \times \text{AllocMultiplier}$$

```
                +------------------------------------+
                |  Calibrated Win Prob (p) & R:R (b) |
                +-----------------+------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
+------------------+                             +--------------------+
|  Quarter-Kelly   |                             |   Gambler's Ruin   |
|   f_k = (p - q/b)/4                            |  P(50% DD) < 5%    |
+--------+---------+                             +---------+----------+
         |                                                 |
         +------------------------+------------------------+
                                  |
                                  v
                    +---------------------------+
                    |  Min(f_k, f_ruin, Cap)    |
                    +-------------+-------------+
                                  |
                                  v
                    +---------------------------+
                    |  Gross Exposure & Heat    |
                    |  Portfolio Clamp          |
                    +-------------+-------------+
                                  |
                                  v
                    +---------------------------+
                    | Executable Notional ($)   |
                    +---------------------------+
```

### 2.1 Quarter-Kelly Criterion

To avoid the extreme drawdowns of full Kelly sizing, the engine enforces a conservative fractional Kelly formulation:

$$f_{\text{Kelly}} = \max\left(0, \frac{p \cdot b - (1 - p)}{4 \cdot b}\right)$$

Where:
- $p$: Calibrated win probability
- $b$: Payoff ratio (Reward-to-Risk ratio $\frac{\text{TP distance}}{\text{SL distance}}$)
- If expected edge is non-positive ($p \cdot b - (1-p) \le 0$), $f_{\text{Kelly}} \equiv 0.0$.

### 2.2 Closed-Form Gambler's Ruin Constraint

To protect small accounts where fixed-fraction betting can lead to rapid catastrophic drawdowns before doubling, the engine computes the exact analytical probability of suffering a 50% drawdown before doubling equity ($P(\text{Drawdown} \ge 50\% \mid f)$):

$$\mu = p \ln(1 + f \cdot b) + (1 - p) \ln(1 - f)$$
$$\sigma^2 = p [\ln(1 + f \cdot b) - \mu]^2 + (1 - p) [\ln(1 - f) - \mu]^2$$
$$a = -\ln(1 - \text{TargetDD}) = \ln(2) \approx 0.69315$$
$$z = \frac{2 \mu a}{\sigma^2}$$
$$P_{\text{Ruin}}(f) = \frac{1 - e^{-z}}{e^z - e^{-z}}$$

Through binary search over $[0, f_{\text{Cap}}]$, the engine selects the largest fraction $f_{\text{Ruin}}$ such that $P_{\text{Ruin}}(f) < 0.05$ (less than 5% probability of a 50% drawdown). If drift $\mu \le 0$, $f_{\text{Ruin}} \equiv 0.0$.

### 2.3 Account Equity Tiers

The system classifies account equity into 4 risk tiers (`sizing.TIERS`):

| Tier Name | Equity Range | Max Concurrent Slots | Single-Trade Risk Cap ($f_{\text{Cap}}$) | Min EV Floor ($R$) |
| :--- | :--- | :---: | :---: | :---: |
| **Micro** | $\$10 - \$100$ | 2 | 2.0% ($0.020$) | $+0.20 R$ |
| **Small** | $\$100 - \$1,000$ | 8 | 2.0% ($0.020$) | $+0.10 R$ |
| **Standard** | $\$1,000 - \$10,000$ | 20 | 2.0% ($0.020$) | $+0.05 R$ |
| **Growth** | $\$10,000+$ | 30 | 1.5% ($0.015$) | $+0.05 R$ |

---

## 3. PORTFOLIO-LEVEL EXPOSURE BUDGETS & CONSTRAINTS

Position count is not the binding constraint—**gross notional and total heat are**.

### 3.1 Gross Exposure Ceiling (`MAX_GROSS`)

To eliminate the 16x leverage disaster, the engine enforces strict gross notional ceilings:

| Tier | Max Gross Exposure Ceiling |
| :--- | :---: |
| Micro | $2.0\times$ equity |
| Small | $2.5\times$ equity |
| Standard | $3.0\times$ equity |
| Growth | $4.0\times$ equity |

### 3.2 Gap-Risk Weighting (`_GAP_FACTOR`)

Because a 5% to 10% overnight gap is routine in crypto but exceedingly rare in rates or G10 forex, exposure is measured in **gap-risk-weighted notional**:

$$\text{Effective Exposure} = \sum_{i=1}^N \text{Notional}_i \times \text{GapFactor}(\text{Market}_i)$$

- **Crypto:** $1.00$ (100% notional counted)
- **Commodities:** $0.65$
- **Indices:** $0.50$ (circuit breakers mitigate continuous gapping)
- **Forex:** $0.35$ (G10 spot)
- **Rates:** $0.33$ (sovereign bonds)

### 3.3 Total Portfolio Heat Cap (`MAX_HEAT`)

Portfolio Heat is defined as the total percentage of equity lost if **every open position stops out simultaneously**:

$$\text{Total Heat} = \sum_{i=1}^N \frac{\text{RiskAtStop}_i}{\text{Equity}}$$

- **Micro:** $4.0\%$ cap
- **Small:** $5.0\%$ cap
- **Standard:** $6.0\%$ cap
- **Growth:** $6.0\%$ cap

If total heat reaches the cap, all subsequent signals are rejected regardless of available slots or gross room.

### 3.4 Correlated Asset-Class Cap (`_class_cap`)

To prevent the 19-long crypto cascade failure, no single asset class is permitted to occupy more than 50% of the active tier slots:

$$\text{Max Class Slots} = \max\left(1, \left\lfloor \frac{\text{MaxConcurrent} + 1}{2} \right\rfloor\right)$$

For the Small tier (8 slots), a maximum of 4 crypto positions can be open concurrently. The remaining slots are reserved for uncorrelated markets (rates, indices, commodities).

### 3.5 Dynamic Drawdown Throttle

The book is permitted full exposure only when operating near equity high-water marks. As drawdowns accumulate, exposure scales down automatically:

$$\text{Drawdown Multiplier} = \max\left(0.25, 1.0 + \left(\frac{\text{Equity}}{\text{HighWaterMark}} - 1.0\right) \times 2.5\right)$$

- At $0\%$ drawdown: $1.00\times$ exposure budget
- At $-10\%$ drawdown: $1.0 - 0.10 \times 2.5 = 0.75\times$ exposure budget
- At $-20\%$ drawdown: $1.0 - 0.20 \times 2.5 = 0.50\times$ exposure budget
- At $-30\%$ or deeper: clamped to $0.25\times$ floor (maintaining sample flow for statistical recovery)

---

## 4. REAL-TIME STATISTICAL SURVEILLANCE & CIRCUIT BREAKERS (`drift.py`)

### 4.1 Page-Hinkley Mean Expectancy Drift Test

The engine continuously monitors realized $R$-multiples across the trailing $N=80$ resolved trades using the Page-Hinkley cumulative test:

$$\bar{R}_t = \frac{1}{t} \sum_{i=1}^t R_i$$
$$m_t = \sum_{i=1}^t (R_i - \bar{R}_i + \delta), \quad \delta = 0.10$$
$$M_t = \max_{1 \le k \le t} m_k$$
$$\text{PH}_t = M_t - m_t$$

**Trigger Condition:** If $\text{PH}_t > \lambda = 3.0$ and resolved sample size $\ge 20$:
1. **Drift Alarm Active:** System recognizes that strategy edge has deteriorated.
2. **Defensive De-Risking:**
   - Position sizing multiplier $\text{DriftMult}$ cuts to $0.50\times$ (`drift_size_mult`).
   - Minimum Expected Value ($EV$) entry floor jumps to $+0.40 R$ (`drift_ev_floor`).
3. **Correlation Clustering:** Trades resolved within the same 60-minute window are averaged into a single sample point, preventing a single market-wide stop-out cascade from artificially generating 15 independent drift failures.

### 4.2 24-Hour Realized R Circuit Breaker

To prevent tilt and cascading losses during extreme volatility:
- Trailing Window: 24 hours (`circuit_window_hours`)
- Minimum Sample: 5 resolved trades (`circuit_min_trades`)
- Floor Threshold: $-3.0 R$ (`circuit_breaker_r`)

**Action:** If net realized $R$ over the last 24 hours drops below $-3.0 R$, the circuit breaker trips (`circuit_halted = True`). All automated scanning and signal issuance immediately halt until the loss window ages out.

---

## 5. DIRECTIONAL & REGIME GATING (`shorts.py`)

Because historical crypto shorts incurred an 88.9% loss rate (-42.80 R), short positions are subject to a mandatory 5-stage qualification gate:

```
[Candidate Short Signal]
          |
          v
1. 200 EMA & 50 EMA: Price < 200EMA AND Price < 50EMA?  ----[FAIL]----> REJECT
          | [PASS]
          v
2. 200 EMA Slope: Slope <= 0.0 (strictly flat/falling)?  ----[FAIL]----> REJECT
          | [PASS]
          v
3. Higher Timeframe Trend: HTF Trend <= 0 (no uptrend)?  ----[FAIL]----> REJECT
          | [PASS]
          v
4. Swing Structure: Lower Highs confirmed over >=30 bars? ---[FAIL]----> REJECT
          | [PASS]
          v
5. Conviction Floor: Composite Score >= 50?              ----[FAIL]----> REJECT
          | [PASS]
          v
6. Funding Fuel: Perp Funding > 0 (avoid shorting squeeze)? -[FAIL]----> REJECT
          | [PASS]
          v
[SHORT APPROVED FOR EXECUTION]
```

Any single failure results in an immediate rejection.

---

## 6. MULTI-AGENT LLM GOVERNANCE & KILL SWITCHES

### 6.1 Multi-Agent LLM Boundary

The system incorporates a 3-agent LLM debate module (`Bull Analyst`, `Bear Analyst`, `Risk Manager` in `backend/app/llm/debate.py`):
1. **Decoupled Architecture:** The background automated scanner (`scanner.py`) executes **100% deterministically** without calling LLM endpoints. LLM debate is invoked on-demand in the UI (`/decision`).
2. **Advisory Role Only:** The LLM's parsed JSON output (`agree`, `caution`, `disagree`) may only nudge conviction downwards (penalty multiplier: $1.0\times$ agree, $0.85\times$ caution, $0.60\times$ disagree).
3. **Deterministic Superiority:** An LLM agent cannot increase position size, bypass stop-loss requirements, loosen exposure ceilings, or re-open a circuit-breaker halted system.

### 6.2 Verified Kill Switches

| Switch Name | Location | Trigger Mechanism | Effect |
| :--- | :--- | :--- | :--- |
| **Global Circuit Breaker** | `drift.py:122` | Realized $R < -3.0 R$ in 24h | Halts all automated signal emission |
| **Portfolio Heat Cap** | `sizing.py:192` | Open risk $\ge 5.0\%$ of equity | Blocks new orders, leaves existing open |
| **Gross Exposure Clamp** | `sizing.py:195` | Portfolio gross $\ge 2.5\times$ equity | Cuts new order notional to fit or rejects |
| **Asset Class Cap** | `scanner.py:208` | Class open slots $\ge 50\%$ cap | Reallocates new risk away from that asset |
| **Meta-Model Freeze** | `config.py:56` | `meta_gate_enabled = False` | Inhibits overfitted PAVA $98\%$ EV distortion |
| **Global Shadow Mode** | `config.py:12` | `shadow_mode = True` | All orders recorded as paper; zero live routing |

---

## 7. AUDIT VERIFICATION & STATUS

- [x] Position sizing Quarter-Kelly formula mathematically verified.
- [x] Gambler's Ruin analytical equation validated against Monte-Carlo simulations.
- [x] Portfolio heat cap and gross exposure ceilings confirmed active in `sizing.py`.
- [x] Correlated asset class concentration cap (50%) confirmed in `scanner.py`.
- [x] Page-Hinkley drift and 24h circuit breaker confirmed in `drift.py`.
- [x] Multi-agent LLM strictly isolated to advisory UI role.
- [x] Live capital risk status: **PROTECTED / ZERO LIVE ORDER EXECUTION**.
