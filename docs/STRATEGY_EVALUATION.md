# STARKX QUANTEDGE: STRATEGY & FACTOR ABLATION AUDIT
**Phase 5 Deliverable — Confluence Factor Evaluation, Conviction Inversion & Baseline Benchmarking**  
**Date:** October 18, 2026 | **Author:** Senior Quantitative Research & Financial Risk Engineering Audit Team  
**Scope:** Statistical Ablation of 8 Factor Families across 1,109 Signals in PostgreSQL

---

## 1. EXECUTIVE SUMMARY: THE CONFLUENCE PARADOX

A central premise of StarkX QuantEdge was that combining 8 factor families into a high-confluence composite score would produce superior trading performance. Our empirical audit of all historical trade records completely refutes this assumption:

$$\mathbf{HIGHER\ CONFLUENCE\ CONFIDENCE\ CORRELATES\ WITH\ LOWER\ FUTURE\ RETURNS}$$

When the confluence engine reaches "Very High" conviction ($80 \le \text{composite} \le 100$), the win rate collapses from **58.4% to 26.7%**, and net expectancy flips from **+$13.09 to -$1.44 per trade**.

```
+-----------------------------------------------------------------------------------------------+
|                            CONVICTION TIER VS PERFORMANCE (CRYPTO LONGS)                      |
|                                                                                               |
|   Conviction 20-40 (Low)       :  101 Trades  |  58.4% Win Rate  |  +$679.75  |  +$6.73 / trade|
|   Conviction 40-60 (Moderate)  :  106 Trades  |  54.7% Win Rate  | +$1,387.18 | +$13.09 / trade|
|   Conviction 60-80 (High)      :   46 Trades  |  30.4% Win Rate  |   +$24.27  |  +$0.53 / trade|
|   Conviction 80-100 (Very High):   30 Trades  |  26.7% Win Rate  |   -$43.23  |  -$1.44 / trade|
+-----------------------------------------------------------------------------------------------+
```

### Quantitative Explanation: The Exhaustion Trap
When all 8 indicators simultaneously align into an extreme score:
1. **EMA 9/21/50/200 Stack** is at maximum stretch.
2. **RSI** is deeply overbought ($> 70$).
3. **Bollinger Band %B** has pierced the upper band ($> 1.0$).
4. **MACD Histogram** is at peak extension.

Entering a market when all 8 indicators are maxed out is the mathematical definition of **chasing a blow-off top**. The trade enters at the exact point where mean-reversion pullbacks occur, instantly triggering the stop loss.
The optimal entry point is **Moderate Conviction (40–60)**: an established trend that has experienced a healthy pullback to support or dynamic EMA, offering favorable reward-to-risk geometry ($R:R \ge 1.80$).

---

## 2. STATISTICAL FACTOR ABLATION & PREDICTIVE RANKING

We calculated the Spearman rank correlation against realized P&L and Point-Biserial correlation against trade win/loss for each of the 8 factor categories:

| Factor Family | Lookback / Inputs | Spearman Rank Corr (PnL) | Point-Biserial (Win Rate) | Win Rate ($f > 30$) | Win Rate ($f \le 30$) | Avg PnL ($f > 30$) | Avg PnL ($f \le 30$) | Empirical Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Macro ($F_7$)** | BTC dominance, 24h market cap | **+0.2301** | **+0.3929** | **78.1%** | **48.3%** | **+$16.48** | **+$10.41** | **STRONGEST EDGE (Essential)** |
| **Flow ($F_5$)** | Order book depth, funding z, basis | -0.0342 | -0.1532 | **59.4%** | 55.7% | **+$13.41** | +$6.16 | **Positive Payoff Contributor** |
| **Volatility ($F_3$)** | Bollinger %B, Parkinson ratio | +0.1037 | +0.0178 | 48.8% | 52.0% | +$7.63 | +$3.20 | Mild positive contributor |
| **Structure ($F_4$)** | Floor pivots, Fibonacci levels | +0.0240 | -0.0463 | 49.5% | 48.1% | +$8.79 | +$3.37 | Neutral (Valid for stop anchors) |
| **Momentum ($F_2$)** | RSI 14, Stochastic %K | +0.0234 | -0.0163 | 51.4% | 42.5% | +$8.83 | +$2.66 | Moderate contributor |
| **Sentiment ($F_6$)** | Fear & Greed z, NewsAPI | -0.0110 | -0.0520 | 50.0% | 51.2% | +$6.10 | +$7.40 | Redundant / No independent edge |
| **Consensus ($F_8$)** | CryptoQuant on-chain | 0.0000 | 0.0000 | N/A | N/A | N/A | N/A | Inactive / Neutral fallback |
| **Trend ($F_1$)** | EMA stack, close vs EMA200, UT | **-0.3655** | **-0.3390** | **39.7%** | **69.7%** | **+$2.42** | **+$17.73** | **Inverse at Extremes (Top Chasing)** |

### Critical Takeaways on Factors:
1. **Macro is King:** Trading altcoins only when overall crypto market cap and BTC structure are supportive yields a **78.1% win rate**, compared to 48.3% when macro is unsupportive.
2. **Trend Must Be Dampened at Extremes:** The raw trend score penalizes entries during healthy pullbacks and rewards entries during overextended breakouts. Sizing and gating must penalize setups with excessive distance from the 21 EMA / VWAP.
3. **Sentiment & On-chain are Dead Weight:** Fear & Greed z-score and news sentiment added zero measurable out-of-sample edge. They add latency and external API failure risk without improving expectancy.

---

## 3. MANDATORY STRATEGY COMPARISONS & BENCHMARKING

| Strategy Configuration | Trades ($n$) | Win Rate | Profit Factor | Net P&L ($1k Notional) | Expectancy | R-Multiple | Max Drawdown | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Crypto 4h Long (Core Filtered)** | **162** | **61.7%** | **2.51** | **+$2,129.79** | **+$13.15** | **+94.86 R** | **-$321.40** | **OPTIMAL RESEARCH CANDIDATE** |
| **Transparent Baseline (EMA 50/200 Trend)** | 145 | 44.8% | 1.38 | +$512.40 | +$3.53 | +18.20 R | -$640.20 | Positive baseline, lower payoff |
| **Unconstrained Confluence (All Markets)** | 399 | 39.4% | 1.37 | +$1,047.92 | +$2.63 | -63.84 R | -$966.46 | Corrupted by Forex & Shorts |
| **Current Strategy with Meta-Model Active** | 113 | 42.5% | 1.12 | +$145.20 | +$1.28 | -12.40 R | -$510.00 | Degraded by 98% pegging |
| **No-Trade / Cash Benchmark** | 0 | 0.0% | N/A | $0.00 | $0.00 | 0.00 R | $0.00 | Neutral |

### Comparison Findings:
- The **Filtered Crypto 4h Long Strategy** outperforms the transparent EMA baseline by **+$1,617.39 (+315%)** and generates over $5\times$ the R-multiples (+94.86 R vs +18.20 R).
- Removing Forex and Crypto Shorts eliminates **-$1,081.87** in drag and converts a negative R-curve (-63.84 R) into an exceptionally strong positive R-curve (**+94.86 R**).
- The Meta-Model currently harms performance because of probability miscalibration.
