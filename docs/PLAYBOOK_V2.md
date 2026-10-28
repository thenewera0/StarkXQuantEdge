# StarkX QuantEdge v2 — Sleeve Governance Playbook

**System:** StarkX QuantEdge v2 Systematic Portfolio Engine  
**Governance Authority:** Quantitative Risk & Edge Rehabilitation Board  
**Purpose:** Formal protocol for researching, pre-registering, and promoting a new trading sleeve into the v2 portfolio engine.

---

## 1. Principles of Sleeve Governance

1. **Honest Trial Accounting:** The trial counter is global and monotonically increasing. Under no circumstances may a failed idea be erased, rebranded, or retroactively excluded.
2. **Pre-Registration Lock:** Every parameter, lookback, universe rule, and evidence gate must be registered in `config/v2_spec.json` with its cryptographic SHA-256 hash **BEFORE** running any backtest or simulation.
3. **Four-Stage Promotion Lifecycle:**
   - **Stage A (Research):** Historical backtesting across $\ge 2$ full secular market cycles, out-of-sample holdouts, and neighbourhood parameter sensitivity checks.
   - **Stage B (Shadow):** Real-time daily target computation on live feeds at 00:05 UTC. Targets logged; zero orders submitted.
   - **Stage C (Paper-Executed):** Orders routed through the systematic paper broker with queue haircuts, maker-first repricing, taker crossing rules, and volume-tiered fees.
   - **Stage D (Micro-Live):** Real money execution unlocked strictly by the owner under hard statutory caps ($100 max capital, 2% daily loss, 15% drawdown, HMAC kill-switch).

---

## 2. Step-by-Step Protocol to Add a New Sleeve

### Step 2.1: Increment Trial Counter & Formulate Hypothesis
Obtain the latest trial number from `config/v2_spec.json`. If current is 518, the new sleeve is assigned Trial 519.
Document:
- Theoretical market anomaly (e.g. term structure basis, volatility risk premium, cross-sectional momentum).
- Economic rationale why the edge should persist after transaction friction and taxes.
- Long/flat or directional constraints.

### Step 2.2: Define Quantitative Specification & Evidence Gates
Specify exact parameter vectors:
- Data source, bar resolution (CLOSED daily bars at 00:00 UTC).
- Signal definitions and composite formula.
- Volatility estimator and target portfolio volatility.
- Liquidation buffer requirements ($\ge 3\times \text{ATR}(1\text{d})$ for leveraged legs).
- Pre-defined Stage A $\to$ B evidence gates:
  - Benchmark comparison (terminal wealth vs Cash and Buy-and-Hold across $\ge 36$ monthly start dates).
  - Maximum drawdown ratio ($\le 60\%$ of Buy-and-Hold).
  - Pre-tax net-of-cost Sharpe ratio on qualified point-in-time liquid universe ($\ge 0.60$).
  - Neighbourhood parameter robustness: all variants scaled by $0.75\times$ and $1.25\times$ must satisfy drawdown and turnover constraints ($\le 12$ switches/year).

### Step 2.3: Commit Pre-Registration SHA-256 Hash
Update `config/v2_spec.json` and compute the SHA-256 hash:
```bash
python -c "import hashlib, json; data=json.load(open('config/v2_spec.json')); print(hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest())"
```
Record the resulting hash in git commit message and CI guards before executing any simulation.

### Step 2.4: Execute Evidence Verification in Stage A
Run the canonical day-block bootstrap ($B=10,000, \text{seed}=17$):
- Compute 5th and 95th percentile confidence intervals.
- Do NOT use effective sample size approximations ($N_{\text{eff}}$); report raw active trading days and total trades.
- Evaluate each gate: outcome is binary (`PASS` or `FAIL`), never argued or rationalized.

### Step 2.5: Stage B Shadow Period (60 Days)
If all Stage A $\to$ B gates pass:
- Sleeve is added to `allocator.py` with allocation capped at maximum sleeve share (e.g. $\le 25\%$).
- Must run in shadow mode for $\ge 60$ days.
- Tracking error between paper fills and ideal close must remain $\le 1.50\%$ annualized.
- Zero ledger reconciliation breaks ($|\delta| \le 0.01$ USD) allowed.

### Step 2.6: Stage C Paper Execution (180 Days)
- Paper broker executes orders using through-by-1-tick rule with 50% queue haircut.
- Must execute for $\ge 180$ continuous days without rule violations.
- Realized drawdown must remain inside the simulated 95th percentile.
- CA review of financial-year tax schedule under Scenarios A and B.

### Step 2.7: Stage D Micro-Live Unlock (Owner Action Only)
- Owner manually unlocks `V2_LIVE_ENABLED=true` in environment configuration.
- Enforces:
  - `V2_MAX_CAPITAL_USD = 100` (or configured micro limit)
  - `V2_MAX_DAILY_LOSS_PCT = 2.0%`
  - `V2_MAX_DRAWDOWN_PCT = 15.0%`
  - HMAC-SHA256 kill switch active on `POST /v2/kill`.
