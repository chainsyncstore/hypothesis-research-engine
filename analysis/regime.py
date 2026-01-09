"""
Market Regime Classification.

Deterministic, rules-based classification of market states.
"""

from enum import Enum
import pandas as pd
import numpy as np


class MarketRegime(Enum):
    """Enumeration of market regimes."""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOL = "HIGH_VOL"
    LOW_VOL = "LOW_VOL"
    UNDEFINED = "UNDEFINED"


class RegimeClassifier:
    """
    Classifies market regimes based on price history.
    
    Rules must be deterministic and causal (only past data).
    """
    
    def __init__(self, high_vol_threshold_annualized: float = 0.20):
        """
        Initialize classifier.
        
        Args:
            high_vol_threshold_annualized: Volatility threshold (default 20%)
        """
        self._vol_threshold = high_vol_threshold_annualized
        
    def classify_trend(self, prices: pd.Series, window: int = 50) -> MarketRegime:
        """
        Classify trend based on simple moving average relationship.
        
        Rule:
            - Price > SMA(window) * 1.02 -> TRENDING_UP
            - Price < SMA(window) * 0.98 -> TRENDING_DOWN
            - Else -> SIDEWAYS
        """
        if len(prices) < window:
            return MarketRegime.UNDEFINED
            
        sma = prices.rolling(window=window).mean().iloc[-1]
        current_price = prices.iloc[-1]
        
        if current_price > sma * 1.02:
            return MarketRegime.TRENDING_UP
        elif current_price < sma * 0.98:
            return MarketRegime.TRENDING_DOWN
        else:
            return MarketRegime.SIDEWAYS

    def classify_volatility(self, returns: pd.Series, window: int = 20) -> MarketRegime:
        """
        Classify volatility based on annualized rolling std dev.
        
        Rule:
            - Ann. Vol > Threshold -> HIGH_VOL
            - Ann. Vol <= Threshold -> LOW_VOL
        """
        if len(returns) < window:
            return MarketRegime.UNDEFINED
            
        # Annualize assuming daily bars (252)
        # Note: input should be percentage returns
        vol = returns.rolling(window=window).std().iloc[-1] * np.sqrt(252)
        
        if vol > self._vol_threshold:
            return MarketRegime.HIGH_VOL
        else:
            return MarketRegime.LOW_VOL
