# StarkX LAB: Specification Amendments Ledger & 30-Day Change Control

> **Pre-Registration Hash (SHA-256):** `30410905d364ab6e4d3f8c6d7940ce0c112944de7891103a68aa776dbd7590ae`  
> **Lab Launch Timestamp:** `2026-10-29T00:00:00Z`  
> **30-Day Invariance Lock Window:** Until `2026-11-28T00:00:00Z`  
> **Strict Rule:** No strategy, spec, parameter or accounting modifications allowed before lock expiry except via pre-registered amendment recorded in this ledger. Bug fixes that do not change signals, parameters, or accounting are allowed and must be recorded in `docs/CHANGELOG_LAB.md`.

---

## 1. Change Control Policy

1. **Cryptographic Invariance:** The configuration in `config/lab_spec.json` is anchored by SHA-256 hash `30410905d364ab6e4d3f8c6d7940ce0c112944de7891103a68aa776dbd7590ae`.
2. **30-Day Freeze Window:** From `2026-10-29T00:00:00Z` to `2026-11-28T00:00:00Z`, automated CI test `test_lab_change_control.py` blocks any commit modifying `config/lab_spec.json` unless a corresponding amendment is logged below.
3. **Amendment Protocol:** Each amendment must define:
   - **Timestamp:** ISO 8601 UTC timestamp of the amendment.
   - **Reason:** Rigorous quantitative justification.
   - **New SHA-256:** Bitwise SHA-256 checksum of the amended `config/lab_spec.json`.
   - **Trial-Counter Delta:** Integer increment to the `research_trials` counter (Rule 0.6 multiple testing penalty).
4. **Permitted Operational Fixes:** Engineering bug fixes that preserve signal generation, numerical parameters, and ledger accounting are allowed without an amendment, but must be documented in `docs/CHANGELOG_LAB.md`.

---

## 2. Pre-Registered Baseline Specification (Initial State)

| Attribute | Specification Value | Verification Rule |
| :--- | :--- | :--- |
| **Spec Version** | `1.0.0` | `config/lab_spec.json` |
| **Execution Mode** | `paper` | Rule 0.1 Strict Invariant |
| **Active Catalog** | 10 Strategies (L1–L10), 15 Initial Variants | Rule 0.5 Virtual Accounts |
| **Initial Risk** | Flat 0.5% ($50 on $10,000) | Rule 0.5 Risk Model |
| **Cost Gate** | Median Cost $\le 0.25R$ | Rule 0.4 Geometry & Cost Hurdle |
| **Ledger Baseline** | $150,000.00 Total Virtual Capital | Rule 0.5 Cent-Level Reconciliation |
| **SHA-256 Checksum** | `30410905d364ab6e4d3f8c6d7940ce0c112944de7891103a68aa776dbd7590ae` | CI Cryptographic Guard |

---

## 3. Formal Amendments Log

| Amendment ID | Timestamp (UTC) | Author / Role | Justification / Reason | New Spec SHA-256 | Trial Delta | CI Approval |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `LAB-AMD-20261030-01` | `2026-10-30T06:00:00Z` | Principal Quantitative Researcher & Systems Architect | StarkX v3.0 Alpha & Execution Re-Engineering of catalog L1–L10 to eliminate negative payoff ratio inversion, add two-stage limit pullback entries and 2-tranche scale-outs, incorporate Hurst persistence and OU half-life stationarity gates, and lock maker fee advantages. | `4fd6dcf163413746aa530d1f40b655303240972a7bfb1ecc09c49ff53736f187` | `+1` | `APPROVED` |

---

## 4. Registered Amendment Details

### Amendment LAB-AMD-20261030-01
- **Timestamp:** 2026-10-30T06:00:00Z
- **Author:** Principal Quantitative Researcher & Lead Systems Architect
- **Target Section:** `config/lab_spec.json -> strategies[L1-L10]`
- **Reason:** Complete institutional re-engineering of L1-L10 catalog. Eliminates adverse selection on breakout chasing by introducing 0.35 ATR limit pullback entry, volatility compression gating (bbw_pct_rank < 0.25), Hurst trend persistence (H > 0.55), OU half-life mean-reversion filters (t_half <= 12 / 20), and beta-neutral cross-sectional long/short factor structures.
- **Prior SHA-256:** `30410905d364ab6e4d3f8c6d7940ce0c112944de7891103a68aa776dbd7590ae`
- **New SHA-256:** `4fd6dcf163413746aa530d1f40b655303240972a7bfb1ecc09c49ff53736f187`
- **Trial Counter Delta:** +1 (Increments research_trials counter for Deflated Sharpe Ratio / multiple testing correction)
- **Accounting & Safety Invariants Preserved:** YES (Execution mode remains strictly 'paper', cent-level reconciliation holds, 18% GST and slippage model preserved)

