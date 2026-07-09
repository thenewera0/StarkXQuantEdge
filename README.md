# StarkX QuantEdge — AI Crypto & Forex Confluence Engine

StarkX QuantEdge is an autonomous, multi-market trading decision-support cockpit. It scans markets, evaluates setups using a deterministic Python indicator engine, runs a multi-agent AI debate to analyze the narrative context, resolves trade outcomes against historical candle replays, tracks paper P&L, and adapts factor weights using a gated machine learning loop.

A key architectural rule is that **every price, indicator, level, and factor score is computed deterministically in Python**. The LLM never invents numbers; it only reasons over the structured data to produce rationales and debates.

---

## 1. System Technology Stack

The application is structured as a monorepo partitioned into three core directories: `/backend` (FastAPI), `/frontend` (Next.js), and `/db` (Supabase migrations).

```
StarkX QuantEdge Monorepo
├── backend/                  # Python FastAPI web server + trading engine
│   ├── app/                  # Main application package
│   │   ├── backtest/         # Replay simulation engine
│   │   ├── data/             # Live/historical data adapters (Binance, TwelveData, etc.)
│   │   ├── factors/          # Multi-family scoring and weighting mechanics
│   │   ├── indicators/       # Custom pure-Python mathematical indicators
│   │   ├── llm/              # OpenRouter integrations & agent prompts
│   │   └── scripts/          # Administration, training, and diagnostics utilities
│   └── requirements.txt      # Python dependencies
├── db/                       # Supabase relational schema files
│   └── migrations/           # SQL migration sequences
└── frontend/                 # Next.js web application
    ├── app/                  # Web app routing and layouts
    ├── components/           # UI elements (charts, signals, debates)
    └── lib/                  # Client-side API fetchers
```

### Dependency Stack
*   **Backend Framework**: `FastAPI` + `uvicorn` (ASGI web server).
*   **Database Client**: `psycopg2-binary` for direct PostgreSQL pooling.
*   **Data Science**: `pandas`, `numpy`.
*   **Task Scheduler**: `APScheduler` (Background scheduler running on the FastAPI host).
*   **Frontend Core**: `Next.js 16` (App Router, React 19, TypeScript).
*   **Styling**: `Tailwind CSS 3` + `lucide-react` for micro-icons.
*   **Charting Library**: `lightweight-charts` (TradingView Canvas wrapper).

---

## 2. Database Schema Layout

The database runs on **Supabase (PostgreSQL)**. It stores watchlists, log records of signal calculations, trade results, and weight variations.

### Table: `watchlist`
Tracks which asset symbols and timeframes are continuously polled by the scanner.
*   `id`: bigint (Primary Key, Identity)
*   `symbol`: text (e.g. `'BTCUSDT'`, `'EUR/USD'`)
*   `interval`: text (e.g. `'15m'`, `'4h'`, `'1d'`)
*   `market`: text (default `'crypto'`)
*   `active`: boolean (default `true`)
*   `created_at`: timestamptz
*   *Constraints*: `UNIQUE(symbol, interval)`

### Table: `signals`
Stores every trade alert emitted by the confluence engine.
*   `id`: bigint (Primary Key, Identity)
*   `symbol`: text
*   `interval`: text
*   `market`: text (e.g., `'crypto'`, `'forex'`)
*   `as_of`: timestamptz (The candle close time that triggered the signal)
*   `label`: text (`'Strong Sell'`, `'Sell'`, `'Neutral'`, `'Buy'`, `'Strong Buy'`)
*   `composite`: numeric (Overall score adjusted for agreement: $-100.0$ to $+100.0$)
*   `confidence`: numeric (Confidence rating: $0$ to $100$)
*   `regime`: text (Detected Layer 1 market regime)
*   `price`: numeric (Asset price at signal timestamp)
*   `atr`: numeric (Average True Range at signal timestamp)
*   `rationale`: text (Written rationale synthesized by the LLM)
*   `entry`: numeric (Calculated invalidation level/limit price)
*   `stop`: numeric (Volatility-based stop-loss level)
*   `target`: numeric (Primary Take-Profit target)
*   `agreement`: text (`'agree'`, `'caution'`, or `'disagree'` from the AI judge)
*   `conviction`: numeric ($0$ to $100$ judgment score from the Risk Manager)
*   `final_confidence`: numeric (Combined score blending composite and conviction)
*   `debate_source`: text (`'openrouter'` or `'fallback'`)
*   `created_at`: timestamptz

