import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

import json
import numpy as np
import pandas as pd

from app.research.dataset import compute_btc_regimes
from app.research.labels import simulate_hybrid_entry_barrier
from app.indicators.engine import compute_indicators
from app.signal_service import detect_regime, score_row

def load_all_cached_4h_data():
    cache_dir = Path("data_cache")
    if not cache_dir.exists():
        cache_dir = Path("backend/data_cache")
    data = {}
    for f in cache_dir.glob("*_4h.parquet"):
        sym = f.name.replace("_4h.parquet", "")
        try:
            df = pd.read_parquet(f)
            if len(df) >= 100:
                data[sym] = df
        except Exception:
            pass
    return data

def main():
    frozen_path = Path("config/frozen_core_long_v1_1.json")
    with open(frozen_path, "r", encoding="utf-8") as f:
        frozen_params = json.load(f)["parameters"]

    data_4h = load_all_cached_4h_data()
    btc_4h = data_4h["BTCUSDT"]
    btc_regimes = compute_btc_regimes(btc_4h)

    # Simulate Always-Long as its OWN sequential series for all symbols:
    # On each symbol, enter at bar 50. Hold until exit. Next bar, enter again.
    al_sequential_trades = []
    for sym, df_raw in list(data_4h.items())[:10]:
        n_bars = len(df_raw)
        curr_bar = 50
        while curr_bar < n_bars - 48:
            t_al = simulate_hybrid_entry_barrier(
                df_raw, curr_bar, direction="long", k_up=2.0, k_dn=1.25, symbol=sym,
                partial_book_r=999.0, partial_book_frac=0.0
            )
            if t_al is None:
                curr_bar += 2
                continue
            t_al["entry_dt"] = df_raw.index[curr_bar]
            al_sequential_trades.append(t_al)
            # Advance to exit bar
            held = t_al["bars_held"]
            curr_bar += max(1, held)

    df_al_seq = pd.DataFrame(al_sequential_trades)
    print(f"Sequential AL trades (10 symbols): {len(df_al_seq)}")
    print(f"Sequential AL Mean R: {df_al_seq['r_net'].mean():.4f} R")

if __name__ == "__main__":
    main()
