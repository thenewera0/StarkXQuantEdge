# StarkX QuantEdge — Autonomous AI Crypto & Forex Confluence Engine & Arbitrage Cockpit

**StarkX QuantEdge** is an enterprise-grade, multi-market autonomous quantitative trading decision-support cockpit and execution engine. It combines pure deterministic mathematical indicator calculations, an 8-family factor confluence engine, machine-learning probability calibration, multi-agent AI narrative debates, capital-adaptive position sizing, walk-forward strategy optimization, and real-time arbitrage detection across crypto and forex markets.

---

## Key Architectural Principles

1. **Deterministic Python Mathematical Foundation**: Every price level, technical indicator, factor score, stop-loss/take-profit level, and mathematical feature is computed deterministically in Python using NumPy and Pandas. The LLM **never** invents prices or numbers; it only synthesizes rationale and debate arguments over structured data.
2. **Causal Zero-Lookahead Engineering**: All indicators, strategy signals, and backtesting replays strictly adhere to temporal causality. Decisions made at bar $t$ use data up to bar $t-1$ or the closed bar $t$.
3. **Multi-Layer Self-Improving Safety Infrastructure**: Features an Isotonic Probability Calibration engine, Page-Hinkley Strategy Drift Detection, Global Circuit Breakers, Multi-Tier Performance Gates (Regime, Direction, Symbol), and Meta-ML Shadow Gating to protect capital in changing market regimes.

---

## 1. System Technology Stack & Architecture

StarkX QuantEdge is structured as a production monorepo partitioned into three primary directories: `/backend` (Python FastAPI), `/frontend` (Next.js 16), and `/db` (Supabase PostgreSQL migrations).

```
StarkX QuantEdge Monorepo Structure
├── backend/                        # Python FastAPI server, trading engine, ML & AI core
│   ├── app/                        # Primary application package
│   │   ├── backtest/               # Causal replay simulation harness & walk-forward engine
│   │   ├── data/                   # Multi-exchange & macro data adapters (Binance, Bybit, Kraken, TwelveData, etc.)
│   │   ├── factors/                # 8-family factor scoring, weights, and agreement scaling
│   │   ├── indicators/             # Pure-Python mathematical indicator engine (UT Bot, Sabres, OU, etc.)
│   │   ├── llm/                    # OpenRouter AI debate agents (Bull, Bear, Risk Manager) & fallback engine
│   │   ├── allocator.py            # Multiplicative Weights (Hedge) strategy allocator
│   │   ├── arb.py                  # Multi-strategy arbitrage engine (Funding Carry, Triangular, Cross-Exchange)
│   │   ├── calibration.py          # Isotonic regression probability calibration & Brier monitor
│   │   ├── config.py               # Pydantic environment configuration & risk limits
│   │   ├── costs.py                # Orderbook depth, spread, and taker fee friction modeling
│   │   ├── db.py                   # Psycopg2 PostgreSQL connection pool client
│   │   ├── drift.py                # Page-Hinkley strategy drift detection & automatic de-risking
│   │   ├── geometry.py             # Volatility-based trade geometry (Entry, Stop Loss, Targets 1-3)
│   │   ├── learning.py             # L2 Logistic Regression factor weight optimizer & Champion/Challenger gating
│   │   ├── main.py                 # FastAPI application routes, CORS, exception handlers & background scheduler
│   │   ├── meta_features.py        # Meta-ML feature extractor
│   │   ├── meta_model.py           # Meta-labeling model (Random Forest / Logistic Regression) & Shadow Gating
│   │   ├── performance.py          # Paper trading portfolio P&L tracker & metrics engine
│   │   ├── persistence.py          # Signal logging, outcome queries, and scoreboard persistence
│   │   ├── psychology.py           # Contrarian sentiment overlay (Funding rates, Fear & Greed)
│   │   ├── regime.py               # Layer 1 regime detection (Trend, Range, High Vol, Squeeze) & Range-Fade strategy
│   │   ├── resolver.py             # Asynchronous auto-outcome resolver (TP/SL/Timeout tracking)
│   │   ├── scanner.py              # Autonomous multi-asset watchlist scanner
│   │   ├── signal_service.py       # Core signal compute pipeline & candle provider
│   │   └── sizing.py               # Capital-adaptive fractional Kelly & ruin-risk position sizing
│   ├── scripts/                    # CLI administration, backtest runners, audit utilities, and test suites
│   └── requirements.txt            # Python dependencies
├── db/                             # Supabase PostgreSQL relational schema
│   └── migrations/                 # Sequential SQL migration files
└── frontend/                       # Next.js 16 web application
    ├── app/                        # App Router pages & global styles
    ├── components/                 # React UI components (Charts, Signals, Debates, Scanner, Arb, Performance)
    └── lib/                        # Client-side API fetchers & TypeScript definitions
```

