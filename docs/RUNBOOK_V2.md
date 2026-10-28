# StarkX QuantEdge v2 — Operations Runbook

**System:** StarkX QuantEdge v2 Systematic Portfolio Engine (Paper-First)  
**Operating Cadence:** Daily bar closed at 00:00 UTC; engine decisions execute at 00:05 UTC.  
**Branch:** `feature/v2-portfolio`  
**Live Trading Guard:** `V2_LIVE_ENABLED=false` (Enforced in `backend/app/v2/config.py` and `backend/scripts/test_v2_no_live_path.py`).

---

## 1. Daily 5-Minute Morning Protocol (00:05 UTC)

Execute daily at 00:05 UTC (immediately following the 00:00 UTC daily bar close):

### Step 1.1: Health & Heartbeat Verification
Check engine health endpoint (health and telemetry only; no P&L figures):
```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/v2/snapshot
```
Verify:
- `ledgerReconciled` is `true`.
- `deltaUsd` satisfies $|\delta| \le 0.01$ USD.
- `governor` reports `NORMAL` (or `HALVED` / `CASH` if drawdown rules are triggered).

### Step 1.2: Order Log & Rebalance Verification
Inspect daily target positions:
```bash
curl -s http://localhost:8000/v2/targets
```
- Verify all generated orders have unique, idempotent SHA-256 IDs.
- Check no-trade band hysteresis: verify orders were emitted only for assets where $|\Delta w| > \max(0.20 \times w_{\text{target}}, 0.02)$.
- Check estimated tax cost preview logged with each proposed rebalance.

### Step 1.3: Sleeve Status Check
```bash
curl -s http://localhost:8000/v2/sleeves
```
- Sleeve T: verify 15% vol-target is active, long/flat exposure $e \in [0, 1]$, and gross exposure $\le 1.0$.
- Sleeve C: verify Economic Gate state. If net forecast APR $< 10.5\%$, allocation must strictly equal $0.0\%$.

---

## 2. Weekly Review Protocol (Every Sunday 00:05 UTC)

1. **Tracking Error Audit:**
   - Run weekly tracking error calculation between paper broker fills and ideal daily-close marks:
     $$\text{Tracking Error} = \text{std}(r_{\text{paper}} - r_{\text{ideal}}) \times \sqrt{365}$$
   - Confirm annualized tracking error $\le 1.50\%$ (Stage B $\to$ C requirement).
2. **Reconciliation Audit:**
   - Confirm exactly zero ledger breaks ($|\delta| > 0.01$ USD) occurred over the trailing 7 days.
3. **Statutory Tax & TDS Ledger Review:**
   - Download the weekly CA disposal CSV:
     ```bash
     curl -s http://localhost:8000/v2/tax/ca-export -o v2_tax_schedule.csv
     ```
   - Verify Section 194S TDS credits (1%) and 18% GST on trading fees.

---

## 3. Alarm Trigger -> Exact Remediation Playbook

| Alarm State | Trigger Condition | System Automatic Action | Exact Human Operator Action |
| :--- | :--- | :--- | :--- |
| **RECONCILIATION BREAK** | Marked equity differs from book ledger by $|\delta| > 0.01$ USD | Immediate order halt. Prevents any execution. | 1. Open `v2_positions` and `v2_orders`.<br>2. Trace last filled order fill price and fee.<br>3. Resolve rounding/fee mismatch.<br>4. Re-verify reconciliation before clearing halt. |
| **DRAWDOWN HALVE** | Drawdown from peak $\ge 10\%$ | Multiplies Sleeve T targets by $0.5\times$ automatically. | 1. Confirm system has halved all asset targets.<br>2. Do not adjust parameters or override.<br>3. Monitor next daily close. |
| **DRAWDOWN CASH HALT** | Drawdown from peak $\ge 20\%$ | Zeros all Sleeve T targets ($0.0\%$, 100% Cash). Latches `CASH` state. | 1. Engine is locked in cash.<br>2. Review macro market conditions.<br>3. To resume trading, operator must manually pass `manual_resume=True` via authenticated admin config (`V2_RESUME=true`). |
| **DAILY LOSS HALT** | 24-hour return $\le -4.0\%$ | Halts all new order submissions for 24 hours. | 1. Confirm existing orders are frozen.<br>2. Wait for 24-hour timeout to lapse.<br>3. Normal trading resumes automatically at next 00:05 UTC bar if daily return recovers. |
| **CARRY UNECONOMIC** | Sleeve C net forecast APR $< 10.50\%$ | Zeros Sleeve C target allocation ($0.0\%$). | 1. No action required; economic gate is working as intended.<br>2. Sleeve C capital remains safe in Cash earning risk-free yield. |
| **EMERGENCY KILL SWITCH** | Security breach, exchange outage, or operator manual trigger | Immediate transition to 100% Cash. All open orders cancelled. Live locked. | 1. Send signed HMAC request to `POST /v2/kill`.<br>2. Confirm response returns `{"status": "HALTED"}`.<br>3. Investigate root cause before resetting state. |

---

## 4. Statutory Disclaimer

**Not tax advice; consult a CA.** All tax figures produced by the v2 tax engine represent hypothetical statutory scenarios (Scenario A vs Scenario B) modeled under Indian Virtual Digital Asset (VDA) provisions (Income Tax Act Section 115BBH, Section 194S, and CGST Act 2017).
