# StarkX QuantEdge — Autonomous Quantitative Trading Engine & Cockpit

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

**StarkX QuantEdge** is an institutional-grade, multi-asset autonomous quantitative trading system and decision-support cockpit. It bridges deterministic mathematical indicator engineering, an 8-family factor confluence pipeline, machine learning probability calibration, price-action structural confirmation, capital-adaptive fractional Kelly sizing, automated walk-forward parameter re-tuning, and real-time delta-neutral arbitrage.

Every trade recommendation, stop loss, and position size is computed deterministically in Python using NumPy and Pandas with zero lookahead bias. Large Language Models (LLMs) operate strictly as qualitative narrative debaters and never generate prices or financial calculations.

---

## Table of Contents

1. [Key Architectural Principles](#1-key-architectural-principles)
2. [System Architecture & Monorepo Structure](#2-system-architecture--monorepo-structure)
3. [Empirical Strategy Foundation (1,002 Trade Audit)](#3-empirical-strategy-foundation-1002-trade-audit)
4. [Trading Engines & Subsystems](#4-trading-engines--subsystems)
   - [Core Swing Confluence Engine](#41-core-swing-confluence-engine)
   - [Flash Bot Scalping Subsystem](#42-flash-bot-scalping-subsystem)
   - [Multi-Strategy Arbitrage Engine](#43-multi-strategy-arbitrage-engine)
   - [Institutional Portfolio & Thematic Sleeves](#44-institutional-portfolio--thematic-sleeves)
5. [Mathematical Indicator & Price Action Engine](#5-mathematical-indicator--price-action-engine)
   - [Technical Indicator Engine](#51-technical-indicator-engine)
   - [Price Action & Candle Structure Engine](#52-price-action--candle-structure-engine)
6. [8-Family Factor Confluence Pipeline](#6-8-family-factor-confluence-pipeline)
7. [Risk Engineering & Capital-Adaptive Sizing](#7-risk-engineering--capital-adaptive-sizing)
   - [Quarter-Kelly & Ruin Risk Formulation](#71-quarter-kelly--ruin-risk-formulation)
   - [Exposure Budgets, Gap-Weighting & Total Heat](#72-exposure-budgets-gap-weighting--total-heat)
   - [Self-Protecting Circuit Breakers & Drift Detection](#73-self-protecting-circuit-breakers--drift-detection)
8. [Machine Learning & Self-Improving Feedback Loop](#8-machine-learning--self-improving-feedback-loop)
   - [Isotonic Probability Calibration](#81-isotonic-probability-calibration)
   - [Meta-Labeling Random Forest / Logistic Regression](#82-meta-labeling-random-forest--logistic-regression)
   - [L2 Regularized Online Weight Optimizer](#83-l2-regularized-online-weight-optimizer)
   - [Asynchronous Outcome Resolver](#84-asynchronous-outcome-resolver)
9. [Execution Economics & Order Routing](#9-execution-economics--order-routing)
10. [Multi-Agent Qualitative AI Debate System](#10-multi-agent-qualitative-ai-debate-system)
11. [Solana On-Chain Intelligence Engine](#11-solana-on-chain-intelligence-engine)
12. [Database Schema & Relational Architecture](#12-database-schema--relational-architecture)
13. [Complete FastAPI REST API Reference](#13-complete-fastapi-rest-api-reference)
14. [Frontend Cockpit Architecture](#14-frontend-cockpit-architecture)
15. [Verification, Audit & Research Suite](#15-verification-audit--research-suite)
16. [Configuration & Environment Reference](#16-configuration--environment-reference)
17. [Installation, Development & Production Deployment](#17-installation-development--production-deployment)

---

## 1. Key Architectural Principles

1. **Deterministic Python Mathematical Core**: Every indicator value, support/resistance level, stop-loss price, expected value, and position sizing fraction is computed in pure Python using NumPy and Pandas. AI/LLM models synthesize narrative context and never hallucinate numbers.
2. **Causal Zero-Lookahead Architecture**: All backtest engines, live candle pipelines, and automated resolvers enforce strict temporal causality. A signal at bar $t$ evaluates using closed bars $0 \dots t-1$ or the final close of completed bar $t$.
3. **Data-Driven Loss Elimination**: Strategies, markets, and trigger kinds that demonstrate negative statistical expectancy in live trading are automatically pruned by software gates rather than maintained on theoretical hope.
4. **Friction-First Expectancy (EV Gate)**: Every potential trade must clear a realistic round-trip cost model (spread, taker/maker fee, depth slippage) in $R$-units before capital is allocated:
   $$\text{EV} = p \cdot R - (1 - p) - \text{cost}_{R} > 0$$
5. **Capital Preservation Over Activity**: "Silence is a position." When market conditions are choppy, overbought, or lacking orderbook confluence, the engine purposefully stands down.

---

## 2. System Architecture & Monorepo Structure

```
StarkX QuantEdge Monorepo
├── backend/                        # Python FastAPI backend & algorithmic engine
│   ├── app/                        # Application package
│   │   ├── backtest/               # Causal historical replay simulation harness
│   │   ├── data/                   # Real-time exchange adapters & on-chain data
│   │   │   ├── binance.py          # Binance Spot/Futures REST + klines fetcher
│   │   │   ├── bybit.py            # Bybit market data & depth orderbook adapter
│   │   │   ├── kraken.py           # Kraken spot price feeds
│   │   │   ├── macro.py            # Crypto macro, dominance, and Fear & Greed index
│   │   │   ├── solana.py           # Solana RPC, Raydium/Orca DEX & whale tracker
│   │   │   ├── twelvedata.py       # TwelveData multi-asset fallback adapter
│   │   │   ├── validate.py         # Causal OHLCV validation & anomaly cleaning
│   │   │   └── yahoo.py            # Yahoo Finance adapter for cross-asset feeds
│   │   ├── factors/                # 8-family factor scorers & confluence logic
│   │   │   ├── agreement.py        # Inter-factor directional agreement ratio
│   │   │   ├── scorer.py           # Factor scoring algorithms (-100 to +100)
│   │   │   └── weights.py          # Interval-specific baseline weight matrices
│   │   ├── indicators/             # Pure NumPy/Pandas technical indicators
│   │   │   └── engine.py           # EMA, ATR, ADX, CHOP, BB, UT Bot, Sabres, OU
│   │   ├── llm/                    # Qualitative reasoning debate engine
│   │   │   ├── debate.py           # OpenRouter Bull/Bear/Risk Manager debate
│   │   │   └── fallback.py         # Deterministic offline debate synthesizer
│   │   ├── allocator.py            # Multiplicative Weights (Hedge) strategy allocator
│   │   ├── arb.py                  # Funding carry, triangular & cross-exchange arb
│   │   ├── calibration.py          # Isotonic regression probability calibration & Brier monitor
│   │   ├── config.py               # Pydantic v2 settings & risk thresholds
│   │   ├── costs.py                # Orderbook depth, spread & fee friction modeling
│   │   ├── db.py                   # Thread-safe PostgreSQL connection pool client
│   │   ├── drift.py                # Page-Hinkley cumulative trade drift detection
│   │   ├── execution.py            # Resting maker limit order execution simulator
│   │   ├── flash.py                # Flash Bot high-frequency momentum scalper
│   │   ├── geometry.py             # Volatility-based trade levels (Entry, SL, T1-T3)
│   │   ├── investments.py          # Long-term investment sleeve & thematic assets
│   │   ├── learning.py             # L2 Logistic Regression factor weight learning loop
│   │   ├── main.py                 # FastAPI endpoints, background scheduler, and CORS
│   │   ├── meta_features.py        # Meta-ML 22-dimensional feature vector builder
│   │   ├── meta_model.py           # Meta-labeling model & shadow-to-live gating
│   │   ├── performance.py          # Portfolio P&L, Sharpe, drawdown & equity tracking
│   │   ├── persistence.py          # Signal logging & database query routines
│   │   ├── portfolio.py            # Multi-sleeve portfolio capital partitioner
│   │   ├── price_action.py         # Wick rejection, chart patterns & S/R cluster engine
│   │   ├── psychology.py           # Contrarian positioning overlay (Funding & F&G)
│   │   ├── regime.py               # L1 regime classification & Range-Fade strategy
│   │   ├── resolver.py             # Asynchronous auto-outcome resolver (TP/SL/timeout)
│   │   ├── scanner.py              # Autonomous 4h universe scanner & exposure monitor
│   │   ├── shorts.py               # Bear-market short qualification filter
│   │   ├── signal_service.py       # Core confluence signal pipeline orchestrator
│   │   ├── sizing.py               # Capital-adaptive fractional Kelly & ruin sizing
│   │   └── universe.py             # Asset catalog, liquidity checks & bleeder filters
│   ├── scripts/                    # Test suites, audits, backtests & administration
│   │   ├── deep_trade_analysis.py  # 1,002 trade empirical forensic audit script
│   │   ├── master_200_strategies_audit.py # 200+ strategy backtest audit harness
│   │   ├── test_p0.py              # P0 core math, costs & indicators test suite
│   │   ├── test_p1.py              # P1 calibration, EV & isotonic regression tests
│   │   ├── test_p2_sizing.py       # P2 Kelly, ruin probability & tier sizing tests
│   │   ├── test_gates_live.py      # Real database performance gate validation
│   │   ├── test_price_action.py    # Candlestick anatomy & chart pattern test suite
│   │   ├── test_execution.py       # Limit order maker/taker execution tests
│   │   └── migrate.py              # Database schema migration runner
│   └── requirements.txt            # Python dependencies
├── db/                             # Supabase PostgreSQL relational schema
│   └── migrations/                 # Sequential SQL migration files
└── frontend/                       # Next.js 16 App Router web cockpit
    ├── app/                        # Pages, layouts, and global CSS
    ├── components/                 # Cockpit React UI components
    └── lib/                        # API fetchers, TypeScript types & utilities
```

---

## 3. Empirical Strategy Foundation (1,002 Trade Audit)

The system's production configuration is governed by an empirical audit of **1,002 resolved historical live and paper trades**. Every strategy parameter is backed by measured statistical outcomes:

### 3.1 What Was Eliminated (Proven Loss Drivers)
* **Forex Market Pruning**: 177 trades resulted in a **24.8% win rate** and **-1.48R cumulative bleed**. Every G10 currency pair generated negative expectancy (EUR/USD -0.59R, GBP/USD -0.38R, USD/JPY -0.32R). Forex was permanently removed from automated scanning.
* **Commodities & Indices Paused**: Only 8 historical trades were recorded—insufficient sample size to validate statistical edge. Suspended until 50+ paper trades accumulate.
* **Crypto 1h Core Terminated**: Core swing signals on 1h timeframes yielded negative returns across all market regimes (-0.13R to -0.15R) due to commission drag relative to bar amplitude.
* **Crypto 4h Shorts Suppressed**: 4h crypto shorts in ranging/bullish markets produced a **0.0% win rate** (-0.26R) due to persistent spot dip-buying. Core engine enforces `crypto_long_only = True`.
* **Flash 1h Dip Trigger Killed**: Dip-buying scalps on 1h produced an **8.0% win rate** (-0.22R). Dropped in favor of momentum continuation.

### 3.2 What Was Preserved & Amplified (Proven Alpha)
* **Core Crypto Long 4h**: Generated **+1.08R net profit** across regimes:
  * `weak_trend`: $n=98$, **60.2% WR**, Profit Factor **1.92**, **+0.63R**.
  * `range`: $n=29$, **82.8% WR**, Profit Factor **9.07**, **+0.37R**.
  * `high_vol`: $n=9$, **88.9% WR**, Profit Factor **15.84**, **+0.08R**.
* **Flash Crypto Short 1h Burst**: $n=92$, **76.1% WR**, Profit Factor **1.54**, **+0.11R** (momentum breakdown trades).
* **Flash Crypto Short 15m Burst**: $n=16$, **75.0% WR**, Profit Factor **2.96**, **+0.10R**.
* **Hold Time Optimization**: Trades held **12 to 50 bars** achieved peak expectancy (62%–71% WR, $+0.0025R$ avg). Premature partial booking was increased from 0.40R to **0.60R** to give winners room to reach targets.
* **Bleeder Reclassification**: `FILUSDT` was rehabilitated after audit proved **77.8% WR, +0.09R** across 36 trades. `BTCUSDT` position sizing was dampened by 50% (`symbol_mult = 0.50`) to minimize beta drag.

---

## 4. Trading Engines & Subsystems

```
                                  ┌───────────────────────────┐
                                  │   STARKX QUANTEDGE CORE   │
                                  └─────────────┬─────────────┘
                ┌───────────────────────────────┼───────────────────────────────┐
                ▼                               ▼                               ▼
  ┌───────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────┐
  │     CORE SWING ENGINE     │   │      FLASH SCALPER        │   │     ARBITRAGE COCKPIT     │
  │ • 4h Crypto Longs         │   │ • 1h & 15m Burst/Breakout │   │ • Funding Rate Carry      │
  │ • 8-Family Confluence     │   │ • Tight Maker Execution   │   │ • Triangular Cycle Arb    │
  │ • Range-Fade & Trend      │   │ • CVD & Vol Expansion     │   │ • Cross-Exchange Depth    │
  └───────────────────────────┘   └───────────────────────────┘   └───────────────────────────┘
```

### 4.1 Core Swing Confluence Engine
The primary swing engine (`signal_service.py`, `scanner.py`) executes multi-day trend continuation and range-fade setups on 4h candlestick bars:
* **Scanning Cadence**: Autonomous background sweep every 30 minutes over 50+ top liquid crypto pairs.
* **Directional Discipline**: Hard-enforced `crypto_long_only = True` for core swings.
* **Regime Adaptability**: Automatically transitions between trend-following geometry and mean-reverting range-fade geometry depending on ADX, Choppiness Index, and Ornstein-Uhlenbeck half-life.
* **Safety Bounds**: Hard rejection of stop distances $> 6.0\%$ and sub-penny micro tokens ($< \$0.001$).

### 4.2 Flash Bot Scalping Subsystem
The Flash Bot (`flash.py`) operates as an independent high-frequency opportunity hunter on 15m and 1h intervals:
* **Trigger 1: Momentum Burst (`burst`)**: Detects explosive price thrusts through EMA9 accompanied by volume expansion $\ge 1.10\times$ 20-bar average and positive CVD aggression ($Z \ge 0.35$).
* **Trigger 2: Range Breakout (`breakout`)**: Price pierces 15-bar high/low extremes with expanding volatility.
* **Short Direction Gating**: Shorts are permitted **exclusively** on the `burst` trigger family; all other short setups are rejected.
* **Anti-Chasing Filters**: Rejects entries when price is $> 2.5\%$ extended from VWAP, when RSI $> 68$ (buying tops) or $< 32$ (shorting bottoms), or when BTC 1h is in an opposing structural trend.
* **Concurrency Caps**: Limits active flash trades to a maximum of 3 concurrent positions, and at most 2 in the same direction.

### 4.3 Multi-Strategy Arbitrage Engine
The arbitrage cockpit (`arb.py`) scans for market inefficiencies across centralized exchanges:
1. **Delta-Neutral Funding Rate Carry**: Buys spot and shorts perpetual futures on high-funding assets. Uses an AR(1) time-series model to forecast funding yield over an 8-hour horizon and verifies that yield exceeds 2-leg taker fees plus a safety buffer.
2. **Triangular Cycle Arbitrage**: Models exchange pairs as directed graphs and executes Bellman-Ford negative cycle searches (e.g., USDT $\rightarrow$ BTC $\rightarrow$ ETH $\rightarrow$ USDT) considering taker fees.
3. **Cross-Exchange Orderbook Spreads**: Compares real-time top-of-book bid/ask quotes between Binance and Bybit.

### 4.4 Institutional Portfolio & Thematic Sleeves
The portfolio manager (`portfolio.py`, `investments.py`) allocates capital across four segregated sleeves:
* **Core Swing Sleeve**: $40\%$ target weight.
* **Flash Scalp Sleeve**: $20\%$ target weight.
* **Arbitrage Sleeve**: $15\%$ target weight.
* **Cash Reserve (Dry Powder)**: Minimum $25\%$ floor maintained at all times.

---

## 5. Mathematical Indicator & Price Action Engine

### 5.1 Technical Indicator Engine
Implemented in `indicators/engine.py` using NumPy vectorized operations:

* **Exponential Moving Averages (EMA)**: Calculated for periods 9, 21, 50, and 200.
* **Triple Exponential Moving Average (TEMA)**:
  $$\text{TEMA} = 3 \cdot \text{EMA}_1 - 3 \cdot \text{EMA}_2 + \text{EMA}_3$$
* **Average True Range (ATR)**: Wilder's 14-period smoothing on true range.
* **Bollinger Bands (%B & Bandwidth)**: 20-period SMA with $2\sigma$ standard deviation channels.
* **Trend & Chop Oscillators**: 14-period ADX, +DI/-DI directional indicators, and Choppiness Index (CHOP).
* **UT Bot Trailing Stop**: ATR-based dynamic volatility stop-and-reverse trailing band.
* **LuxAlgo MA Sabres**: Detects inflection points in TEMA trend velocity after prolonged runs.
* **Ornstein-Uhlenbeck (OU) Mean-Reversion Half-Life**:
  Fits an AR(1) continuous mean-reverting process on residuals $x_t = P_t - \text{EMA}_{21}(P_t)$:
  $$\Delta x_t = -\lambda x_{t-1} + \epsilon_t \implies t_{half} = \frac{\ln(2)}{\lambda}$$
  Ensures range-fades are only initiated when mean reversion occurs rapidly ($t_{half} \le 24$ bars).

### 5.2 Price Action & Candle Structure Engine
Implemented in `price_action.py` to provide candlestick anatomy and structural clearance checks:

```
    Upper Rejection Wick (Bearish)
          │   ┌──────┐  <- Upper Candle Body
          └───┤      │
              │      │  <- Candle Body
          ┌───┤      │
          │   └──────┘  <- Lower Candle Body
          │
    Lower Rejection Wick (Bullish)
```

1. **Candle Anatomy Diagnosis**:
   - Computes upper wick ratio $\frac{H - \max(O, C)}{H - L}$ and lower wick ratio $\frac{\min(O, C) - L}{H - L}$.
   - Detects shooting stars (bearish rejection $> 50\%$ upper wick) and hammers (bullish absorption $> 50\%$ lower wick).
2. **Multi-Candle Pattern Recognition**:
   - Identifies Bullish/Bearish Engulfing, Inside Bars, Double Tops/Bottoms, and Liquidity Sweeps (stop hunts).
3. **Dynamic Support & Resistance (S/R) Clustering**:
   - Identifies swing pivots and groups price levels into volatility-based support and resistance bands.
4. **Pre-Trade Clearance Gate**:
   - Longs are blocked if an opposing resistance cluster exists within $0.50\times \text{ATR}$ or if the previous candle printed a heavy bearish upper rejection wick.
   - Shorts are blocked if support sits within $0.50\times \text{ATR}$ or a bullish absorption wick is detected.

---

## 6. 8-Family Factor Confluence Pipeline

Primary signals pass through 8 independent evidence families (`factors/scorer.py`), each generating a normalized score in $[-100.0, +100.0]$:

| Factor Family | Core Inputs & Signals | Weight (4h Core) |
|---|---|:---:|
| **F1: Trend** | EMA 9/21/50/200 stack alignment, TEMA slope, UT Bot position state, LuxAlgo flip | 0.22 |
| **F2: Momentum** | 14-period RSI, Stochastic %K, MACD histogram normalized to ATR | 0.18 |
| **F3: Volatility** | Bollinger Band %B position, Bandwidth expansion/compression ratio | 0.12 |
| **F4: Structure** | Distance to nearest DBSCAN S/R pivot, 50-bar Fibonacci retracement levels | 0.14 |
| **F5: Order Flow** | Cumulative Volume Delta (CVD) Z-score, bid/ask orderbook imbalance, funding rate Z-score | 0.14 |
| **F6: Sentiment** | Alternative.me Crypto Fear & Greed Z-score, curated crypto news sentiment | 0.08 |
| **F7: Macro** | BTC/ETH market dominance metrics, cross-asset macro trend momentum | 0.06 |
| **F8: Consensus** | Higher timeframe (HTF) trend alignment, cross-oscillator agreement | 0.06 |

### Confluence Score & Agreement Scaling
1. Active weights are re-normalized across available factor families: $w_i' = \frac{w_i}{\sum w_k}$.
2. Raw weighted confluence score is computed: $R_{raw} = \sum w_i' \cdot S_i$.
3. Directional agreement ratio ($A$) measures consensus:
   $$A = \frac{\text{Count of active families sharing the sign of } R_{raw}}{\text{Total active families}}$$
4. Final Composite Score is scaled by agreement to prevent single-factor distortion:
   $$\text{Composite} = \text{Clip}_{-100, 100}\left( R_{raw} \cdot (0.50 + 0.50 \cdot A) \right)$$
5. Action Labels:
   * $\text{Composite} \ge +60.0 \implies$ **Strong Buy**
   * $+20.0 \le \text{Composite} < +60.0 \implies$ **Buy**
   * $-20.0 < \text{Composite} < +20.0 \implies$ **Neutral**
   * $-60.0 < \text{Composite} \le -20.0 \implies$ **Sell**
   * $\text{Composite} \le -60.0 \implies$ **Strong Sell**

---

## 7. Risk Engineering & Capital-Adaptive Sizing

### 7.1 Quarter-Kelly & Ruin Risk Formulation
Implemented in `sizing.py`. Position sizing balances optimal logarithmic wealth growth with strict survival constraints:

$$\text{Quarter-Kelly Fraction: } f_k = \frac{\max\left(0, \, p - \frac{1 - p}{R}\right)}{4}$$

To prevent catastrophic account drawdown, the system solves the continuous gambler's ruin equation for drawdown tolerance $D = 0.50$ (50% account drawdown) and ruin probability $\alpha = 0.05$ (5% risk of ruin):

$$\text{Ruin Fraction: } f_{ruin} = \text{Solve}\left( P(\text{Drawdown} \ge D) \le \alpha \right)$$

$$\text{Final Risk Fraction } f = \min(f_k, \, f_{ruin}, \, \text{Tier Risk Cap}) \times \text{Drift Mult} \times \text{Alloc Mult} \times \text{Symbol Mult}$$

* **Account Tiers**:
  * **Micro** ($<\$100$): Risk cap $2.0\%$, EV floor $+0.20R$, max concurrent 2.
  * **Small** ($\$100 - \$1,000$): Risk cap $2.0\%$, EV floor $+0.10R$, max concurrent 8.
  * **Standard** ($\$1,000 - \$10,000$): Risk cap $2.0\%$, EV floor $+0.05R$, max concurrent 20.
  * **Growth** ($>\$10,000$): Risk cap $1.5\%$, EV floor $+0.05R$, max concurrent 30.

### 7.2 Exposure Budgets, Gap-Weighting & Total Heat
* **Gross Exposure Ceiling**: Total notional exposure is capped at $2.0\times$ to $4.0\times$ equity depending on tier.
* **Gap-Risk Weighting**: Assets are weighted by gap propensity ($\text{Crypto} = 1.0\times$, $\text{Commodities} = 0.65\times$, $\text{Indices} = 0.50\times$).
* **Total Portfolio Heat**: Defined as the total percentage of equity lost if all open positions stop out simultaneously:
  $$\text{Heat} = \sum_{\text{open}} \frac{\text{Risk USD}_i}{\text{Equity}} \le \text{Max Heat (4\%--6\%)}$$
* **Symbol Dampening**: High-beta or marginal performers (`BTCUSDT`) receive a 50% sizing multiplier (`symbol_mult = 0.50`).

### 7.3 Self-Protecting Circuit Breakers & Drift Detection
* **Page-Hinkley Drift Detector (`drift.py`)**: Tracks cumulative trade performance residuals $m_t = R_t - \bar{R}$. When cumulative negative drift exceeds threshold $U_t - T_t > \lambda$, the system flags regime drift, automatically raises the EV floor to $+0.40R$, and cuts position sizing by $50\%$.
* **Global Circuit Breaker**: If realized returns drop below $-3.0R$ over a rolling 24-hour window, all scanning and signal emission halts for 24 hours.
* **Rolling Performance Gates**: Automatically silences symbols, directions, or regimes that produce negative realized returns over rolling 14- to 30-day windows.

---

## 8. Machine Learning & Self-Improving Feedback Loop

```
                               ┌───────────────────────────┐
                               │ 1. RESOLVER (resolver.py) │
                               │ Evaluates TP/SL Outcomes  │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │ 2. CALIBRATION & ISOTONIC │
                               │ Maps Composite -> Win Prob│
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │ 3. META-ML CLASSIFIER     │
                               │ Shadow Gating & Filtering │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │ 4. L2 WEIGHT OPTIMIZER    │
                               │ Champion/Challenger Tests │
                               └───────────────────────────┘
```

### 8.1 Isotonic Probability Calibration
Raw model confidence ratings frequently exhibit overconfidence. The calibration engine (`calibration.py`) fits a **Pool Adjacent Violators Algorithm (PAVA)** monotonic isotonic regression mapping composite scores directly to empirical win probabilities conditioned on market and direction:
$$p = \text{IsotonicFit}(\text{Composite} \mid \text{Market}, \text{Direction})$$
Rolling calibration accuracy is continuously audited using the **Brier Score**:
$$\text{Brier} = \frac{1}{N}\sum_{i=1}^{N} (p_i - y_i)^2$$

### 8.2 Meta-Labeling Random Forest / Logistic Regression
Implemented in `meta_model.py` and `meta_features.py`. A secondary classifier trains on a 22-dimensional feature vector (regimes, factor scores, volatility ratios, funding rate Z-scores, agreement ratios) to predict the probability that a generated trade signal will achieve its target before stopping out. Operates in shadow mode until out-of-sample AUC-ROC exceeds primary baseline calibration.

### 8.3 L2 Regularized Online Weight Optimizer
Implemented in `learning.py`. Periodically fits an L2-regularized logistic regression over historical factor score logs and realized trade outcomes:
$$\min_{\mathbf{w}} \sum_{i=1}^{N} \mathcal{L}(y_i, \, \mathbf{w}^T \mathbf{x}_i) + \lambda \|\mathbf{w}\|_2^2$$
Learned weights are tested via walk-forward out-of-sample replay. If a Challenger weight profile outperforms the active Champion profile across a holdout basket, it is automatically promoted in PostgreSQL.

### 8.4 Asynchronous Outcome Resolver
Implemented in `resolver.py`. Executes continuously as an asynchronous background worker polling completed candles to track open signals:
* **Target Resolution**: Evaluates high/low touches against Target 1 ($T_1$) and partial booking levels.
* **Stop Resolution**: Evaluates adverse candle wicks against Stop Loss ($SL$).
* **Timeout Resolution**: Signals that do not hit target or stop within 48 bars are closed at market close to free capital.

---

## 9. Execution Economics & Order Routing

Implemented in `execution.py` and `costs.py`. StarkX QuantEdge explicitly models the friction differential between taker and maker execution:

* **Maker Advantage**: Crossing the orderbook spread via taker market orders incurs fees of $0.16\%$--$0.28\%$ per round trip. Resting maker limit orders pay $\sim 0.04\%$ round trip (+0.34 percentage points net P&L advantage per trade).
* **Resting Limit Geometry**:
  * Long limit orders rest at $\text{Entry} = \text{Close} - 0.15 \times \text{ATR}$.
  * Short limit orders rest at $\text{Entry} = \text{Close} + 0.15 \times \text{ATR}$.
* **Adverse Selection Modeling**: Simulates limit order fill rates. If price runs away without pulling back to fill the resting order within 2 bars, the order expires unfilled and contributes zero P&L rather than assuming fantasy fills.

---

## 10. Multi-Agent Qualitative AI Debate System

When an active confluence setup is identified, the system can dispatch structured technical context to OpenRouter (`llm/debate.py`) to execute a 3-agent qualitative narrative debate:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. BULL ANALYST AGENT                                                  │
│ Argues bullish thesis using factor strengths, order flow & support.    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. BEAR ANALYST AGENT                                                  │
│ Challenges the setup, highlights overhead resistance & macro risks.    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. RISK MANAGER JUDGE AGENT                                            │
│ Delivers structured JSON verdict: { agreement, conviction, risks }     │
└────────────────────────────────────────────────────────────────────────┘
```

* **Penalty Adjustment**:
  $$\text{Final Confidence} = \text{Round}\Big( (0.50 \cdot \text{Model Conf} + 0.50 \cdot \text{AI Conviction}) \times \text{Penalty} \Big)$$
  where $\text{Penalty} = 1.00$ (Agree), $0.85$ (Caution), $0.60$ (Disagree).
* **Deterministic Fallback Engine (`llm/fallback.py`)**: If external AI APIs are disabled, unreachable, or unconfigured, an internal mathematical debate generator synthesizes debate narratives directly from factor scores.

---

## 11. Solana On-Chain Intelligence Engine

Implemented in `data/solana.py`. Provides direct integration with Solana RPC nodes, Raydium, and Orca DEX protocols:
* **Whale Wallet Profiling**: Monitors high-net-worth wallet accumulation and distribution flows.
* **DEX Liquidity Verification**: Audits liquidity pool depth, LP token burn/lock verification, and token mint authority status before evaluating decentralized altcoin setups.
* **On-Chain Volume Acceleration**: Measures taker volume spikes on decentralized automated market makers (AMMs).

---

## 12. Database Schema & Relational Architecture

StarkX QuantEdge utilizes **PostgreSQL (Supabase)** with the following relational schema:

```
  ┌──────────────────┐       1:N       ┌──────────────────┐
  │     signals      ├────────────────►│     outcomes     │
  └────────┬─────────┘                 └──────────────────┘
           │
           │ 1:1
           ▼
  ┌──────────────────┐
  │   factor_logs    │
  └──────────────────┘
```

### Table Definitions

#### `signals`
Stores every evaluated signal emitted by the core confluence or flash engine:
```sql
CREATE TABLE signals (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    market TEXT DEFAULT 'crypto',
    strategy TEXT DEFAULT 'core',
    as_of TIMESTAMPTZ NOT NULL,
    label TEXT NOT NULL,
    composite NUMERIC NOT NULL,
    confidence NUMERIC NOT NULL,
    regime TEXT NOT NULL,
    price NUMERIC NOT NULL,
    atr NUMERIC NOT NULL,
    entry NUMERIC,
    stop NUMERIC,
    target NUMERIC,
    partial_target NUMERIC,
    reward_risk NUMERIC,
    win_prob NUMERIC,
    ev_r NUMERIC,
    meta_p NUMERIC,
    agreement TEXT,
    conviction NUMERIC,
    final_confidence NUMERIC,
    rationale TEXT,
    shadow BOOLEAN DEFAULT FALSE,
    features JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `outcomes`
Stores resolved trade executions, realized P&L, and price excursions:
```sql
CREATE TABLE outcomes (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES signals(id) ON DELETE CASCADE,
    result TEXT NOT NULL,            -- 'target', 'stop', 'trailing_stop', 'timeout', 'unfilled'
    pnl NUMERIC NOT NULL,               -- Realized percentage return (e.g. +1.85% or -1.05%)
    mfe NUMERIC,                        -- Maximum Favorable Excursion
    mae NUMERIC,                        -- Maximum Adverse Excursion
    bars_held INTEGER,                  -- Candle duration from entry to exit
    resolved_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `factor_logs`
Stores raw factor family scores per signal for ML training:
```sql
CREATE TABLE factor_logs (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES signals(id) ON DELETE CASCADE,
    trend NUMERIC, momentum NUMERIC, volatility NUMERIC, structure NUMERIC,
    flow NUMERIC, sentiment NUMERIC, macro NUMERIC, consensus NUMERIC
);
```

#### `regime_weights`
Stores active champion factor weights per market regime:
```sql
CREATE TABLE regime_weights (
    id BIGSERIAL PRIMARY KEY,
    regime TEXT NOT NULL,
    interval TEXT NOT NULL,
    weights JSONB NOT NULL,
    is_champion BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `arb_opportunities`
Stores detected delta-neutral funding carry and triangular cycles:
```sql
CREATE TABLE arb_opportunities (
    id BIGSERIAL PRIMARY KEY,
    arb_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    net_ev NUMERIC NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 13. Complete FastAPI REST API Reference

The backend exposes an interactive OpenAPI documentation endpoint at `/docs`.

| Method | Endpoint | Query / Body Parameters | Description |
|:---:|:---|:---|:---|
| `GET` | `/health` | None | Returns backend status, environment, version, and database connection state |
| `GET` | `/signal` | `symbol`, `interval`, `market`, `limit`, `with_flow` | Computes full deterministic factor scores, levels, and regime for asset |
| `GET` | `/explain` | `symbol`, `interval`, `market`, `limit` | Computes signal + qualitative LLM narrative synthesis |
| `GET` | `/decision` | `symbol`, `interval`, `market`, `limit` | Full decision pipeline: Factor Confluence + AI Multi-Agent Debate + Logging |
| `GET` | `/candles` | `symbol`, `interval`, `market`, `limit` | Returns validated OHLCV candlestick bars for frontend charting |
| `GET` | `/scan` | `min_confidence` | Executes an on-demand sweep across the 4h watchlist |
| `POST`| `/resolve` | `max_signals` | Manually triggers the asynchronous outcome resolver over open signals |
| `GET` | `/flash/scan` | `log` (bool) | Sweeps the high-frequency flash universe (15m/1h) for burst setups |
| `GET` | `/flash/stats`| `window_days` | Returns rolling Flash Bot performance, hit rate, and P&L metrics |
| `GET` | `/performance`| `trade_size` | Returns paper trading portfolio metrics, Sharpe ratio, and floating P&L |
| `GET` | `/trades` | `result`, `limit`, `offset` | Returns paginated list of closed historical trades |
| `GET` | `/trade` | `id` | Fetches comprehensive details for a specific signal and its outcome |
| `GET` | `/learning/status` | None | Returns active champion factor weights and ML learning state |
| `POST`| `/learning/train` | None | Triggers factor weight retraining and walk-forward challenger gating |
| `POST`| `/meta/train` | None | Trains secondary Meta-ML model and checks shadow-to-live promotion |
| `POST`| `/arb/funding-scan` | None | Executes delta-neutral funding rate carry arbitrage sweep |
| `POST`| `/arb/triangular-scan` | None | Executes triangular currency cycle arbitrage sweep |
| `GET` | `/arb/opportunities` | `limit` | Fetches active positive-EV arbitrage opportunities |
| `POST`| `/webhook/tradingview` | Header: `x-signature` | HMAC-authenticated webhook endpoint for external Pine Script alerts |

---

## 14. Frontend Cockpit Architecture

The user interface (`/frontend`) is built with **Next.js 16 (App Router)**, **React 19**, **TypeScript**, and **Tailwind CSS**, designed with an ultra-responsive dark-mode glassmorphism visual aesthetic:

1. **Trading Terminal (`page.tsx`, `SignalCard.tsx`)**: Displays composite scores, confidence dials, price levels (Entry, SL, $T_1$--$T_3$), calibrated win probabilities, and EV estimates.
2. **Interactive Financial Chart (`PriceChart.tsx`)**: High-performance TradingView Canvas charting via `lightweight-charts`. Features candlestick rendering, volume bars, EMA overlays (9, 21, 50, 200), UT Bot trailing stops, LuxAlgo reversal markers, and DBSCAN S/R zones.
3. **8-Family Confluence Matrix (`FactorBar.tsx`)**: Visual breakdown of individual factor scores ($-100$ to $+100$) with color-coded gradients.
4. **AI Debate Viewer (`DebatePanel.tsx`)**: Side-by-side terminal displaying Bull Analyst thesis, Bear Analyst rebuttal, Risk Manager verdict, and conviction penalty.
5. **Watchlist Scanner (`ScannerPanel.tsx`)**: Live table tracking continuously scanned assets, status flags, and signal alerts.
6. **Portfolio Performance & Equity Curve (`PerformancePanel.tsx`, `EquityCurve.tsx`)**: Real-time equity curve visualization, drawdown metrics, profit factor, and closed trade distribution.
7. **Arbitrage Cockpit (`ArbPanel.tsx`)**: Displays positive-EV funding carry opportunities, cross-exchange spreads, and triangular cycles.

---

## 15. Verification, Audit & Research Suite

The `/backend/scripts/` directory includes an exhaustive suite of diagnostic, backtesting, and validation scripts:

```powershell
# Set Python path to backend root
$env:PYTHONPATH="."

# Execute core unit test suites
& ".venv/Scripts/python.exe" scripts/test_p0.py            # Costs, OHLCV validation, indicators
& ".venv/Scripts/python.exe" scripts/test_p1.py            # Isotonic calibration, EV math
& ".venv/Scripts/python.exe" scripts/test_p2_sizing.py     # Quarter-Kelly, ruin probability, tiers
& ".venv/Scripts/python.exe" scripts/test_gates_live.py    # Database performance gates validation
& ".venv/Scripts/python.exe" scripts/test_price_action.py  # Candlestick anatomy, patterns, S/R
& ".venv/Scripts/python.exe" scripts/test_execution.py     # Limit order maker/taker execution

# Execute deep forensic trade analysis
& ".venv/Scripts/python.exe" scripts/deep_trade_analysis.py

# Execute 200+ multi-strategy backtest audit
& ".venv/Scripts/python.exe" scripts/master_200_strategies_audit.py
```

---

## 16. Configuration & Environment Reference

### Backend `.env` (`backend/.env`)

```env
# Server & Security
APP_ENV=production
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://your-domain.com
TRADINGVIEW_WEBHOOK_SECRET=your-secure-webhook-secret

# Database (Supabase PostgreSQL)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-supabase-publishable-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
DATABASE_URL=postgresql://postgres.xxx:password@aws-0-region.pooler.supabase.com:6543/postgres

# Qualitative LLM Debate (OpenRouter)
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL_STRONG=openrouter/auto
OPENROUTER_MODEL_CHEAP=openai/gpt-4o-mini

# Market Data Adapters
TWELVEDATA_API_KEY=your-twelvedata-api-key
NEWSAPI_KEY=your-newsapi-key
COINMARKETCAP_API_KEY=your-coinmarketcap-api-key
HELIUS_API_KEY=your-solana-helius-key

# Risk Management & Strategy Settings
ACCOUNT_EQUITY_USD=1000.0
RISK_PER_TRADE_PCT=0.75
CRYPTO_LONG_ONLY=true
PARTIAL_BOOK_AT_R=0.60
PARTIAL_BOOK_FRACTION=0.35
EV_GATE_ENABLED=true
MIN_EV_R=0.0
DRIFT_ENABLED=true
CIRCUIT_BREAKER_ENABLED=true

# Flash Bot Settings
FLASH_ENABLED=true
FLASH_PAPER_MODE=true
FLASH_LONG_ONLY=false
FLASH_STOP_ATR=1.25
FLASH_RR=2.0
FLASH_MIN_CVD_Z=0.35
FLASH_LIMIT_OFFSET_ATR=0.15
FLASH_PARTIAL_BOOK_AT_R=1.25

# Autonomous Background Workers
SCANNER_ENABLED=true
SCANNER_INTERVAL_MINUTES=30
RESOLVER_ENABLED=true
RESOLVER_INTERVAL_MINUTES=15
```

### Frontend `.env.local` (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

---

## 17. Installation, Development & Production Deployment

### 17.1 Local Development Setup

#### Prerequisites
* **Python 3.10+** (Python 3.11 recommended)
* **Node.js 18+** & **npm**
* **PostgreSQL 15+** or active **Supabase** instance

#### 1. Backend Setup
```bash
# Clone the repository
git clone https://github.com/thenewera0/StarkXQuantEdge.git
cd StarkXQuantEdge/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Apply database migrations
python -m scripts.migrate

# Start FastAPI development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Backend API will be active at `http://127.0.0.1:8000`.

#### 2. Frontend Setup
```bash
cd ../frontend

# Install dependencies
npm install

# Configure environment variables
cp .env.local.example .env.local

# Start Next.js development server
npm run dev
```
Frontend Cockpit will be active at `http://localhost:3000`.

---

### 17.2 Production Deployment

#### Backend Deployment (Docker / Render)
A production `Dockerfile` is provided in the project root:

```bash
# Build Docker image
docker build -t starkx-quantedge-backend -f backend/Dockerfile .

# Run container
docker run -d -p 8000:8000 --env-file backend/.env --name quantedge-backend starkx-quantedge-backend
```

For **Render**, connect the GitHub repository and specify:
* **Environment**: `Python 3`
* **Build Command**: `pip install -r backend/requirements.txt`
* **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`

#### Frontend Deployment (Vercel)
Deploy the `/frontend` directory directly to Vercel:
1. Set Root Directory to `frontend`.
2. Configure Environment Variable: `NEXT_PUBLIC_API_BASE = https://your-backend-api.onrender.com`.
3. Deploy.

---

## License & Intellectual Property

StarkX QuantEdge is proprietary algorithmic trading software. All rights reserved. Code, architecture, and mathematical models are protected under proprietary licensing.
