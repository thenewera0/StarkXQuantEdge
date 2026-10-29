# StarkX LAB: Strategy Developer Playbook

> **Scope:** Protocol and governance guidelines for introducing new strategies into StarkX Lab.  
> **Rule 0.6:** No self-modification without evidence. The system never edits its own code. All parameter mutations must remain strictly within pre-registered bounds verified by daily SHA-256 hash checks.

---

## 1. Strategy Interface Protocol

Every strategy implemented in `backend/app/lab/strategies/` must satisfy the canonical `Strategy` protocol defined in `backend/app/lab/models.py`:

```python
from typing import Literal, List
from app.lab.models import MarketContext, Signal

class Strategy:
    id: str                                  # Unique strategy identifier, e.g. "donchian_4h"
    timeframe: Literal["1h", "4h", "1d"]     # Timeframe on which bar close triggers
    params: dict                             # Numerical parameters for indicators/rules

    def on_bar_close(self, ctx: MarketContext) -> List[Signal]:
        """Evaluates closed historical bars point-in-time and returns signals.
        
        CRITICAL RULES:
        1. Accesses ctx.bars strictly closed BEFORE current time (lookahead-free).
        2. Decisions on CLOSED bars only.
        3. Initial stop distance >= 0.25% (crypto).
        4. Target must be 0.5R to 5.0R (or None if using trailing stop).
        """
        ...
```

---

## 2. Pre-Registration in `config/lab_spec.json`

Every strategy must be pre-registered in `config/lab_spec.json` with its:
1. `timeframe`: `"1h"`, `"4h"`, or `"1d"`.
2. `universe_rule`: `"top_30_volume"`.
3. `defaults`: baseline parameter dictionary.
4. `numeric_bounds`: `[min_val, max_val]` for every mutable parameter.
5. `direction_permissions`: `short_enabled: false` by default, except for explicit short variants.
6. `cost_gate`: `max_median_cost_r: 0.25`.

Example specification entry:
```json
{
  "strategies": {
    "donchian_4h": {
      "timeframe": "4h",
      "universe_rule": "top_30_volume",
      "direction_permissions": {
        "long_enabled": true,
        "short_enabled": true
      },
      "defaults": {
        "entry_period": 55,
        "exit_period": 20,
        "stop_atr": 2.5,
        "max_hold_bars": 48
      },
      "numeric_bounds": {
        "entry_period": [20, 100],
        "exit_period": [10, 40],
        "stop_atr": [1.5, 4.0],
        "max_hold_bars": [24, 72]
      },
      "cost_gate": {
        "max_median_cost_r": 0.25
      }
    }
  }
}
```

---

## 3. Cryptographic Spec Verification Protocol

Whenever `config/lab_spec.json` is registered or amended:
1. Compute the bitwise SHA-256 hash of `config/lab_spec.json`:
   ```bash
   certutil -hashfile config/lab_spec.json SHA256
   ```
2. Mirror the file to `backend/config/lab_spec.json`.
3. Update `LAB_SPEC_SHA256` in `backend/app/lab/__init__.py`.
4. Run `backend/.venv/Scripts/python.exe backend/scripts/test_lab_no_real_orders.py`.

---

## 4. Research Trial Counter Invariant

Rule 0.6 requires that every strategy variant and every spawned neighbour increments the global research trial counter:
```python
# In backend/app/lab/storage.py
storage.increment_trials_count()
```
This guarantees that multiple-testing deflated Sharpe ratio ($DSR$) calculations and expected false positive metrics ($E[FP] = 0.05 \times N_{T2/T3}$) honestly reflect the full trial history.

---

## 5. Verification Checklist for New Strategies

Before landing any new strategy:
1. [ ] Implement class in `backend/app/lab/strategies/lXX_strategy_name.py`.
2. [ ] Register class in `backend/app/lab/strategies/__init__.py`.
3. [ ] Register parameters and bounds in `config/lab_spec.json`.
4. [ ] Verify truncation invariance in `backend/scripts/test_lab_lookahead.py`.
5. [ ] Verify geometry validation in `backend/scripts/test_lab_geometry.py`.
6. [ ] Replay 12 months historical closed bars to seed T0 chart labelled `BACKFILL`.
7. [ ] Confirm start tier is strictly `T0` (zero forward evidence counted from backfill).
