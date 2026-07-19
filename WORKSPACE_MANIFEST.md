# PROJECT MANIFEST

## 1. PROJECT IDENTITY
**StarkX QuantEdge** is an autonomous, multi-market trading decision-support cockpit. Its core purpose is to continuously scan markets, evaluate setups using a deterministic pure-Python mathematical indicator engine, and output objective, explainable trading signals. The system relies on a rigorous "no-hallucination" philosophy: the LLM is only utilized to generate narrative debate and rationale based strictly on the structured numbers fed to it. It manages risk geometry, tracks backtest performance, and dynamically adapts factor weights using a gated, machine learning walk-forward loop.

## 2. FRAMEWORKS & STACK
*   **Languages:** Python 3 (Backend), TypeScript (Frontend), SQL (Database)
*   **Database:** Supabase (PostgreSQL with `pgvector`), accessed via direct `psycopg` (binary pooling).
*   **Hosting Platforms:** Render (`render.yaml` defines a Dockerized backend service `starkx-quant-edge-api`), Vercel (intended for Next.js frontend).
*   **Major Dependencies (Backend):** FastAPI, Uvicorn, Pandas, NumPy, Pydantic, APScheduler, HTTPX.
*   **Major Dependencies (Frontend):** Next.js 16 (App Router), React 19, Tailwind CSS 3, Lightweight Charts.
*   **External APIs:** OpenRouter (LLM Routing), TwelveData, Binance Public API, NewsAPI, CoinMarketCap, CryptoQuant.

## 3. CORE ARCHITECTURE
**Directory Tree Breakdown:**
*   `/backend`: The Python FastAPI core.
    *   `/app`: The main application logic housing the Confluence Engine.
        *   `/backtest`: Replay simulation and walk-forward engines.
        *   `/data`: Adapters for historical and live market data feeds.
        *   `/factors`: Scoring mechanics for trend, momentum, volatility, etc.
        *   `/indicators`: Causality-enforced pure NumPy/Pandas technical formulas (e.g., VWAP, Hurst, Kalman).
        *   `/llm`: Narrative builders and multi-agent debate wrappers via OpenRouter.
    *   `/scripts`: Utilities and migrations.
*   `/frontend`: The Next.js application containing the UI (`app/`, `components/`, `lib/`).
*   `/db`: Supabase relational database schemas and migration scripts.

**Primary API Entry Points:**
*   `GET /health`: Liveness check.
*   `GET /signal/{symbol}`: Returns deterministic factor score and trade levels.
*   `GET /signal/{symbol}/explain`: Same as above, but enriched with LLM rationale.
*   `POST /webhook/tradingview`: Secure webhook stub to listen for Pine Script alerts.

## 4. ACTIVE AUTOMATIONS
The backend runs an active **APScheduler** instance (`backend/app/main.py`) which manages several crucial background daemons:
*   **`resolver`**: Auto-resolves open signals against market outcomes based on predefined time intervals.
*   **`scanner`**: Continuously polls and evaluates watched asset symbols to emit new trading signals autonomously.
*   **`retrain`**: A weekly walk-forward machine learning job to train challenger weights and gate them against current champions.
*   **`meta_retrain`**: Evaluates the L5c meta-model (probabilistic win-rate models) on a fast cadence based on recent shadow-learning behavior.
*   **`arb`**: An hourly arbitrage detector tracking funding carry, triangular arb, and cross-exchange discrepancies.
*(Note: There are no social media macros or web scrapers natively running here, though the app relies on fetching sentiment/macro data periodically via APIs).*

## 5. UPGRADE LOG & FUTURE TODOS
**Recent Upgrades & Optimizations:**
*   Established a robust walk-forward machine learning gate preventing overfitting (champion/challenger weight logic in `learning.py`).
*   Implemented strict causal indicators (`indicators/engine.py`) explicitly avoiding TA-Lib dependencies to ensure perfect reproducibility and no look-ahead bias.
*   Embedded multi-tiered risk geometry (L5 filters) including kalman slope, volatility gating, and automated circuit breakers.

**Future Refactors & Todos:**
*   **Integrate `pgvector` FinMem:** Fully operationalize the vector-based memory retrieval for context-aware historical market states.
*   **Multi-Agent Debate:** Deploy the full Phase 5 multi-agent debate (Bull vs. Bear vs. Risk Manager) which is currently deferred due to LLM token costs.
*   **Asset Expansion:** Implement the Indian Equities broker APIs (e.g., Dhan/Upstox) and expand robustly to Forex/Gold/Macro.
*   **Notification Automation:** Add Telegram/WhatsApp integrations for real-time autonomous push alerts.