### Table: `factor_logs`
Logs the individual scores of each factor category to train the machine learning weights.
*   `id`: bigint (Primary Key, Identity)
*   `signal_id`: bigint (References `signals.id` with cascade deletion)
*   `trend`, `momentum`, `volatility`, `structure`, `flow`, `sentiment`, `macro`, `consensus`: numeric (Individual family scores: $-100.0$ to $+100.0$)

### Table: `outcomes`
Stores the actual trading result of each signal as resolved by historical data replay.
*   `id`: bigint (Primary Key, Identity)
*   `signal_id`: bigint (References `signals.id`)
*   `resolved_at`: timestamptz
*   `result`: text (`'target'`, `'stop'`, `'timeout'`, or `'manual'`)
*   `pnl`: numeric (Calculated net return, accounting for fees and slippage)
*   `mfe`: numeric (Maximum Favorable Excursion, fraction of entry price)
*   `mae`: numeric (Maximum Adverse Excursion, fraction of entry price)
*   `bars_held`: integer

### Table: `regime_weights`
Maintains the optimized weights produced by the self-learning engine.
*   `id`: bigint (Primary Key, Identity)
*   `regime`: text
*   `interval`: text (Representing the timeframe category: `intraday`, `short`, `swing`, `long`)
*   `weights`: jsonb (Key-value pairs of category weights)
*   `is_champion`: boolean
*   `created_at`: timestamptz

---

## 3. Mathematical Indicator Engine

StarkX QuantEdge uses pure NumPy and Pandas to compute technical indicators. The calculations are designed to be causal—using only prior bars ($< t$) or the current closed bar ($t$) to eliminate lookahead bias in backtests.

### Average True Range (ATR)
Calculates Wilder's Average True Range to measure volatility:
$$TR_t = \max \left( (H_t - L_t), \, |H_t - C_{t-1}|, \, |L_t - C_{t-1}| \right)$$
$$ATR_t = \text{EMA}\left(TR, \, \alpha = \frac{1}{14}\right)$$

### Average Directional Index (ADX)
Measures trend strength for Layer 1 regime detection:
$$+DM_t = H_t - H_{t-1} \quad \text{if} \quad (H_t - H_{t-1}) > (L_{t-1} - L_t) \quad \text{and} \quad (H_t - H_{t-1}) > 0, \quad \text{else } 0$$
$$-DM_t = L_{t-1} - L_t \quad \text{if} \quad (L_{t-1} - L_t) > (H_t - H_{t-1}) \quad \text{and} \quad (L_{t-1} - L_t) > 0, \quad \text{else } 0$$
$$+DI_t = 100 \times \frac{\text{EMA}(+DM, \, \alpha)}{\text{ATR}_t}$$
$$-DI_t = 100 \times \frac{\text{EMA}(-DM, \, \alpha)}{\text{ATR}_t}$$
$$DX_t = 100 \times \frac{|+DI_t - -DI_t|}{+DI_t + -DI_t}$$
$$ADX_t = \text{EMA}(DX, \, \alpha)$$

### Choppiness Index (CHOP)
Differentiates range-bound consolidation from active trends:
$$\text{CHOP}_t = 100 \times \frac{\log_{10} \left( \sum_{i=0}^{13} TR_{t-i} \right) - \log_{10}\left( \max(H_{t-13 \dots t}) - \min(L_{t-13 \dots t}) \right)}{\log_{10}(14)}$$

