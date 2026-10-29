# StarkX LAB: Engineering Changelog

All operational engineering enhancements, bug fixes, and maintenance updates are logged here. In accordance with Section 7 Change Control, fixes recorded here preserve all signal generation logic, strategy parameters, and accounting invariants.

---

## [1.0.1] - 2026-10-29

### Operational Acceptance & Reliability Enhancements
- **Warm-Start Position Invariant:**
  - Added boolean `warm_start` to `lab_positions` schema and `LabPosition` model.
  - Flagged initial 11 launch positions as `warm_start = 1` because they entered at startup rather than awaiting subsequent bar open.
  - Excluded warm-start positions from tier progression evidence (`T0 -> T1 -> T2 -> T3`), ensuring pure closed-bar forward evidence only.
  - Retained positions in ledger for cent-level reconciliation and added `WARM START` visual badge to `/lab` dashboard.
- **3-Hour Downtime Catch-Up & Replay:**
  - Implemented `LabEngine.catch_up()` to replay missed 1-minute candles chronologically and evaluate missed bar closes.
  - Enforced Stop-First collision resolution on missed minute candles.
  - Verified idempotency and cent-level ledger reconciliation across simulated 3-hour downtime.
  - Added automated CI test suite `backend/scripts/test_lab_downtime_catchup.py`.
- **Statutory Tax Alignment (Scenario B = v2):**
  - Updated Lab Scenario B to strictly net gains and losses at 31.2% (Section 115BBH Netting Treatment, identical to v2).
  - Removed outdated 20% ordinary business income definition across code, models, tests, and documentation.
  - Updated `backend/scripts/test_lab_tax.py` and `backend/app/lab/api.py`.
- **Database Backup & Disaster Recovery:**
  - Created automated online atomic backup script `backend/scripts/backup_lab.py`.
  - Configured daily backup schedule with 14-day rolling retention and automatic pruning.
  - Verified bitwise PRAGMA integrity and executed successful restore drill ($0.00 delta).
- **Health-Only Operational Alerts:**
  - Added `RECONCILIATION_BREAK` and `JOB_FAILURE` to `LabEvent` audit kinds.
  - Dispatched verified test alerts for `FEED_STALE`, `RECONCILIATION_BREAK`, and `JOB_FAILURE` carrying zero P&L figures.
- **30-Day Change Control Guard:**
  - Recorded `LAB_START_TIMESTAMP = '2026-10-29T00:00:00Z'` in `backend/app/lab/__init__.py`.
  - Created `docs/LAB_AMENDMENTS.md` tracking pre-registered SHA-256 hash.
  - Added automated CI guard `backend/scripts/test_lab_change_control.py` enforcing the 30-day immutability lock.
