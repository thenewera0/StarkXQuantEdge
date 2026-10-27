# Changelog: StarkX QuantEdge

## [2026-10-26] — Phase 0.6 Freeze Amendment & Parameter Split

- **Date:** 2026-10-26T08:22:03Z
- **Reason:** Split frozen parameters into signal-generating parameters (`config/frozen_core_long_v1_1.json`) and risk/sizing parameters (`config/risk_params.json`). Sizing parameters are evaluated in R-units and therefore separated from cryptographic signal locks. Signal-generating parameters remain strictly locked.
- **Old Hash (v1.0):** `e224027c42f068fca34db70e2f60e0a8fcc27acfc9c6e946765563556d837cf3` (included risk parameters)
- **New Hash (v1.1):** `3fae909fb085597400a1d00de04431893172008963eca38cf2742a96ee3b6928` (signal-generating parameters only)
- **Signal-Generating Integrity:** Confirmed that NO signal-generating parameter, gate, threshold, weight, or geometry value was modified. All indicator thresholds, entry offsets, partial booking (0.20R / 50%), and stop parameters are identical to v1.0.
- **Sizing Mode:** Following the Phase 0.6.4 empirical audit showing non-positive information carry in `win_prob` ($t = -3.36$), paper signals now operate under `sizing_mode = "flat_risk"` with `flat_risk_pct = 0.50` (managed in `config/risk_params.json`).
- **Evaluation Entry Mode:** Formalized primary evaluation entry mode as `(c) Hybrid` (limit at close - 0.15*ATR, cancel after 2 bars, then market).
- **Forward-Test Pre-Registration Target:** Evaluation at the earlier of (i) day-cluster $N_{\text{eff}} \ge 85$ or (ii) 2027-04-26. Pass threshold = Hybrid Mean R $\ge +0.15$ AND day-block bootstrap 95% lower bound $> 0$ AND top-5 trades $\le 20\%$ of total R. Test is powered for edges $\ge \sim 0.28$ R.
