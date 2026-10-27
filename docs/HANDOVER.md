# Engineering Handover & Governance Protocol

**Program Status:** **`HALT`** (Research Closed, Live Trading Permanently Disabled)  
**Effective Date:** 2026-10-27  
**System Operating Mode:** **`LOG-ONLY`** Forward Paper Observation (`FLASH_PAPER_MODE = True`)  
**Lead Quantitative Mandate:** Maintenance & Governance Handover

---

## 1. What Is Running

The following background processes and services remain operational in **read-only / log-only mode**:

1. **Market Scanner (`backend/app/main.py`):**
   - **Mode:** Background event loop polling 4h and 1h Binance perpetual markets.
   - **Signal Generation:** Evaluates incoming market bars against frozen indicators (`config/frozen_core_long_v1_1.json`).
   - **Order Execution:** **DISABLED**. No orders are routed to any exchange API.
   - **Persistence:** Generated signals are written to PostgreSQL `signals` with `shadow = True` for forward paper observation.
   - **Outcome Resolution:** Background worker periodically resolves expired paper signals to track forward out-of-sample performance in `outcomes`.

2. **Reporting API & Frontend Dashboard (`backend/app/performance.py` & `frontend/`):**
   - Fast-API backend serves `/performance` displaying reconciled dollar P&L and R-units.
   - Next.js frontend runs with `#00E5A8` "Ledger Reconciled" badge.

---

## 2. What Is Locked (Immutable Safeguards)

Under standing institutional rules R1–R7, the following safeguards are strictly locked:

1. **Live Trading Guardrail (`backend/app/config.py`):**
   ```python
   # Line 63: LOCKED TO FALSE
   live_trading_enabled: bool = False
   ```
   Live order routing is impossible while this flag is `False`. Any attempt to flip this flag to `True` is blocked by CI and requires satisfying all 12 conditions in [`docs/CAPITAL_READINESS_CHECKLIST.md`](file:///c:/Users/Admin/Trading%20Bot%20app/docs/CAPITAL_READINESS_CHECKLIST.md).

2. **v1.1 Parameter Freeze (`config/frozen_core_long_v1_1.json`):**
   - **Locked SHA-256 Checksum:** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928`
   - **Enforced By:** [`backend/scripts/test_freeze_hash.py`](file:///c:/Users/Admin/Trading%20Bot%20app/backend/scripts/test_freeze_hash.py). CI fails if the file or any parameter within it is modified.

3. **Direction A Strategy Freeze (`config/dirA_spec.json`):**
   - **Locked SHA-256 Checksum:** `119d7245491f5df601d0159310e775a0e76a21514a643b183372660ab4977664`
   - Cross-sectional composite strategy parameters are frozen.

4. **Fee & Execution Engine (`backend/app/costs.py` & `backend/app/execution.py`):**
   - Perpetual fees locked at Maker: 2.0 bps, Taker: 5.0 bps, Stop Slippage: 3.0 bps.

---

## 3. Governance: Who Reviews Before Any Status Change

Any proposed change to strategy status (e.g., from `HALT` to `SHADOW`, or from `SHADOW` to `LIVE`) requires unanimous multi-stakeholder approval and cryptographic verification:

| Role | Responsibility | Mandatory Pre-Conditions for Approval |
| :--- | :--- | :--- |
| **Chief Risk Officer (CRO)** | Capital allocation and drawdown caps | Verified that max potential portfolio drawdown $\le 10\%$; account equity $\ge \$25,000$; risk-free rate hurdle exceeded by $\ge +2.0\%$ net. |
| **Head of Quantitative Research** | Statistical significance and edge verification | Confirmed out-of-sample forward paper performance: $N \ge 100$ trades, $N_{\text{eff}} \ge 85$, Mean Net $R \ge +0.15$, 95% bootstrap lower bound $> 0$, DSR $\ge 0.95$. |
| **Lead Infrastructure / DX Engineer** | Execution integrity and exchange connectivity | Validated exchange websocket latency $< 50\text{ ms}$, through-by-1-tick execution model, reconciliation delta $\Delta = \$0.0000$, and zero lookahead test green. |
| **Senior Governance / Compliance Officer** | Audit compliance and parameter freeze | Verified SHA-256 checksums of all frozen files; verified that all numbers in reports originate from deterministic Query IDs without manual edits. |

### Status Change Workflow
```
[PROPOSED STATUS CHANGE]
           |
           v
[Run Automated Audit Suite: pytest tests/]
           |
           v (Must Pass 100% Green)
[Verify CAPITAL_READINESS_CHECKLIST.md (All 12 Gates)]
           |
           v (All Gates Satisfied)
[4-Way Cryptographic Sign-Off: CRO, Head of Quant, Lead Eng, Compliance]
           |
           v
[Status Transition Approved (Logged to DB audit_logs)]
```

---

## 4. Operational Checklist for On-Call Engineer

- **Daily Check:** Verify PostgreSQL connection and ensure scanner process is active in log-only mode (`tail -n 50 backend/scanner.log`).
- **Weekly Check:** Query new forward paper trades:
  ```sql
  SELECT count(*), avg(o.r_net) 
  FROM signals s 
  JOIN outcomes o ON o.signal_id = s.id 
  WHERE s.created_at >= '2026-10-26T16:00:00Z';
  ```
- **Alert Escalation:** If `live_trading_enabled` is ever detected as `True` without four-way sign-off, immediately kill the scanner process and notify the Chief Risk Officer.
