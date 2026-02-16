"""
Price microstructure features.

Captures statistical properties of returns that reveal institutional footprints
and regime transitions invisible to simple technical indicators.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute microstructure features.

    Features (3):
        - return_autocorr_5:    5-bar rolling autocorrelation of returns
                                (positive = trending, negative = mean-reverting)
        - return_kurtosis_20:   20-bar excess kurtosis of returns
                                (high = fat tails / regime transition risk)
        - high_low_range_ratio: Current candle range / 20-bar avg range
                                (< 1 = compression, > 1 = expansion)

    Args:
        df: OHLCV DataFrame with 'high', 'low', 'close' columns.

    Returns:
        DataFrame with microstructure feature columns appended.
    """
    out = df.copy()
    close = df["close"]
    returns = close.pct_change()

    # --- Return autocorrelation (5-bar lag-1) ---
    # Rolling correlation of returns with 1-bar lagged returns
    lagged_returns = returns.shift(1)
    out["return_autocorr_5"] = returns.rolling(window=20).corr(lagged_returns)

    # --- Return kurtosis (20-bar) ---
    # Excess kurtosis: 0 = normal, >0 = fat tails
    out["return_kurtosis_20"] = returns.rolling(window=20).kurt()

    # --- High-low range ratio ---
    # Current range normalized by rolling average range
    candle_range = df["high"] - df["low"]
    avg_range = candle_range.rolling(window=20).mean()
    out["high_low_range_ratio"] = np.where(avg_range > 0, candle_range / avg_range, 1.0)

    return out
