# StarkX LAB: Operational Runbook

> **Strict Operating Mode:** `LAB_EXECUTION_MODE = 'paper'`  
> **Mandatory Rule:** Pure paper sandbox. Zero private keys, zero exchange order endpoints. All alerts carry no P&L.

---

## 1. Daily 5-Minute Checklist (00:25 UTC)

Every operator performs this 5-minute audit daily following the 00:20 UTC Learning Loop:

| Step | Check | Nominal / Safe Value | Diagnostic Command / Dashboard View |
| :--- | :--- | :--- | :--- |
| **1. Feed Lag** | Public websocket / REST kline latency | `< 10 seconds` (Alert at `> 300s`) | View `/lab` Health Strip or `GET /lab/health` |
| **2. Ledger Reconciliation** | Virtual account cash + floating R | `deltaUsd == $0.00` (to the cent) | View `/lab` Health Strip or run `test_lab_ledger_reconcile.py` |
| **3. Active Variants** | Total concurrent running variants | `8 <= N <= 40` | View `/lab` Leaderboard or `GET /lab/health` |
| **4. Open Positions** | Open paper positions across universe | `0 <= N <= 3` per variant, max 1/symbol | View `/lab` Live Positions panel |
| **5. Beta Exposure** | Portfolio beta-adjusted BTC exposure | `\|Exposure\| <= 2.0 x Equity` | View `/lab` Portfolio & Beta panel |
| **6. Spec Integrity** | SHA-256 of `config/lab_spec.json` | Bitwise equal to registered hash | Daily automated check |

---

## 2. Alarm -> Action Decision Matrix

### Alarm 1: `FEED_STALE` (Market feed lag > 5 minutes / 300 seconds)
- **Symptom:** Health strip shows red feed latency badge (`> 300s`).
- **Immediate Action:**
  1. Inspect network connectivity to Binance public REST / WS endpoint (`https://fapi.binance.com`).
  2. The lab engine automatically skips signal evaluation for that bar cycle until fresh closed bars are confirmed.
  3. Positions remain managed by local trailing stops and last-known 1m ticks.
  4. Never place orders manually.

### Alarm 2: `RECONCILIATION_BREAK` (`deltaUsd != 0.00`)
- **Symptom:** Health strip indicates `Ledger Desync` (`deltaUsd > $0.01`).
- **Immediate Action:**
  1. Freeze engine dispatching immediately (`systemctl stop starkx-lab` or terminate resolver loop).
  2. Inspect `lab_positions` for unclosed or improperly rounded positions.
  3. Run `backend/.venv/Scripts/python.exe backend/scripts/test_lab_ledger_reconcile.py`.
  4. Reconcile ledger cash to exact virtual balance before resuming ticks.

### Alarm 3: `JOB_FAILURE` (Cron job failed on bar close)
- **Symptom:** System alert indicates bar close job failure (1h, 4h, or 1d).
- **Immediate Action:**
  1. Inspect `backend/data/lab.db` lock state.
  2. Verify that closed bars were persisted to parquet cache in `backend/data_cache/`.
  3. Re-run manual bar-close tick via engine: `engine.on_bar_close_tick(timeframe)`.
  4. Engine idempotency constraint (`UNIQUE(strategy_id, variant_id, symbol, direction, bar_open_time)`) guarantees no duplicate signals or double positions are created.

### Alarm 4: `REJECTED_GEOMETRY` (Signal rejected by geometry validator)
- **Symptom:** Audit event feed shows `REJECTED_GEOMETRY` with rejection reason.
- **Immediate Action:**
  1. No operational intervention required; system correctly rejected invalid stop/target geometry.
  2. Review variant parameters in `config/lab_spec.json` to verify stop ATR or target R settings.

---

## 3. Scheduled Jobs Matrix (UTC)

| Job | Frequency | UTC Schedule | Description |
| :--- | :--- | :--- | :--- |
| **1m Resolver** | Every 1 minute | `* * * * *` | Resolves stops, targets, same-minute collisions (stop-first), and updates unrealized P&L. |
| **1h Bar-Close** | Every hour | `hh:00:05` | Evaluates 1h strategies (L3, L4, L8) on newly closed 1h bars. |
| **4h Bar-Close** | Every 4 hours | `00/04/08/12/16/20:00:05` | Evaluates 4h strategies (L2, L5, L7) on newly closed 4h bars. |
| **1d Bar-Close** | Daily | `00:05:00` | Evaluates daily strategies (L1, L6, L9, L10) on newly closed daily bars. |
| **Learning Loop** | Daily | `00:20:00` | Evaluates evidence tiers (T0-T3), computes Hedge weights, executes pause/spawn/swap. |
| **Weekly Report** | Weekly (Sunday) | `06:00:00` | Generates `docs/reports/lab_weekly_YYYYWW.md` via `scripts/generate_report.py`. |

---

## 4. Operational Invariants
- `LAB_EXECUTION_MODE = 'paper'` strictly immutable.
- Zero private keys, zero exchange order endpoints.
- Alerts carry NO P&L numbers (status and health only).