### Dependency & Framework Stack
* **Backend Core**: `Python 3.10+`, `FastAPI` (ASGI framework), `Uvicorn` (server worker), `APScheduler` (in-process background task scheduler).
* **Data Science & ML**: `NumPy`, `Pandas`, `Scikit-Learn` (Logistic Regression, Isotonic Regression, Random Forest), `SciPy` (Ornstein-Uhlenbeck estimation).
* **Database Client**: `Psycopg2-binary` for thread-safe PostgreSQL connection pooling to Supabase.
* **Frontend Application**: `Next.js 16` (App Router), `React 19`, `TypeScript`.
* **Styling & UI**: `Tailwind CSS 3`, `Lucide React` (micro-icons), custom dark-mode glassmorphism design system.
* **Data Visualization**: `Lightweight-Charts` (TradingView Canvas wrapper for financial charting), custom SVG/Canvas equity curves.

---

## 2. Database Schema & Relational Architecture

The system utilizes **Supabase (PostgreSQL 15+)** for persistent state management, signal logging, trade outcome resolution, and machine learning training feedback loops.

### Table Summary

#### 1. `watchlist`
Stores monitored market assets and timeframes continuously scanned by the background scanner.
* `id`: bigint (Primary Key, Identity)
* `symbol`: text (e.g. `'BTCUSDT'`, `'ETHUSDT'`, `'EUR/USD'`)
* `interval`: text (e.g. `'15m'`, `'1h'`, `'4h'`, `'1d'`)
* `market`: text (e.g. `'crypto'`, `'forex'`)
* `active`: boolean (default `true`)
* `created_at`: timestamptz
* *Constraints*: `UNIQUE(symbol, interval)`

#### 2. `signals`
Logs every signal evaluated or emitted by the confluence engine.
* `id`: bigint (Primary Key, Identity)
* `symbol`: text, `interval`: text, `market`: text
* `as_of`: timestamptz (Timestamp of candle close)
* `label`: text (`'Strong Sell'`, `'Sell'`, `'Neutral'`, `'Buy'`, `'Strong Buy'`)
* `composite`: numeric (Raw weighted composite score: $-100.0$ to $+100.0$)
* `confidence`: numeric (Raw model confidence rating: $0$ to $100$)
* `regime`: text (`'trend'`, `'range'`, `'high_vol'`, `'squeeze'`)
* `price`: numeric, `atr`: numeric
* `rationale`: text (Synthesized LLM narrative explanation)
* `entry`: numeric (Entry price accounting for slippage)
* `stop`: numeric (Volatility-adjusted stop loss)
* `target`: numeric (Primary Take-Profit target $T_1$)
* `agreement`: text (`'agree'`, `'caution'`, `'disagree'`)
* `conviction`: numeric (Risk Manager AI conviction score: $0$ to $100$)
* `final_confidence`: numeric (Blended confidence adjusted for LLM agreement)
* `debate_source`: text (`'openrouter'` or `'fallback'`)
* `meta_prob`: numeric (Meta-ML predicted win probability $P_{meta}$)
* `ev_r`: numeric (Calibrated Expected Value in terms of R)
* `recommended_size_usd`: numeric (Capital-adaptive position size in USD)
* `created_at`: timestamptz

#### 3. `factor_logs`
Logs individual factor family scores per signal to supply training datasets for ML weight optimization.
* `id`: bigint (Primary Key, Identity)
* `signal_id`: bigint (Foreign Key `signals.id` ON DELETE CASCADE)
* `trend`, `momentum`, `volatility`, `structure`, `flow`, `sentiment`, `macro`, `consensus`: numeric (Individual scores: $-100.0$ to $+100.0$)

#### 4. `outcomes`
Tracks the exact execution result of each trade signal after historical replay or live auto-resolution.
* `id`: bigint (Primary Key, Identity)
* `signal_id`: bigint (Foreign Key `signals.id` ON DELETE CASCADE)
* `resolved_at`: timestamptz
* `result`: text (`'target'`, `'stop'`, `'timeout'`, or `'manual'`)
* `pnl`: numeric (Calculated net return percentage after fees and slippage)
* `mfe`: numeric (Maximum Favorable Excursion as fraction of entry price)
* `mae`: numeric (Maximum Adverse Excursion as fraction of entry price)
* `bars_held`: integer (Duration of trade in candlestick bars)

#### 5. `regime_weights`
Stores active champion factor weights per market regime and interval tier.
* `id`: bigint (Primary Key, Identity)
* `regime`: text (`'trend'`, `'range'`, `'high_vol'`, `'squeeze'`)
* `interval`: text (`'intraday'`, `'short'`, `'swing'`, `'long'`)
* `weights`: jsonb (Key-value mapping of factor family weights)
* `is_champion`: boolean
* `created_at`: timestamptz

