# Universal Signal Cockpit — Implementation Plan

> Personal multi-market trading **decision-support** app. Not financial advice. Every signal
> carries risk; nothing is trusted with real money until it survives an honest backtest.

**Status:** Planning · Local dev first · Greenfield
**Last updated:** 2026-06-30

---

## 0. The non-negotiable principle

The app does **not** predict the market. It **aggregates evidence, scores it, and explains a
decision** with a confidence level.

- All prices, indicators, levels, and scores are computed in **Python** (deterministic).
- The **LLM only reasons over** the structured data we hand it and writes the rationale.
  It **never invents a numeric value**.
- A backtest that lies is worse than no backtest. **Backtest integrity gates everything.**

---

## 1. Stack (locked for local dev)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui | Lightweight Charts for price/indicators |
| Backend | Python + FastAPI | APScheduler for polling; `/webhook/tradingview` stub |
| Indicators | **pandas-ta** (pure Python) | Avoid TA-Lib C toolchain on Windows; hand-code UT Bot / Supertrend |
| Database | **Supabase** (Postgres + pgvector) | Unlimited API requests on free tier; SQL for backtests |
| LLM | OpenRouter (model routing) | Strong model for reasoning, cheap model for routine refresh |
| News/macro | Tavily + SerpAPI (cached digest) | Refresh every N min, not every run |
| Consensus | `tradingview-ta` (unofficial) | Wrapped so failure degrades gracefully |
| Charts data | Binance public (keyless) | Authoritative source of truth for crypto |

**Secrets:** `.env` placeholders for now. Real keys (OpenRouter, Tavily, SerpAPI, Supabase)
added later. Binance public data needs none.

---

## 2. What we are deliberately NOT building yet

These are real ideas from the blueprint, deferred on purpose:

- **"100+ factors"** → start with ~15–20 *orthogonal* factors (2–3 per category). Correlated
  factors add noise, not information.
- **Adaptive weighting / contextual bandits / PPO** → meaningless with zero outcome data.
  Use **fixed, hand-tuned weights** until the outcome table has real volume (months of logging).
- **HMM regime detection** → replace with a simple ADX + realized-vol bucket
  (trending / choppy / high-vol) for the MVP.
- **pgvector "FinMem" memory retrieval** → research bet; naive embeddings of indicator vectors
  retrieve weak neighbors. Defer until a real market-state representation exists.
- **Multi-agent bull/bear/risk debate** → 3–4× LLM cost per signal; defer to Phase 5.
- **Forecast foundation models** (TimesFM/Chronos/Lag-Llama), **FinRL** → later, each must beat
  the champion on a walk-forward backtest before inclusion.
- **Live TradingView webhook infra** → build the stub now; the always-on host is a Phase 3 concern.

Principle: each added component multiplies surface area and cost while the edge still comes from
cheap robust factors + honest backtesting + discipline. Earn each addition by beating the champion.

---

## 3. The factor engine (MVP set, ~15–20 factors)

Score each category −100…+100, combine with **fixed tunable weights**, map to
Strong Sell … Strong Buy + 0–100 confidence. LLM then explains which categories drove it.

1. **Trend** — EMA stack (9/21/50/200), MACD
2. **Momentum** — RSI, Stochastic
3. **Volatility/risk** — ATR, Bollinger width
4. **Structure/levels** — Fibonacci, pivots, prior-day H/L
5. **Volume/flow** — volume vs avg, VWAP distance, order-book imbalance, long/short ratio (crypto)
6. **Sentiment/news** — LLM-scored from cached Tavily/SerpAPI digest + event tags
7. **Macro/cross-asset** — DXY, US10Y, BTC dominance (crypto-relevant subset first)
8. **External consensus** — `tradingview-ta` recommendation

Weights differ by **timeframe** (intraday leans Trend/Momentum/Flow; long-term leans Macro/Structure).
Regime-specific weights come later, only after outcome data exists.

---

## 4. Backtest integrity (the part that decides everything)

Engineering this perfectly matters more than any feature.

- **Bar-by-bar replay.** The decision at bar *t* may only see data through bar *t-1*'s close.
  No same-bar close leakage. No lookahead.
