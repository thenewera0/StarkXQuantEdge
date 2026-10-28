# Changelog: StarkX QuantEdge

## [2026-10-28] — StarkX QuantEdge v2: Evidence-Gated Systematic Portfolio Engine (Paper-First)

- **Branch:** `feature/v2-portfolio`
- **Surgical Build Invariants (Rule 0.1):** All new code isolated under `backend/app/v2/`, tables prefixed `v2_`, frontend route `/portfolio`. No changes made to frozen v1.1 cores, forward guards, scanner, or resolver. CI freeze tests `test_code_freeze_guard.py`, `test_freeze_hash.py`, and `test_cohort_invariants.py` stay 100% green.
- **Rule 0.2 Live Lock:** `LIVE_TRADING_ENABLED=false` and `V2_LIVE_ENABLED=false`. Live adapter interface implemented with non-functional `V2LiveStubAdapter` raising `NotImplementedError` unconditionally.
- **Rule 0.3 Daily Closed Bars:** All portfolio decisions execute on CLOSED daily bars at 00:05 UTC. Order IDs generated deterministically as `id = sha256(sleeve, asset, bar_open_time, side)` with unique constraint.
- **Sleeve T (Diversified Trend, Vol-Targeted, Long/Flat):** 7 signals (4 momentum lookbacks {20, 60, 120, 250}, 3 EMA pairs {(16,64), (32,128), (64,256)}), composite exposure $e = \max(s, 0)$, 30d EWMA vol targeting at $\sigma_{\text{target}}=0.15$ with 20% floor, 90-day covariance portfolio scaling, 25% single-asset cap, 100% gross exposure cap, and no-trade band hysteresis.
- **Sleeve C (Gated Carry Arbitrage):** AR(1) funding forecast, 18% GST on trading fees, 0.5% rebalance drag, and 10.5% net hurdle rate ($6.5\% \text{ cash} + 2.0\% \text{ spread} + 2.0\% \text{ liquidation premium}$). Allocation strictly $0.0\%$ when uneconomic. $\ge 3\times \text{ATR}(1\text{d})$ liquidation buffer.
- **Drawdown Governor & Allocator:** Halves Sleeve T targets at 10% peak drawdown; forces 100% Cash at 20% drawdown (latched until manual resume `V2_RESUME=true`); halts new orders for 24h on daily loss $\le -4.0\%$. Daily ledger reconciliation ($|\delta| \le 0.01$ USD).
- **Statutory Tax & Compliance Engine:** FIFO lot ledger per asset; transfer event on every disposal; Scenario A (31.2% on positive gains, 0 loss offset) vs Scenario B (31.2% on netted gains); Section 194S 1% TDS credit tracking; CA CSV export; order rebalance tax cost estimator; mandatory banner: *"Not tax advice; consult a CA"*.
- **Pre-Registration:** Specification registered in `config/v2_spec.json` (SHA-256: `3704e9e742e5ee9bcaa491df0c919fba0af23e65417ce106369e09a3803f6497`), continuing trial counter from 516 $\to$ 517 (Sleeve T) and 518 (Sleeve C).
- **Frontend:** Route `/portfolio` with dark glass theme (`#0B0F14`, `#121821`, `#1E2733`, `#E6EDF3`, `#8B98A9`, `#00E5A8`, `#FF4D6A`, `#FFB020`, `#4DA3FF`, radius 12px) featuring lightweight-charts equity curves, ledger verified badge, sleeve cards, target table, risk panel, tax panel, and evidence gates.
- **Test Suite:** 9 new unit tests covering lookahead, vol target, signals, idempotent orders, governor, tax lots, reconciliation, gates, and no-live-path all passing 100%.

## [2026-10-26] — Phase 0.6 Freeze Amendment & Parameter Split

- **Date:** 2026-10-26T08:22:03Z
- **Reason:** Split frozen parameters into signal-generating parameters (`config/frozen_core_long_v1_1.json`) and risk/sizing parameters (`config/risk_params.json`). Sizing parameters are evaluated in R-units and therefore separated from cryptographic signal locks. Signal-generating parameters remain strictly locked.
- **Old Hash (v1.0):** `e224027c42f068fca34db70e2f60e0a8fcc27acfc9c6e946765563556d837cf3` (included risk parameters)
- **New Hash (v1.1):** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` (signal-generating parameters only)
- **Signal-Generating Integrity:** Confirmed that NO signal-generating parameter, gate, threshold, weight, or geometry value was modified. All indicator thresholds, entry offsets, partial booking (0.20R / 50%), and stop parameters are identical to v1.0.
- **Sizing Mode:** Following the Phase 0.6.4 empirical audit showing non-positive information carry in `win_prob` ($t = -3.36$), paper signals now operate under `sizing_mode = "flat_risk"` with `flat_risk_pct = 0.50` (managed in `config/risk_params.json`).
- **Evaluation Entry Mode:** Formalized primary evaluation entry mode as `(c) Hybrid` (limit at close - 0.15*ATR, cancel after 2 bars, then market).
- **Forward-Test Pre-Registration Target:** Evaluation at the earlier of (i) day-cluster $N_{\text{eff}} \ge 85$ or (ii) 2027-04-26. Pass threshold = Hybrid Mean R $\ge +0.15$ AND day-block bootstrap 95% lower bound $> 0$ AND top-5 trades $\le 20\%$ of total R. Test is powered for edges $\ge \sim 0.28$ R.