#### 6. `meta_models`
Stores metadata and version tracking for the secondary Meta-ML classifier.
* `id`: bigint (Primary Key, Identity)
* `model_version`: text, `status`: text (`'shadow'` or `'promoted'`)
* `auc_score`: numeric, `brier_score`: numeric, `sample_count`: integer
* `model_binary`: bytea / jsonb
* `created_at`: timestamptz

#### 7. `arb_opportunities`
Logs detected positive-EV arbitrage opportunities across funding carry, triangular cycles, and cross-exchange spreads.
* `id`: bigint (Primary Key, Identity)
* `arb_type`: text (`'funding_carry'`, `'triangular'`, `'cross_exchange'`)
* `symbol`: text
* `net_ev`: numeric (Net expected value percentage after fees)
* `details`: jsonb (Leg details, rates, prices, estimated fee burden)
* `created_at`: timestamptz

---

## 3. Mathematical Indicator Engine (`indicators/engine.py`)

The indicator engine calculates all technical metrics in pure NumPy/Pandas with strict causality guarantees.

### 1. Moving Averages & Trend Metrics
* **Exponential Moving Average (EMA)**:
  $$\text{EMA}_t = \alpha \cdot P_t + (1 - \alpha) \cdot \text{EMA}_{t-1}, \quad \alpha = \frac{2}{N + 1}$$
* **Triple Exponential Moving Average (TEMA)**:
  $$\text{TEMA}_t = 3 \cdot \text{EMA}_1(P_t) - 3 \cdot \text{EMA}_2(\text{EMA}_1(P_t)) + \text{EMA}_3(\text{EMA}_2(\text{EMA}_1(P_t)))$$

