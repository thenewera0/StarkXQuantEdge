"""Factor scoring: 8 categories -> composite signal + confidence."""

from .scorer import score_row, SignalResult, LABELS, label_for, tier_for
from .weights import weights_for_interval, timeframe_bucket, regime_base_weights

__all__ = [
    "score_row", "SignalResult", "LABELS", "label_for", "tier_for",
    "weights_for_interval", "timeframe_bucket", "regime_base_weights",
]
