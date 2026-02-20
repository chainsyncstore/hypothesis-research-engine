"""
Order flow features from Binance taker buy/sell volumes.

Taker buy/sell volumes are included in Binance kline responses —
these represent aggressive orders that cross the spread, providing
direct measurement of buying/selling pressure.
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute order flow features.

    Requires columns: taker_buy_volume, taker_sell_volume, volume.
    """
    out = df.copy()

    buy = out["taker_buy_volume"]
    sell = out["taker_sell_volume"]
    vol = out["volume"]

    # Taker buy ratio: >0.5 means net buying pressure
    out["taker_buy_ratio"] = buy / vol.replace(0, np.nan)

    # Smoothed buy ratio (8-bar MA)
    out["taker_buy_ratio_ma8"] = out["taker_buy_ratio"].rolling(8).mean()

    # Z-score of buy ratio (20-bar window)
    ratio_mean = out["taker_buy_ratio"].rolling(20).mean()
    ratio_std = out["taker_buy_ratio"].rolling(20).std()
    out["taker_buy_ratio_zscore"] = (out["taker_buy_ratio"] - ratio_mean) / ratio_std.replace(0, np.nan)

    # Cumulative delta over 8 bars: signed directional flow
    delta = buy - sell
    out["cumulative_delta_8"] = delta.rolling(8).sum()

    # Normalize cumulative delta by rolling volume
    vol_sum_8 = vol.rolling(8).sum()
    out["cumulative_delta_8_norm"] = out["cumulative_delta_8"] / vol_sum_8.replace(0, np.nan)

    # Flow imbalance: (buy - sell) / (buy + sell)
    total = buy + sell
    imbalance = (buy - sell) / total.replace(0, np.nan)
    out["flow_imbalance_1"] = imbalance
    out["flow_imbalance_4"] = imbalance.rolling(4).mean()

    # Volume-weighted flow: imbalance * volume z-score
    vol_mean = vol.rolling(20).mean()
    vol_std = vol.rolling(20).std()
    vol_zscore = (vol - vol_mean) / vol_std.replace(0, np.nan)
    out["volume_weighted_flow"] = imbalance * vol_zscore

    return out