### UT Bot Trailing Stop & Position State
A step-based stop system ported from TradingView Pine Script:
1.  Calculate True Range stop distance: $\text{Loss}_t = \text{Multiplier} \times \text{ATR}_{10, t}$.
2.  If current close $C_t > \text{Stop}_{t-1}$ and prior close $C_{t-1} > \text{Stop}_{t-1}$:
    $$\text{Stop}_t = \max(\text{Stop}_{t-1}, \, C_t - \text{Loss}_t)$$
3.  If current close $C_t < \text{Stop}_{t-1}$ and prior close $C_{t-1} < \text{Stop}_{t-1}$:
    $$\text{Stop}_t = \min(\text{Stop}_{t-1}, \, C_t + \text{Loss}_t)$$
4.  If $C_t$ crosses above $\text{Stop}_{t-1}$:
    $$\text{Stop}_t = C_t - \text{Loss}_t, \quad \text{Position}_t = 1 \text{ (Long)}$$
5.  If $C_t$ crosses below $\text{Stop}_{t-1}$:
    $$\text{Stop}_t = C_t + \text{Loss}_t, \quad \text{Position}_t = -1 \text{ (Short)}$$

### LuxAlgo MA Sabres Reversal Signal
Identifies momentum shifts using Triple EMA (TEMA):
1.  Compute $\text{TEMA}_{50, t} = 3 \times \text{EMA}_t - 3 \times \text{EMA}(\text{EMA}_t) + \text{EMA}(\text{EMA}(\text{EMA}_t))$.
2.  If TEMA has decreased for 20 consecutive bars, and then ticks up ($TEMA_t > TEMA_{t-1}$), trigger a Bullish Flip ($+1$).
3.  If TEMA has increased for 20 consecutive bars, and then ticks down ($TEMA_t < TEMA_{t-1}$), trigger a Bearish Flip ($-1$).

---

## 4. Confluence Scoring & Weighting Engine

Individual indicators are processed into 8 normalized categories, each returning a score in the range $[-100.0, +100.0]$.

### Individual Scorer Logic
*   **Trend Score**: Combines EMA stack relative layouts (9/21/50/200 EMAs), distance of price from the 200 EMA, MACD histogram size relative to ATR, and the UT Bot position state. A LuxAlgo Sabres flip adds a $\pm 25$ point boost.
*   **Momentum Score**: Blends RSI and Stochastic %K:
    $$\text{Score} = 0.6 \times \left( \frac{\text{RSI}_t - 50}{50} \times 100 \right) + 0.4 \times \left( \frac{\text{Stochastic } \%K_t - 50}{50} \times 100 \right)$$
*   **Volatility Score**: Evaluates the closing price's position within Bollinger Bands:
    $$\text{Score} = (\%B_t - 0.5) \times 200$$
*   **Structure Score**: Combines distance from pivots and lookback range position:
    $$\text{Score} = 0.6 \times \left( 100 \times \tanh\left( \frac{C_t - \text{Pivot}_t}{0.5 \times \text{ATR}_t} \right) \right) + 0.4 \times \left( (\text{Fib Position}_t - 0.5) \times 200 \right)$$
*   **Flow Score**: Evaluates VWAP distance, order book imbalance, derivatives funding rates (contrarian), premium basis (contrarian), and open interest changes matching the VWAP direction.

### Score Aggregation & Agreement adjustment
1.  Extract the weight profile for the interval. For example, the **Swing** profile sets:
    $$\{ \text{trend}: 18\%, \, \text{momentum}: 14\%, \, \text{volatility}: 8\%, \, \text{structure}: 16\%, \, \text{flow}: 10\%, \, \text{sentiment}: 8\%, \, \text{macro}: 16\%, \, \text{consensus}: 10\% \}$$
2.  Filter categories to only those containing valid data. Re-normalize weights so they sum to $1.0$.
3.  Calculate the weighted raw average $R$.
4.  Determine the **Agreement Ratio** ($A$):
    $$A = \frac{\text{Count of active categories sharing the sign of } R}{\text{Total count of active categories}}$$
5.  Adjust the raw average to get the final composite score:
    $$\text{Composite} = \text{Clip}_{-100, 100}\left( R \times (0.5 + 0.5 \times A) \right)$$
