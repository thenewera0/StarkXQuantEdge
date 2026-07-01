"""Multi-agent debate: Bull vs Bear, adjudicated by a Risk Manager.

Pattern (from PLAN.md / TradingAgents-style): the deterministic engine produces the numbers; three
LLM agents then REASON and ARGUE over them before the system settles on a final conviction.

  1. Bull analyst  — strongest evidence-based long case (uses only provided numbers).
  2. Bear analyst  — strongest short case, rebutting the bull.
  3. Risk manager  — weighs both + the model signal, outputs a structured verdict (JSON).

The deterministic label stays the headline (numbers are the anchor). The debate decides CONVICTION,
whether the AI AGREES/CAUTIONS/DISAGREES with the model, and the key risks. If OpenRouter is
unavailable, a deterministic fallback builds the same structure from the factor scores.
"""

from __future__ import annotations

import json

from ..factors.weights import weights_for_interval
from .openrouter import LLMUnavailable, chat

_CATS = ("trend", "momentum", "volatility", "structure", "flow", "sentiment", "macro", "consensus")

_BULL_SYS = (
    "You are a BULLISH trading analyst in a debate. Argue the strongest evidence-based LONG case "
    "for this asset using ONLY the numbers provided (category scores, composite, levels, context). "
    "Never invent or alter a number. 3-5 crisp sentences. Cite specific factor scores. Concede "
    "nothing you don't have to, but stay honest about what the data actually shows."
)
_BEAR_SYS = (
    "You are a BEARISH trading analyst in a debate. Argue the strongest evidence-based SHORT case "
    "using ONLY the numbers provided, and directly rebut the bull's argument. Never invent or alter "
    "a number. 3-5 crisp sentences citing specific factor scores."
)
_JUDGE_SYS = (
    "You are a senior RISK MANAGER adjudicating a bull/bear debate. You are given the deterministic "
    "model signal (the numeric anchor), the bull case, and the bear case. Weigh them soberly. You "
    "may NOT invent numbers. Decide a final conviction and whether you agree with the model. "
    "Respond in STRICT JSON only, no prose, with keys: "
    '{"agreement": "agree"|"caution"|"disagree", "conviction": <0-100 integer>, '
    '"key_risks": [<=3 short strings], "verdict": "<2-3 sentence final call>"}'
)


def _signal_brief(signal: dict) -> str:
    """Compact, numbers-only view handed to each agent."""
    return json.dumps(
        {
            "symbol": signal["symbol"],
            "market": signal.get("market"),
            "interval": signal["interval"],
            "model_label": signal["label"],
            "composite": signal["composite"],
            "model_confidence": signal["confidence"],
            "category_scores": signal["categories"],
            "price": signal["price"],
            "levels": signal["levels"],
            "macro_context": signal.get("macro"),
            "news_context": signal.get("news"),
        },
        default=str,
    )


def _parse_judge(text: str) -> dict | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{") :]
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    agreement = str(data.get("agreement", "caution")).lower()
    if agreement not in ("agree", "caution", "disagree"):
        agreement = "caution"
    try:
        conviction = max(0, min(100, int(round(float(data.get("conviction", 50))))))
    except (TypeError, ValueError):
        conviction = 50
    risks = data.get("key_risks") or []
    if not isinstance(risks, list):
        risks = [str(risks)]
    return {
        "agreement": agreement,
        "conviction": conviction,
        "key_risks": [str(r) for r in risks][:3],
        "verdict": str(data.get("verdict", "")).strip(),
    }


# --- Deterministic fallback (no LLM) ---------------------------------------


def _split_factors(signal: dict) -> tuple[list, list]:
    weights = weights_for_interval(signal["interval"])
    contrib = []
    for cat in _CATS:
        v = signal["categories"].get(cat)
        if v is not None:
            contrib.append((cat, v, weights.get(cat, 0.0) * v))
    pos = sorted([c for c in contrib if c[1] > 0], key=lambda x: x[2], reverse=True)
    neg = sorted([c for c in contrib if c[1] < 0], key=lambda x: x[2])
    return pos, neg


def _fallback_debate(signal: dict) -> dict:
    pos, neg = _split_factors(signal)
    pos_txt = ", ".join(f"{c} ({v:+.0f})" for c, v, _ in pos) or "none"
    neg_txt = ", ".join(f"{c} ({v:+.0f})" for c, v, _ in neg) or "none"
    composite = signal["composite"]

    bull = (
        f"Supportive factors lean long: {pos_txt}. With a composite of {composite:+.0f}, the "
        f"bullish read rests on these categories holding."
    )
    bear = (
        f"Opposing factors lean short: {neg_txt}. The bull case weakens if these dominate, which a "
        f"composite of {composite:+.0f} only partially reflects."
    )
    agreement = "agree" if abs(composite) >= 20 else "caution"
    conviction = int(round(min(100.0, 0.6 * abs(composite) + 0.4 * signal["confidence"])))
    key_risks = [f"{c} against the call ({v:+.0f})" for c, v, _ in (neg if composite >= 0 else pos)[:3]]
    verdict = (
        f"Model reads {signal['label']} (composite {composite:+.0f}, confidence {signal['confidence']:.0f}). "
        f"Evidence is {'aligned' if agreement == 'agree' else 'mixed'}; treat conviction as {conviction}/100 and honor the stop."
    )
    return {
        "bull": bull,
        "bear": bear,
        "agreement": agreement,
        "conviction": conviction,
        "key_risks": key_risks,
        "verdict": verdict,
        "source": "fallback",
    }


# --- Public entry point -----------------------------------------------------


def run_debate(signal: dict) -> dict:
    """Run the three-agent debate. Falls back to deterministic synthesis if OpenRouter is down."""
    brief = _signal_brief(signal)
    try:
        bull = chat(
            [{"role": "system", "content": _BULL_SYS}, {"role": "user", "content": brief}],
            temperature=0.5, max_tokens=240,
        )
        bear = chat(
            [
                {"role": "system", "content": _BEAR_SYS},
                {"role": "user", "content": f"{brief}\n\nBULL ARGUMENT TO REBUT:\n{bull}"},
            ],
            temperature=0.5, max_tokens=240,
        )
        judge_raw = chat(
            [
                {"role": "system", "content": _JUDGE_SYS},
                {"role": "user", "content": f"{brief}\n\nBULL:\n{bull}\n\nBEAR:\n{bear}"},
            ],
            temperature=0.2, max_tokens=320,
        )
    except LLMUnavailable:
        return _fallback_debate(signal)

    judge = _parse_judge(judge_raw)
    if judge is None:
        # Got text but couldn't parse JSON: keep the arguments, synthesize the verdict deterministically.
        fb = _fallback_debate(signal)
        return {"bull": bull, "bear": bear, **{k: fb[k] for k in ("agreement", "conviction", "key_risks")},
                "verdict": judge_raw.strip()[:600], "source": "openrouter"}

    return {"bull": bull, "bear": bear, **judge, "source": "openrouter"}
