
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

class CostModel(ABC):
    @abstractmethod
    def estimate_cost(self, row: pd.Series) -> float:
        """Estimate execution cost (spread + slippage) in price units."""
        pass

    def fit(self, df: pd.DataFrame):
        """Optional training step for data-driven models."""
        pass

class ConstantCostModel(CostModel):
    def __init__(self, spread: float):
        self.spread = spread

    def estimate_cost(self, row: pd.Series) -> float:
        return self.spread

class PercentageCostModel(CostModel):
    """
    Percentage-based cost model for crypto.

    Cost = close_price * fee_rate * 2 (round trip: entry + exit).
    Optionally scaled by volatility relative to training average.
    """
    def __init__(self, fee_rate: float = 0.0004, vol_col: str = "realized_vol_5", power: float = 0.5):
        self.fee_rate = fee_rate
        self.vol_col = vol_col
        self.power = power
        self.avg_vol = None

    def fit(self, df: pd.DataFrame):
        if self.vol_col in df.columns:
            self.avg_vol = df[self.vol_col].mean()
            if self.avg_vol == 0:
                self.avg_vol = 1e-6

    def estimate_cost(self, row: pd.Series) -> float:
        close = row.get("close", 0.0)
        base_cost = close * self.fee_rate * 2  # round trip

        if self.avg_vol is None:
            return base_cost

        curr_vol = row.get(self.vol_col, self.avg_vol)
        ratio = curr_vol / self.avg_vol
        scaling = max(1.0, ratio ** self.power)
        return base_cost * scaling

class VolatilityAdjustedCostModel(CostModel):
    """
    Estimates spread/slippage based on relative volatility.

    Formula:
        Cost = BaseSpread * max(1.0, (CurrentVol / AverageVol)^power)

    If volatility is below average, cost is BaseSpread (minimum).
    If volatility is 2x average, cost scales up.
    """
    def __init__(self, base_spread: float, vol_col: str = "realized_vol_5", power: float = 1.0):
        self.base_spread = base_spread
        self.vol_col = vol_col
        self.power = power
        self.avg_vol = None

    def fit(self, df: pd.DataFrame):
        if self.vol_col in df.columns:
            self.avg_vol = df[self.vol_col].mean()
            # Safety: avoid zero division
            if self.avg_vol == 0:
                self.avg_vol = 1e-6

    def estimate_cost(self, row: pd.Series) -> float:
        if self.avg_vol is None:
            return self.base_spread

        curr_vol = row.get(self.vol_col, self.avg_vol)
        ratio = curr_vol / self.avg_vol

        # Scale factor: max(1.0, ratio) means we never go below base spread
        scaling = max(1.0, ratio ** self.power)

        return self.base_spread * scaling
