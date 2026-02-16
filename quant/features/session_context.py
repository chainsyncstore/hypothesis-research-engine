"""
Session-relative context features.

Captures where we are within the trading session — proximity to session
extremes and elapsed time drive end-of-session flows and breakout patterns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute session context features.

    Features (3):
        - session_elapsed_pct:    Fraction of trading session elapsed (0→1)
                                  (based on 08:00–21:00 UTC window = 780 min)
        - dist_from_session_high: (close - session_high) / ATR_14
                                  Negative = below high; near 0 = breakout zone
        - dist_from_session_low:  (close - session_low) / ATR_14
                                  Positive = above low; near 0 = support zone

    Args:
        df: OHLCV DataFrame with UTC DatetimeIndex and 'high', 'low', 'close' columns.

    Returns:
        DataFrame with session context feature columns appended.
    """
    out = df.copy()
    idx = df.index

    # --- Session elapsed percentage ---
    # Session runs 08:00–21:00 UTC = 780 minutes
    session_start_hour = 8
    session_length_minutes = 780.0
    minutes_since_start = (idx.hour - session_start_hour) * 60 + idx.minute
    out["session_elapsed_pct"] = np.clip(minutes_since_start / session_length_minutes, 0.0, 1.0)

    # --- Session high/low tracking ---
    # Create a session ID (date) to group bars within the same session
    session_date = idx.date

    # Compute expanding high/low within each session day
    out["_session_date"] = session_date
    session_high = out.groupby("_session_date")["high"].expanding().max().droplevel(0)
    session_low = out.groupby("_session_date")["low"].expanding().min().droplevel(0)

    # ATR for normalization (use pre-computed if available, else compute)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_14 = tr.rolling(window=14).mean()
    safe_atr = atr_14.replace(0, np.nan).ffill().fillna(1e-8)

    # --- Distance from session high ---
    out["dist_from_session_high"] = (close - session_high) / safe_atr

    # --- Distance from session low ---
    out["dist_from_session_low"] = (close - session_low) / safe_atr

    # Cleanup temp column
    out.drop(columns=["_session_date"], inplace=True)

    return out
