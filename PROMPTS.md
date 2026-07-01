# Master Prompts

Reusable prompts for building the Universal Signal Cockpit. Paste into Antigravity (Plan mode)
or any Claude-class coding agent. These reflect the **tightened** plan in [PLAN.md](PLAN.md):
backtest-core-first, fixed weights, ~15 orthogonal factors, learning deferred.

---

## Phase 1 master prompt (crypto, walking skeleton)

```
ROLE: Senior full-stack engineer. Build "Universal Signal Cockpit", a personal
multi-market trading DECISION-SUPPORT web app (not financial advice).

NON-NEGOTIABLE RULES:
- All indicator/price/level/score values are computed in Python (pandas-ta + hand-coded
  exotics). The LLM NEVER generates a numeric value — it only reasons over the structured
  data we pass and writes the rationale.
- Backtest integrity is the highest priority: bar-by-bar replay, the decision at bar t may
  only see data through bar t-1 close, explicit fees + slippage, no lookahead, no survivorship.
  A backtest that lies is worse than none.
- Stack: Next.js + TypeScript + Tailwind + shadcn/ui + Lightweight Charts (frontend);
  FastAPI + pandas-ta (backend); Supabase (Postgres + pgvector); OpenRouter for model
  routing; Tavily + SerpAPI for news; tradingview-ta for consensus.
- Start with ~15-20 ORTHOGONAL factors (2-3 per category), FIXED hand-tuned weights.
  Do NOT build adaptive ML, HMM regimes, pgvector memory, or multi-agent debate yet.
- UI: clean, bright, matte, premium, next-gen. No emojis, no clutter.
- Every signal logs its 8-category scores, composite, confidence, and (placeholder) regime.

BUILD ORDER (do NOT reorder — backtest core comes before LLM and UI):

PHASE 0 — Foundations (local):
  - Monorepo: /backend (FastAPI), /frontend (Next.js), /db (SQL migrations).
  - Supabase schema incl. pgvector extension; .env.example placeholders.
  - Health check endpoint; /webhook/tradingview stub (shared-secret token check only).

PHASE 1a — Honest backtest core (no LLM, no UI):
  - Binance fetchers (keyless): OHLCV, order-book depth, global long/short ratio.
  - Indicator engine: EMA stack (9/21/50/200), MACD, RSI, Stochastic, ATR, Bollinger,
    VWAP, Fibonacci, pivots. Hand-code UT Bot / Supertrend if used.
  - 8-category factor scorer -> composite (Strong Sell..Strong Buy) + 0-100 confidence,
    FIXED weights, weights vary by timeframe. Add tradingview-ta as external-consensus factor.
  - Backtest harness: bar-by-bar replay through the scorer with fees + slippage; report
    hit-rate, P&L, MFE/MAE per symbol/timeframe.

PHASE 1b — Reasoning + one signal card:
  - LLM reasoning endpoint (OpenRouter): takes structured scores + cached Tavily/SerpAPI
    news digest, returns label, confidence, rationale, suggested entry/stop/target.
  - One signal card UI + timeframe switcher (Intraday/Short/Swing/Long-term) + Lightweight Chart.

DELIVER an Implementation Plan artifact first for each phase. Wait for approval before coding
the next phase. Keep secrets in .env (placeholders for now). Local dev on Windows.
```

---

## Per-phase kickoff prompt (short form)

```
Continue the Universal Signal Cockpit per PLAN.md. Implement <PHASE> only.
Honor the non-negotiable rules (deterministic math, LLM-reasoning-only, backtest integrity,
fixed weights, deferred learning). Show me the file tree and the key files, then a way to run
and verify it locally before moving on.
```