- **Explicit costs.** Model trading fees + slippage. Report results net of costs.
- **Honest metrics.** Hit-rate, P&L, max favorable/adverse excursion, per symbol + timeframe.
- **Walk-forward** for any future weight/model change (champion vs challenger).
- Guard against survivorship and regime-shift overfitting.

---

## 5. Roadmap (walking-skeleton first, then widen)

### Phase 0 — Foundations (local)
- [ ] Monorepo: `/backend` (FastAPI), `/frontend` (Next.js), `/db` (SQL migrations)
- [ ] Supabase project + enable `vector` extension
- [ ] `.env.example` with placeholders; config loading
- [ ] Health check endpoint
- [ ] `/webhook/tradingview` stub (shared-secret token check only)
- **Deliverable:** both apps boot, DB migrates cleanly.

### Phase 1a — Honest backtest core FIRST (no LLM, no UI)
- [ ] Binance OHLCV fetcher (keyless) + order-book depth + long/short ratio
- [ ] Indicator engine: EMA stack, MACD, RSI, Stochastic, ATR, Bollinger, VWAP, Fibonacci, pivots
- [ ] ~15-factor scorer → composite (Strong Sell..Strong Buy) + 0–100 confidence, **fixed weights**
- [ ] Bar-by-bar backtest harness with fees/slippage
- **Deliverable:** replay BTCUSDT across timeframes → an honest hit-rate / P&L number.

### Phase 1b — Reasoning + one signal card
- [ ] LLM rationale endpoint (OpenRouter) over structured scores + cached news digest
- [ ] Returns: label, confidence, rationale, suggested entry/stop/target
- [ ] One signal card in UI: factor breakdown + Lightweight Chart + timeframe switcher
- **Deliverable:** view a live BTC signal with its "why".

### Phase 2 — Cockpit
- [ ] Watchlist
- [ ] Signal cards w/ confidence + factor breakdown
- [ ] Cost-Saver / Trading-Mode toggle (stored in Postgres)
- [ ] `cost_log` table (log every LLM/search call's cost)

### Phase 3 — Logging → learning (only after outcome volume exists)
- [ ] Outcome labeling job (hit target / hit stop / P&L / MFE / MAE)
- [ ] Simple regime buckets (ADX + realized vol)
- [ ] Adaptive weighting, each change gated by walk-forward backtest (champion/challenger)
- [ ] TradingView Pine webhook → live signals (needs always-on host)
- [ ] pgvector memory — optional/experimental

### Phase 4 — Indian equities
- [ ] One broker API (Dhan/Upstox) — note: funded account + daily-expiring tokens

### Phase 5 — Expand + intelligence
- [ ] Forex/gold/commodities/US/ETF · macro module · multi-agent debate
- [ ] Telegram/WhatsApp alerts · signal-accuracy dashboard

---

## 6. Cost control (Cost-Saver / Trading mode)

| | Research Mode (off) | Trading / Cost-Saver (on) |
|---|---|---|
| Polling | On-demand, full | Throttled; watched symbols only |
| LLM model | Strongest | Cheap/fast; escalate to strong only on signal change |
| News search | Tavily + SerpAPI every run | Cached digest, refresh every N min |
| Indicators | Free (code) | Free (code) |

`mode` stored in Postgres; every LLM/search call logged to `cost_log`.

---

## 7. Database schema (initial tables)

- `signals` — composite, label, confidence, timeframe, regime, timestamp, symbol
- `factor_logs` — all 8 category scores per signal (for later learning)
- `outcomes` — resolved result per signal (target/stop/P&L/MFE/MAE)
- `regime_weights` — weight profile per regime (Phase 3)
- `memory_embeddings` — pgvector (Phase 3, experimental)
- `cost_log` — per-call LLM/search cost
- `watchlist` — tracked symbols + timeframes
- `settings` — mode toggle, etc.

---

## 8. Open decisions / parking lot

- Exact orthogonal-factor shortlist (correlation-check before locking weights)
- Backtest fee/slippage assumptions per market
- Hosting choice for Phase 3 always-on webhook receiver (Railway/Render/Fly)
- Indian broker pick for Phase 4

---

### Definition of done for the MVP

A signal card for one crypto symbol, across 4 timeframes, whose every number is computed in code,
whose rationale is written by the LLM over those numbers, and whose scoring strategy has been
replayed through an **honest, cost-aware, leak-free backtest** that you can read and trust.