### 2. Volatility & Channel Indicators
* **Average True Range (ATR)** (Wilder's Smoothing):
  $$\text{TR}_t = \max \left( (H_t - L_t), \, |H_t - C_{t-1}|, \, |L_t - C_{t-1}| \right)$$
  $$\text{ATR}_t = \text{EMA}\left(\text{TR}, \, \alpha = \frac{1}{14}\right)$$
* **Bollinger Bands (%B)**:
  $$\text{Upper}_t = \text{SMA}_{20}(C) + 2 \cdot \sigma_{20}(C), \quad \text{Lower}_t = \text{SMA}_{20}(C) - 2 \cdot \sigma_{20}(C)$$
  $$\%B_t = \frac{C_t - \text{Lower}_t}{\text{Upper}_t - \text{Lower}_t}$$

### 3. Regime & Trend Strength Indicators
* **Average Directional Index (ADX)**:
  $$+DM_t = (H_t - H_{t-1}) \quad \text{if } (H_t - H_{t-1}) > (L_{t-1} - L_t) \text{ and } (H_t - H_{t-1}) > 0 \text{ else } 0$$
  $$-DM_t = (L_{t-1} - L_t) \quad \text{if } (L_{t-1} - L_t) > (H_t - H_{t-1}) \text{ and } (L_{t-1} - L_t) > 0 \text{ else } 0$$
  $$+DI_t = 100 \cdot \frac{\text{EMA}(+DM)}{\text{ATR}_t}, \quad -DI_t = 100 \cdot \frac{\text{EMA}(-DM)}{\text{ATR}_t}$$
  $$\text{DX}_t = 100 \cdot \frac{|+DI_t - -DI_t|}{+DI_t + -DI_t}, \quad \text{ADX}_t = \text{EMA}(\text{DX}, 14)$$
* **Choppiness Index (CHOP)**:
  $$\text{CHOP}_t = 100 \cdot \frac{\log_{10} \left( \sum_{i=0}^{13} \text{TR}_{t-i} \right) - \log_{10}\left( \max(H_{t-13 \dots t}) - \min(L_{t-13 \dots t}) \right)}{\log_{10}(14)}$$

### 4. Custom Pine Script Ports & Structural Indicators
* **UT Bot Trailing Stop & Position State**:
  1. $\text{Loss}_t = \text{Multiplier} \times \text{ATR}_{10, t}$
  2. If $C_t > \text{Stop}_{t-1}$ and $C_{t-1} > \text{Stop}_{t-1}$: $\text{Stop}_t = \max(\text{Stop}_{t-1}, C_t - \text{Loss}_t)$
  3. If $C_t < \text{Stop}_{t-1}$ and $C_{t-1} < \text{Stop}_{t-1}$: $\text{Stop}_t = \min(\text{Stop}_{t-1}, C_t + \text{Loss}_t)$
  4. If $C_t$ crosses above $\text{Stop}_{t-1}$: $\text{Stop}_t = C_t - \text{Loss}_t, \text{Position}_t = 1 \text{ (Long)}$
  5. If $C_t$ crosses below $\text{Stop}_{t-1}$: $\text{Stop}_t = C_t + \text{Loss}_t, \text{Position}_t = -1 \text{ (Short)}$
* **LuxAlgo MA Sabres Reversal Signal**:
  Identifies TEMA trend flips: if TEMA50 decreases for 20 consecutive bars and ticks up ($TEMA_t > TEMA_{t-1}$), fires Bullish Flip ($+1$). If TEMA50 increases for 20 consecutive bars and ticks down ($TEMA_t < TEMA_{t-1}$), fires Bearish Flip ($-1$).
* **Pivot Points & Fibonacci Retracements**:
  Computes Classic Pivots ($P = \frac{H+L+C}{3}$, $R_1, R_2, R_3, S_1, S_2, S_3$) and 50-bar Fibonacci retracements ($23.6\%, 38.2\%, 50.0\%, 61.8\%, 78.6\%$).
* **Ornstein-Uhlenbeck (OU) Mean-Reversion Half-Life**:
  Fits AR(1) process on price deviations $x_t = P_t - \text{EMA}(P_t)$:
  $$\Delta x_t = -\lambda x_{t-1} + \epsilon_t \implies t_{half} = \frac{\ln(2)}{\lambda}$$
  Measures speed of mean-reversion for range-fade strategy validation.

---

## 4. 8-Family Confluence Scoring & Weighting Engine

Indicators are mapped into 8 normalized factor family scores, each bounded within $[-100.0, +100.0]$.

### Factor Family Scorer Logic (`factors/scorer.py`)

1. **Trend Family**: EMA stack alignment (9>21>50>200), price distance to 200 EMA, MACD histogram relative to ATR, UT Bot state, and LuxAlgo Sabres flip boost ($\pm 25$ pts).
2. **Momentum Family**: Blended RSI and Stochastic %K oscillator values:
   $$\text{Score} = 0.6 \cdot \left( \frac{\text{RSI}_t - 50}{50} \cdot 100 \right) + 0.4 \cdot \left( \frac{\text{Stoch } \%K_t - 50}{50} \cdot 100 \right)$$
3. **Volatility Family**: Bollinger Band %B location relative to mid-band:
   $$\text{Score} = (\%B_t - 0.5) \cdot 200$$
4. **Structure Family**: Hyperbolic tangent scaling of distance to nearest pivot point and 50-bar Fibonacci level:
   $$\text{Score} = 0.6 \cdot \left( 100 \cdot \tanh\left( \frac{C_t - \text{Pivot}_t}{0.5 \cdot \text{ATR}_t} \right) \right) + 0.4 \cdot \left( (\text{Fib Position}_t - 0.5) \cdot 200 \right)$$
5. **Order Flow & Derivatives Family**: VWAP distance, Order Book Imbalance (bid vs ask volume depth), Derivatives Funding Rate (contrarian boost), Futures Premium Basis (spot vs perp), and Open Interest change alignment.
6. **Sentiment Family**: Alternative.me Fear & Greed Index (Extreme Fear $<25 \implies +12$ Bullish boost, Extreme Greed $>75 \implies -12$ Bearish boost), combined with crypto news sentiment.
7. **Macro & Cross-Asset Family**: Market cap dominance, BTC/ETH dominance metrics, and global multi-asset trend alignment.
8. **Consensus Family**: Cross-timeframe alignment and indicator directional agreement.

### Score Aggregation & Agreement Ratio Adjustment
1. Extract dynamic weight profile for timeframe interval (`intraday`, `short`, `swing`, `long`).
2. Filter to active factor families with valid data and re-normalize weights to sum to $1.0$.
3. Compute weighted raw score $R_{raw} = \sum w_i \cdot S_i$.
4. Determine **Agreement Ratio** ($A$):
   $$A = \frac{\text{Count of active factor families sharing the sign of } R_{raw}}{\text{Total active factor families}}$$
5. Calculate final **Composite Score**:
   $$\text{Composite} = \text{Clip}_{-100, 100}\left( R_{raw} \cdot (0.5 + 0.5 \cdot A) \right)$$
6. Assign Signal Action Labels:
   * $\text{Composite} \ge +60.0 \implies$ **Strong Buy**
   * $+20.0 \le \text{Composite} < +60.0 \implies$ **Buy**
   * $-20.0 < \text{Composite} < +20.0 \implies$ **Neutral**
   * $-60.0 < \text{Composite} \le -20.0 \implies$ **Sell**
   * $\text{Composite} \le -60.0 \implies$ **Strong Sell**

---

## 5. Market Regimes & Strategy Allocation

### Layer 1 Market Regime Classifier (`regime.py`)
* **Trend Regime**: ADX $> 25.0$ and CHOP $< 50.0$. Focuses on direction-following setups.
* **Range Regime**: ADX $< 20.0$ and CHOP $> 50.0$ with validated OU half-life ($t_{half} \le 24$ bars).
* **High Volatility Regime**: ATR percentile $> 95\text{th}$ percentile. Widens stop distance.
* **Squeeze Regime**: Bollinger Band width at multi-bar low. Prepares for breakout.

### Range-Fade Strategy Module
When a symbol enters a Range regime, the system activates the Range-Fade module. Instead of following breakouts, it fades band extremes (buying near Lower Bollinger Band / S1 Pivot, selling near Upper Bollinger Band / R1 Pivot), targeting the mean (EMA21) with relaxed R:R floors ($\text{RR}_{min} = 1.0$).

### Multiplicative Weights (Hedge) Strategy Allocator (`allocator.py`)
Dynamically adjusts capital allocation between Trend-Following and Range-Fade strategy families using an online exponential decay learning algorithm based on trailing 14-day performance:
$$w_{strat, t} = w_{strat, t-1} \cdot \exp\left( \eta \cdot \bar{R}_{strat} \right)$$
Re-normalized subject to a minimum weight floor of $5\%$ to prevent strategy starvation.

---

## 6. Expected Value (EV) Gate & Multi-Tier Protection

### Calibrated Expected Value (EV) Gate (`config.py`, `calibration.py`)
Before any signal is deemed actionable, it must pass the EV gate:
$$\text{EV} = p \cdot R - (1 - p) - \text{cost}_{R}$$
where:
* $p$: Calibrated win probability predicted by Isotonic Regression.
* $R$: Reward-to-Risk ratio ($\frac{\text{Target}_1 - \text{Entry}}{\text{Entry} - \text{Stop}}$).
* $\text{cost}_{R}$: Friction costs (taker fees + slippage) normalized in R units.

If $\text{EV} \le 0.0$ (or below tier floor), the signal is silenced.

```
Risk Geometry Setup
========================================= <- Target 3 (Entry + 4.5 * Risk)
========================================= <- Target 2 (Entry + 2.8 * Risk)
========================================= <- Target 1 (Entry + 1.8 * Risk, adjusted to Pivot)

▶ Entry Price (Bar Open + Slippage)
========================================= <- Stop Loss (Entry - 1.2 * ATR, adjusted to Swing Low)
```

### Self-Improving Protection Systems

1. **Isotonic Probability Calibration (`calibration.py`)**: Maps raw composite scores to empirical win rates via monotonic piecewise linear calibration.
2. **Page-Hinkley Strategy Drift Detection (`drift.py`)**: Monitors the running sequence of trade returns $R$. If cumulative negative drift exceeds threshold ($\lambda = 3.0$), it flags strategy drift, automatically raises the EV floor (to $+0.4 R$), and cuts position size by $50\%$ until conditions recover.
3. **Self-Calibration Brier Monitor**: Tracks rolling Brier score ($BS = \frac{1}{N}\sum (p_i - y_i)^2$). If calibration accuracy degrades below baseline, it automatically scales down trade sizing ("knows when it doesn't know").
4. **Global Circuit Breaker**: Halts all new trade signals for 24 hours if cumulative realized return drops below $-3.0 R$ over a rolling window.
5. **Multi-Tier Performance Gates**:
   * **Regime Gate**: Drops trading in market regimes showing negative rolling P&L.
   * **Direction Gate**: Temporarily halts long or short signals if trailing 2-day expectancy is negative.
   * **Symbol Gate**: Pauses specific assets with negative trailing expectancy.

---

## 7. Meta-ML Machine Learning Model (`meta_model.py`)

StarkX QuantEdge incorporates a secondary **Meta-Labeling Machine Learning Model** (Random Forest / L2 Logistic Regression) operating on high-dimensional meta-features extracted from primary signals.

### Meta-Feature Matrix (`meta_features.py`)
* Composite score, confidence, agreement ratio
* Individual 8 factor family scores
* Market regime, ADX, CHOP, ATR percentile, Bollinger Band width
* Orderbook bid/ask imbalance, funding rate, basis premium
* Calculated EV, R:R ratio, time-of-day / day-of-week encodings

### Shadow-to-Gating Promotion Framework
1. **Shadow Execution**: The Meta-Model runs continuously in SHADOW mode, logging predicted win probabilities $P_{meta}$ without affecting active trading.
2. **Walk-Forward Holdout Evaluation**: Periodically evaluates out-of-sample performance on historical outcomes ($N \ge 30$).
3. **Automated Promotion Gate**: If the Meta-Model achieves superior out-of-sample ROC-AUC and Brier score compared to the primary isotonic model, it is automatically promoted to actively filter signals in the EV Gate.

---

## 8. Capital-Adaptive Position Sizing (`sizing.py`, `costs.py`)

### Multi-Tier Capital Framework
The engine adapts position sizing and risk management based on total account equity:
* **Tier 1: Micro ($<\$5,000$)**: Prioritizes capital preservation, strict EV floors ($EV \ge 0.15 R$), capped leverage.
* **Tier 2: Core ($\$5,000 - \$50,000$)**: Optimal growth parameters, Fractional Kelly sizing ($0.25 \cdot f^*$).
* **Tier 3: Institutional ($>\$50,000$)**: Multi-leg execution, advanced orderbook friction modeling.

### Fractional Kelly Criterion & Ruin Prevention
$$\text{Kelly Fraction } f^* = \frac{p \cdot b - (1 - p)}{b}, \quad b = R$$
$$\text{Recommended Risk \%} = \min \left( \text{Risk}_{max}, \, 0.25 \cdot f^* \right)$$

### Parametric Orderbook Friction Modeling (`costs.py`)
Models realistic market execution costs based on order size and depth:
$$\text{Total Cost} = 2 \cdot \text{Fee}_{taker} + \text{Spread}_{half} + \text{Impact}_{market}(V_{order}, \text{Depth})$$

---

## 9. Multi-Agent AI Debate System (`llm/debate.py`)

When an active signal is detected, StarkX QuantEdge invokes a multi-agent AI debate via OpenRouter to analyze qualitative narrative context alongside quantitative numbers.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. INGEST SIGNAL                                                        │
│ Raw Signal Data (Symbol, Interval, 8 Factor Scores, Pivots, Sentiment)  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. BULL ANALYST AGENT                                                   │
│ Builds optimal long thesis using technical data & factor strengths.     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. BEAR ANALYST AGENT                                                   │
│ Rebuts Bull arguments & identifies structural weaknesses/risks.        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. RISK MANAGER (JUDGE AGENT)                                           │
│ Evaluates debate and returns structured JSON output:                    │
│ { "agreement", "conviction", "key_risks", "verdict" }                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Blended Final Confidence Score
$$\text{Penalty} = \begin{cases} 1.00 & \text{if Agreement = 'agree'} \\ 0.85 & \text{if Agreement = 'caution'} \\ 0.60 & \text{if Agreement = 'disagree'} \end{cases}$$
$$\text{Final Confidence} = \text{Round}\Big( \min\left(100.0, \, (0.5 \cdot \text{Model Confidence} + 0.5 \cdot \text{AI Conviction}) \cdot \text{Penalty}\right), \, 1 \Big)$$

### Deterministic Fallback Engine (`_fallback_debate`)
If LLM APIs are offline or unconfigured, the system seamlessly activates a deterministic fallback engine that computes structured debate arguments, conviction, and risk factors directly from mathematical factor scores.

---

## 10. Multi-Strategy Arbitrage Engine (`arb.py`)

StarkX QuantEdge includes a real-time multi-strategy arbitrage engine continuously scanning for zero-risk or statistical arbitrage opportunities.

### 1. Delta-Neutral Funding Rate Carry Arbitrage
Harvests crypto perpetual funding rates by taking opposing positions in Spot and Futures markets:
* Fits an **AR(1) Time-Series Model** on historical funding rates to forecast expected funding yield over holding horizon $H$:
  $$\hat{f}_{t+k} = \mu + \phi^k (f_t - \mu)$$
* Net EV calculation clearing 2-leg taker fees:
  $$\text{Net EV} = \sum_{k=1}^{H} \hat{f}_{t+k} - 2 \cdot (\text{Fee}_{spot} + \text{Fee}_{perp}) - \text{Buffer}$$

### 2. Triangular Currency Cycle Arbitrage
Executes Bellman-Ford negative cycle detection over exchange currency pair graphs (e.g. BTC $\rightarrow$ ETH $\rightarrow$ USDT $\rightarrow$ BTC):
$$\text{Cycle Return} = (R_{AB} \cdot R_{BC} \cdot R_{CA}) \cdot (1 - \text{Fee}_{taker})^3 - 1.0$$

### 3. Cross-Exchange Orderbook Arbitrage
Monitors real-time orderbook depth across exchange venues (Binance vs Bybit):
$$\text{Spread} = \frac{\text{Bid}_{Bybit} - \text{Ask}_{Binance}}{\text{Ask}_{Binance}} - (\text{Fee}_{Binance} + \text{Fee}_{Bybit})$$

---

## 11. Asynchronous Self-Learning Loop (`learning.py`, `resolver.py`)

```
      1. AUTOMATED OUTCOME RESOLUTION (resolver.py)
      Polls candle data to check active signals against TP/SL levels or 48-bar timeout.

      2. DATA EXTRACTION & FEATURE NORMALIZATION
      Joins outcomes, factor_logs, and signals partitioned by market regime.

      3. TRAIN CHALLENGER MODEL (learning.py)
      Fits L2-Regularized Logistic Regression on factor scores to predict outcomes.

      4. WALK-FORWARD HOLDOUT BACKTEST
      Evaluates Challenger weight profile against active Champion profile on out-of-sample data.

      5. DATABASE PROMOTION
      If Challenger outperforms Champion, promotes it to active status in Supabase.
```

---

## 12. Complete FastAPI API Reference

| Endpoint | Method | Parameters | Description |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | None | Returns server health status, version, and environment |
| `/signal` | `GET` | `symbol`, `interval`, `market`, `limit`, `with_flow` | Computes deterministic factor scores, levels, and regime |
| `/explain` | `GET` | `symbol`, `interval`, `market`, `limit`, `with_flow` | Computes signal + LLM narrative rationale |
| `/decision` | `GET` | `symbol`, `interval`, `market`, `limit` | Full pipeline: Signal + Multi-Agent AI Debate + Persistence |
| `/candles` | `GET` | `symbol`, `interval`, `market`, `limit` | Returns OHLCV candles for charting |
| `/db/status` | `GET` | None | Checks Supabase database reachability and persistence status |
| `/signals/recent` | `GET` | `limit` | Fetches recently logged trade signals |
| `/trades` | `GET` | `result`, `limit`, `offset`, `trade_size` | Returns paginated closed trade history with P&L |
| `/trade` | `GET` | `id` | Fetches complete detail for a specific trade signal |
| `/stats` | `GET` | None | Scoreboard summary of hit rate and average return |
| `/performance` | `GET` | `trade_size` | Paper trading portfolio P&L report (realized & floating) |
| `/summary` | `GET` | `trade_size` | Weekly, monthly, and all-time summary metrics & weight changes |
| `/resolve` | `POST` | `max_signals` | Manually triggers the automated signal outcome resolver |
| `/scan` | `POST` | `min_confidence` | Manually triggers multi-asset watchlist scanner |
| `/learning/status` | `GET` | None | Displays active champion weights, regime samples, & ML status |
| `/learning/train` | `POST` | None | Triggers factor weight retraining and walk-forward gating |
| `/meta/train` | `POST` | None | Trains Meta-ML model and checks shadow-to-gating promotion |
| `/arb/funding-scan` | `POST` | None | Executes delta-neutral funding-carry arbitrage scan |
| `/arb/triangular-scan` | `POST` | None | Executes triangular currency cycle arbitrage scan |
| `/arb/cross-scan` | `POST` | None | Executes cross-exchange (Binance vs Bybit) arbitrage scan |
| `/arb/opportunities` | `GET` | `limit` | Fetches recently logged positive-EV arbitrage opportunities |
| `/arb/alerts` | `GET` | `hours` | Returns active positive-EV arbitrage alerts for past N hours |
| `/outcome` | `POST` | Payload: `OutcomeIn` | Manually labels trade outcome (target/stop/timeout/manual) |
| `/webhook/tradingview` | `POST` | Payload: `TradingViewAlert`, Header: `x-signature` | HMAC-authenticated webhook endpoint for Pine Script alerts |

---

## 13. Frontend UI & Interactive Dashboards

The Next.js 16 web application (`/frontend`) provides a cockpit interface with the following interactive panels:

1. **Main Trading Cockpit (`page.tsx`, `SignalCard.tsx`)**: Real-time signal card displaying composite score gauge, confidence rating, regime badge, risk/reward levels (Entry, SL, $T_1, T_2, T_3$), meta-ML predicted win probability, recommended position size, and rationale.
2. **Interactive Financial Chart (`PriceChart.tsx`)**: Powered by TradingView `lightweight-charts`. Features live candlestick charting, volume bars, overlay toggles (EMA 9/21/50/200, UT Bot stop line, LuxAlgo Sabres reversal arrows, Pivot levels), and entry/stop/target visual markers.
3. **8-Factor Gauge Bar (`FactorBar.tsx`)**: Visual metric breakdown displaying scores for each of the 8 factor families (-100 to +100) with color gradients.
4. **Multi-Agent AI Debate Viewer (`DebatePanel.tsx`)**: Side-by-side display of Bull Analyst vs Bear Analyst arguments, Risk Manager verdict, agreement badge, and key risk factors.
5. **Automated Watchlist Scanner Panel (`ScannerPanel.tsx`)**: Real-time table displaying continuously scanned watchlist assets across multiple timeframes with filter controls.
6. **Paper Trade History & Modal (`TradeHistoryPanel.tsx`, `TradeDetailModal.tsx`)**: Filterable table of closed trades with outcome badges, realized P&L, MFE/MAE excursions, and full modal drill-down into historical signal state.
7. **Portfolio Performance & Equity Curve (`PerformancePanel.tsx`, `EquityCurve.tsx`)**: Interactive portfolio metrics showing equity curve, net P&L, win rate, profit factor, max drawdown, Sharpe ratio, and floating asset P&L.
8. **Learning Loop & System Summary (`SummaryPanel.tsx`)**: Dashboard tracking weekly/monthly performance, dynamic champion factor weight shifts, probability calibration curves, and meta-model status.
9. **Real-Time Arbitrage Dashboard (`ArbPanel.tsx`)**: Interactive panel displaying active funding rate carry opportunities, triangular arbitrage cycles, and cross-exchange spreads with net EV calculations.

---

## 14. Command Line Tools & Administration Scripts (`backend/scripts/`)

| Script | Command | Purpose |
| :--- | :--- | :--- |
| **Database Migration** | `python -m scripts.migrate` | Applies SQL migration sequences to Supabase PostgreSQL |
| **Run Backtest** | `python -m scripts.run_backtest` | Executes causal backtest simulation over historical data |
| **Walk-Forward Analysis** | `python -m scripts.walk_forward` | Runs walk-forward parameter sweep to optimize strategy |
| **Train Weights** | `python -m scripts.train_weights` | Retrains regime factor weights on resolved trade outcomes |
| **Scan Once** | `python -m scripts.scan_once` | Executes a single background scan of the watchlist |
| **Resolve Outcomes** | `python -m scripts.resolve` | Manually runs outcome resolver over open signals |
| **System Audit** | `python -m scripts.audit` | Comprehensive diagnostic check of database, data providers, & ML |
| **PnL Diagnostics** | `python -m scripts.diag_pnl` | Detailed breakdown of paper trading portfolio performance |
| **Verify Confluence** | `python -m scripts.verify_confluence` | Verifies deterministic math output against Pine Script baselines |
| **Verify Integrations** | `python -m scripts.verify_integrations` | Tests connectivity to Binance, TwelveData, OpenRouter, & Supabase |
| **Test Suites** | `python -m scripts.test_p0` ... `test_p3_tri` | Executes unit and integration test suites for all project phases |
| **Render Deployment** | `python -m scripts.deploy_render` | Diagnostics & deployment helper script for Render hosting |

---

## 15. Environment Variables & Configuration Reference

### Backend `.env` Configuration (`backend/.env`)

```env
# Server & Environment
APP_ENV=local
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Webhook Security
TRADINGVIEW_WEBHOOK_SECRET=your-shared-webhook-secret

# LLM Reasoning (OpenRouter)
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL_STRONG=openrouter/auto
OPENROUTER_MODEL_CHEAP=openai/gpt-4o-mini

# Market Data Adapters
TWELVEDATA_API_KEY=your-twelvedata-api-key
ALPHAVANTAGE_API_KEY=your-alphavantage-api-key
NEWSAPI_KEY=your-newsapi-key
COINMARKETCAP_API_KEY=your-coinmarketcap-api-key
CRYPTOQUANT_API_KEY=your-cryptoquant-api-key

# Supabase / PostgreSQL Persistence
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-supabase-publishable-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

# Risk & System Limits
RISK_PER_TRADE_PCT=0.75
MIN_REWARD_RISK=1.5
CONVICTION_FLOOR=18.0
EV_GATE_ENABLED=true
MIN_EV_R=0.0
DRIFT_ENABLED=true
CIRCUIT_BREAKER_ENABLED=true
ACCOUNT_EQUITY_USD=1000.0

# Autonomous Background Tasks
SCANNER_ENABLED=true
SCANNER_INTERVAL_MINUTES=30
RESOLVER_ENABLED=true
RESOLVER_INTERVAL_MINUTES=15
ARB_FUNDING_ENABLED=true
ARB_TRIANGULAR_ENABLED=true
ARB_CROSS_ENABLED=true
```

### Frontend `.env.local` Configuration (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

---

## 16. Development Setup & Deployment

### Local Development Setup

#### 1. Backend (Python FastAPI)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # Fill in active API keys & Postgres URL
python -m scripts.migrate       # Apply database migrations
uvicorn app.main:app --reload   # Server runs at http://127.0.0.1:8000
```

#### 2. Frontend (Next.js 16)
```powershell
cd frontend
npm install
copy .env.local.example .env.local
npm run dev                      # Frontend cockpit starts at http://localhost:3000
```

### Production Deployment

#### Backend Deployment (Render / Docker)
The application includes a production `Dockerfile` and `render.yaml`:
```powershell
# Build and run Docker container locally
docker build -t starkx-quantedge-backend .
docker run -p 8000:8000 --env-file backend/.env starkx-quantedge-backend
```

#### Frontend Deployment (Vercel)
Deploy `/frontend` directly to Vercel and configure `NEXT_PUBLIC_API_BASE` pointing to your hosted backend API URL.

---

## License & Attribution

StarkX QuantEdge is proprietary trading software built for quantitative market analysis and autonomous decision support. All rights reserved.