6.  Assign action labels based on the composite score:
    *   $\text{Composite} \ge 60$: **Strong Buy**
    *   $20 \le \text{Composite} < 60$: **Buy**
    *   $-20 < \text{Composite} < 20$: **Neutral**
    *   $-60 < \text{Composite} \le -20$: **Sell**
    *   $\text{Composite} \le -60$: **Strong Sell**

---

## 5. Psychology, Risk Geometry & Filters

Before generating a trade signal, the system processes sentiment indices, risk metrics, and structural levels to filter out low-probability setups.

### Contrarian Psychological Overlay
*   **Long Candidate (+1)**: 
    *   If derivatives funding rate is highly negative ($< -0.02\%$), it suggests a high number of short positions. The engine adds $+15$ to the composite score to account for short-squeeze potential.
    *   If the Fear & Greed index is below $25$ (Extreme Fear), it adds $+12$ to the composite.
*   **Short Candidate (-1)**:
    *   If funding rate is highly positive ($> +0.02\%$), it suggests crowded longs. The engine subtracts $-15$ from the composite.
    *   If Fear & Greed index is above $75$ (Extreme Greed), it subtracts $-12$ from the composite.

### Volatility-Based Stops & Targets
Stops and targets are calculated using ATR multipliers, pivot points, and recent swing extremes.

```
Long Entry Setup
=========================================  <- Target 3 (Entry + 4.5 * Risk)
=========================================  <- Target 2 (Entry + 2.8 * Risk)
=========================================  <- Target 1 (Entry + 1.8 * Risk, adjusted for swing high)

▶ Entry Price (Bar Open + Slippage)
=========================================  <- Stop Loss (Entry - 1.2 * ATR, adjusted for swing low)
```

*   **Long Trade Geometry**:
    $$\text{Stop Loss} = \text{Entry} - (k \times \text{ATR}_t) \quad \text{where } k = 1.2 \text{ (or } 1.8 \text{ in High Volatility)}$$
    $$\text{Risk} = \text{Entry} - \text{Stop}$$
    $$\text{Target}_1 = \text{Entry} + 1.8 \times \text{Risk} \quad (\text{adjusted to the lowest pivot resistance if it sits between } 1.8R \text{ and } 3.0R)$$
    $$\text{Target}_2 = \text{Entry} + 2.8 \times \text{Risk}, \quad \text{Target}_3 = \text{Entry} + 4.5 \times \text{Risk}$$
*   **Veto Filters**:
    *   **R:R Filter**: Vetoes the trade if the primary Reward-to-Risk ratio is less than $1.5$.
    *   **Regime Filter**: Restricts trading to trend regimes by default, filtering out range or high-volatility environments unless they show a proven positive expectancy.
    *   **Directional Filter**: Temporarily suspends long or short signals if recent live outcomes for that direction show a negative net P&L over the trailing 21 days.

---

## 6. Multi-Agent AI Debate System

For active signals, the system runs a multi-agent debate using structured prompts to analyze the narrative context behind the technical metrics.

```
   ┌─────────────────────────────────────────────────────────────────┐
   │ 1. INGEST                                                       │
   │ Raw Signal Data (Symbol, Interval, Scores, Pivots, Sentiment)   │
   └────────────────────────────────┬────────────────────────────────┘
                                    │
                                    ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ 2. BULL ANALYST                                                 │
   │ Argues the long case using only the provided numbers.           │
   └────────────────────────────────┬────────────────────────────────┘
                                    │
                                    ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ 3. BEAR ANALYST                                                 │
   │ Builds the short case and rebuts the Bull's arguments.          │
   └────────────────────────────────┬────────────────────────────────┘
                                    │
                                    ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ 4. RISK MANAGER (JUDGE)                                         │
   │ Adjudicates the debate and outputs structured JSON decision:    │
   │ { "agreement", "conviction", "key_risks", "verdict" }          │
   └─────────────────────────────────────────────────────────────────┘
```

If OpenRouter is offline or credentials are missing, the system uses a fallback module (`_fallback_debate`) that calculates the debate narrative, conviction score, and risk labels deterministically from the factor scores.

