# StarkX QuantEdge — AI Crypto & Forex Confluence Engine

An autonomous, multi-market trading **decision-support** system. It scans popular pairs, emits
regime-fit signals with risk geometry, argues them with a multi-agent AI debate, verifies outcomes
against real candles, tracks fixed-notional P&L, and adapts its factor weights — all gated so it
can't drift into noise. **Not financial advice. Probabilistic edge, not a profit guarantee.**

> Core rule: every price/indicator/score/level is computed deterministically in Python.
> The LLM only *reasons over* those numbers and writes the thesis — it never invents a number.

## What it does (the loop)

```
scan popular pairs → Confluence Engine (regime + 8 factor families + agreement + psychology + risk
geometry) → emit actionable signals (silence when nothing qualifies) → log to Supabase →
resolver replays candles → label outcome (target/stop/timeout) → per-asset & combined P&L +
equity curve + per-regime breakdown → weekly champion/challenger retrain (backtest-gated)
```

Confluence Engine layers: **L1** 5-regime classifier (ADX/Choppiness) · **L2** 8 orthogonal factor
families · **L3** regime-conditional weights + agreement multiplier + conviction tiers · **L4**
positioning/psychology (crowd boost + veto) · **L5** risk geometry (laddered targets, RR≥1.5 gate) ·
**L6** hard filters / silence · **L7** enriched signal object · **L8** self-learning.

Live data: Binance (OHLCV, depth, funding, OI, basis, long/short — keyless), Twelve Data (forex/US),
NewsAPI + Fear&Greed (sentiment), CoinMarketCap (macro/dominance), CryptoQuant (on-chain, if plan
allows). Charts via Lightweight Charts.

## Layout

```
backend/   FastAPI + deterministic engine + schedulers (scanner/resolver/retrain)
  app/     data/ indicators/ factors/ backtest/ regime.py psychology.py resolver.py
           learning.py scanner.py performance.py signal_service.py main.py
  scripts/ run_backtest, walk_forward, migrate, resolve, scan_once, train_weights, verify_*
db/migrations/   Supabase schema (+ pgvector)
frontend/  Next.js 16 cockpit (chart, signal card, AI debate, scanner, performance, history)
Dockerfile render.yaml   backend deployment (always-on host)
```

## Local dev

```powershell
# Backend
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # fill keys; DATABASE_URL enables persistence + schedulers
python -m scripts.migrate       # create Supabase tables (once)
uvicorn app.main:app --reload   # http://127.0.0.1:8000/health

# Frontend (another terminal)
cd frontend
npm install
copy .env.local.example .env.local   # NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm run dev                          # http://localhost:3000
```

Everything degrades gracefully: no `OPENROUTER_API_KEY` → deterministic rationale; no `DATABASE_URL`
→ persistence/scanner/learning off but signals still work.

---

## Deploy (24/7)

**Architecture:** Frontend → **Vercel** · Backend → **Railway / Render / Fly** (always-on) · DB →
**Supabase**. Vercel serverless is ephemeral and **cannot** run the always-on scanner/resolver
schedulers, so the Python backend must live on an always-on host — not Vercel.

### 1. Supabase (already provisioned)
Project is live; run migrations once (the Docker image auto-runs them on boot, or `python -m
scripts.migrate` locally with the Session-Pooler `DATABASE_URL`).

### 2. Backend → Render (or Railway)
- **Render:** New + → Blueprint → pick this repo (uses [render.yaml](render.yaml) + [Dockerfile](Dockerfile)).
  Set env vars in the dashboard: `DATABASE_URL` (Supabase **Session Pooler**, percent-encode `@`→`%40`),
  `CORS_ORIGINS` (your Vercel URL), `OPENROUTER_API_KEY`, `TWELVEDATA_API_KEY`, `NEWSAPI_KEY`,
  `COINMARKETCAP_API_KEY`, `CRYPTOQUANT_API_KEY`. Use a plan that stays awake (free tiers sleep and
  stop the schedulers). Note the service URL, e.g. `https://starkx-quant-edge-api.onrender.com`.
- **Railway:** New Project → Deploy from repo → it builds the Dockerfile → add the same env vars.

### 3. Frontend → Vercel
- Import this repo, set **Root Directory = `frontend`**.
- Env var: `NEXT_PUBLIC_API_BASE = https://<your-backend-url>`.
- Deploy. Then add the resulting Vercel URL to the backend's `CORS_ORIGINS` and redeploy the backend.

### 4. Verify
`GET https://<backend>/health` → ok · `GET /db/status` → reachable true · open the Vercel URL →
scanner/performance/debate all populate. The schedulers (scan 30 min, resolve 15 min, retrain weekly)
run continuously on the backend host.

> Secrets are gitignored (`.env`, `.env.local`) and never committed. Set them only in the host
> dashboards. Rotate any key that was ever shared in plaintext.

## The honest caveat

Self-improving ≠ guaranteed profitable — it becomes better-calibrated and regime-aware, gated
against drift. Real edge still depends on costs and discipline. Watch the paper P&L / equity curve
and per-regime breakdown before trusting it with real capital.
