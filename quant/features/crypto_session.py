"""
Crypto session context features.

Replaces FX session windows with crypto-specific time anchors:
funding settlement times, regional session overlaps, and
time-of-week effects.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute crypto session context features.

    Requires: DatetimeIndex (UTC).
    """
    out = df.copy()
    idx = out.index

    # Hours until next funding settlement (every 8H: 00:00, 08:00, 16:00 UTC)
    hour_in_cycle = idx.hour % 8
    minute_in_cycle = idx.minute
    hours_to_funding = 8 - hour_in_cycle - (minute_in_cycle / 60.0)
    out["hours_to_funding"] = hours_to_funding

    # Cyclical encoding of hours to funding
    out["hours_to_funding_sin"] = np.sin(2 * np.pi * hours_to_funding / 8.0)
    out["hours_to_funding_cos"] = np.cos(2 * np.pi * hours_to_funding / 8.0)

    # Post-funding window: within 2H after settlement
    out["post_funding_window"] = (hour_in_cycle < 2).astype(float)

    # Regional session flags (approximate)
    hour = idx.hour
    out["asia_session"] = ((hour >= 0) & (hour < 8)).astype(float)      # 00-08 UTC
    out["europe_session"] = ((hour >= 8) & (hour < 16)).astype(float)    # 08-16 UTC
    out["us_session"] = ((hour >= 14) & (hour < 22)).astype(float)       # 14-22 UTC

    # Day of week (0=Mon, 6=Sun) — crypto trades 24/7 but weekend volume differs
    out["day_of_week_sin"] = np.sin(2 * np.pi * idx.dayofweek / 7.0)
    out["day_of_week_cos"] = np.cos(2 * np.pi * idx.dayofweek / 7.0)

    return out