---

## 7. Backtest Replay & Parameter Sweep

The backtest harness simulates historical trade execution bar-by-bar to evaluate the performance of a given configuration.

### Replay Simulation Rules
1.  **Causal Signal Checks**: The trading decision for bar $t$ is calculated using the indicators computed at the close of bar $t-1$. This prevents lookahead bias.
2.  **Open Execution**: Trades are filled at the opening price of bar $t$ rather than the close of bar $t-1$.
3.  **Conservative Fills**: If a bar's high reaches the target and its low touches the stop in the same interval, the simulator assumes the stop was hit first.
4.  **Transaction Fees**: Deducts taker fees (e.g., $0.04\%$ for futures, $0.1\%$ for spot) and slippage (e.g., $0.02\%$ per fill) from the net return.
5.  **Excursion Logging**: Logs Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE) to measure price movement during the trade.

### Walk-Forward Parameter Sweep
To avoid curve-fitting (over-optimizing parameters on historical noise), the system runs a walk-forward analysis:

$$\underbrace{[\quad \text{In-Sample Optimization (e.g. 700 bars)} \quad]}_{\text{Find best ATR multiplier & Risk-to-Reward Ratio}} \quad \underbrace{[\quad \text{Out-of-Sample Performance (e.g. 250 bars)} \quad]}_{\text{Record performance using optimized parameters}}$$

The window then shifts forward by the out-of-sample length, repeating the process. Only the out-of-sample results are used to measure the strategy's overall performance.

---

## 8. Asynchronous Self-Learning Loop

The self-learning loop dynamically optimizes category weights as trade outcomes accumulate in the database.

```
       1. EXTRACT DATA
       Join outcomes, factor_logs, and signals by regime (requires >= 40 samples).

       2. TRAIN CHALLENGER MODEL
       Fit L2 Logistic Regression. The positive coefficients form the Challenger weights.

       3. WALK-FORWARD BACKTEST
       Compare Challenger weights against active Champion weights on out-of-sample data.

       4. PROMOTE CHAMPION
       If Challenger outperforms Champion in backtesting, promote it to active status.
```

### Mathematical Training Detail
1.  Extract training data: features $X \in \mathbb{R}^{d}$ represent the backtestable factor scores (Trend, Momentum, Volatility, Structure); labels $y \in \{0, 1\}$ represent trade outcomes ($1.0$ for target hits, $0.0$ for stop hits).
2.  Standardize the features:
    $$X_s = \frac{X - \mu}{\sigma + 10^{-9}}$$
3.  Fit a Logistic Regression model with $L2$ regularization by minimizing cross-entropy loss:
    $$E(w) = -\frac{1}{n}\sum_{i=1}^{n}\left[ y_i \log(p_i) + (1-y_i)\log(1-p_i) \right] + \frac{\lambda}{2n}\|w\|^2_2$$
    where $p_i = \sigma(X_{s, i} w) = \frac{1}{1 + e^{-X_{s, i} w}}$.
4.  Filter coefficients to keep only positive relationships:
    $$w_c = \max(0, \, w)$$
5.  Scale the coefficients so they sum to the baseline indicator allocation:
    $$\text{Challenger Weight}_j = \frac{w_{c, j}}{\sum w_c} \times \sum_{k \in \text{Backtestable}} \text{Baseline Weight}_k$$
6.  The remaining weight is allocated to external variables (e.g., Sentiment and Macro), ensuring the final weights sum to $1.0$.
7.  **Holdout Gate**: The new challenger weights are backtested on out-of-sample data. If they produce a higher return than the current champion weights, they are promoted in the database to score new signals.

---

## 9. Development and Deployment

### Local Development Setup

#### Backend (Python & FastAPI)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # Fill in active API keys
python -m scripts.migrate       # Initialize Supabase DB tables
uvicorn app.main:app --reload   # Health check at http://127.0.0.1:8000/health
```

#### Frontend (Next.js)
```powershell
cd frontend
npm install
copy .env.local.example .env.local   # Set NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm run dev                          # App starts at http://localhost:3000
```
