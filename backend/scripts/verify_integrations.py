"""One-shot verification of the new integrations: TwelveData, NewsAPI, indicators, OpenRouter."""

from __future__ import annotations

from app.data import fetch_klines_td, news_sentiment
from app.llm.rationale import build_rationale
from app.signal_service import compute_signal


def main() -> None:
    fx = fetch_klines_td("EUR/USD", "1h", 300)
    print(f"TWELVEDATA EUR/USD bars: {len(fx)}  last close: {round(fx['close'].iloc[-1], 5)}")

    print("NEWS BTC:", news_sentiment("BTCUSDT"))

    sig = compute_signal("BTCUSDT", "4h", market="crypto")
    print(f"CRYPTO {sig['symbol']} {sig['label']} comp={sig['composite']} conf={sig['confidence']}")
    print(f"  trend={sig['categories']['trend']}  sentiment={sig['categories']['sentiment']}")

    exp = build_rationale(sig)
    print(f"LLM source: {exp['source']}  model: {exp['model']}")
    print("RATIONALE:", exp["rationale"][:500])

    fxsig = compute_signal("EUR/USD", "1h", market="forex")
    print(f"FOREX {fxsig['symbol']} {fxsig['label']} comp={fxsig['composite']} conf={fxsig['confidence']} "
          f"price={fxsig['price']} dir={fxsig['levels']['direction']}")


if __name__ == "__main__":
    main()
