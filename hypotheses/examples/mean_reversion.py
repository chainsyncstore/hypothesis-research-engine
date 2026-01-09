"""
Mean Reversion Hypothesis - Actively trades for demo purposes.

Strategy: 
- Buy when price drops 2% below 10-day SMA
- Sell when price rises 2% above 10-day SMA
- Hold for max 5 bars then exit
"""

from hypotheses.base import Hypothesis, TradeIntent, IntentType
from state.market_state import MarketState
from state.position_state import PositionState
from clock.clock import Clock


class MeanReversionHypothesis(Hypothesis):
    """Simple mean reversion strategy that actively trades."""
    
    def __init__(self, lookback: int = 10, threshold: float = 0.02, max_hold: int = 5, **kwargs):
        self.lookback = lookback
        self.threshold = threshold
        self.max_hold = max_hold
        self._bars_held = 0
    
    @property
    def hypothesis_id(self) -> str:
        return "mean_reversion"
    
    @property
    def parameters(self) -> dict:
        return {
            "lookback": self.lookback,
            "threshold": self.threshold,
            "max_hold": self.max_hold
        }
    
    def on_bar(
        self, 
        market_state: MarketState, 
        position_state: PositionState, 
        clock: Clock
    ) -> TradeIntent | None:
        
        # Need enough history
        if market_state.bar_count() < self.lookback:
            return None
            
        # Calculate SMA
        closes = market_state.get_close_prices(self.lookback)
        if len(closes) < self.lookback:
            return None
            
        sma = sum(closes) / len(closes)
        current_price = market_state.get_current_price()
        
        # Calculate deviation
        deviation = (current_price - sma) / sma
        
        if position_state.has_position:
            self._bars_held += 1
            
            # Exit conditions
            # 1. Price reverted above SMA (for long) or below SMA (for short)
            # 2. Max hold time reached
            if self._bars_held >= self.max_hold:
                self._bars_held = 0
                return TradeIntent(type=IntentType.CLOSE, size=1.0)
            
            # Exit on mean reversion
            if deviation > 0:  # Price above SMA - close long
                self._bars_held = 0
                return TradeIntent(type=IntentType.CLOSE, size=1.0)
                
            return None
        else:
            self._bars_held = 0
            
            # Entry condition: Price significantly below SMA
            if deviation < -self.threshold:
                return TradeIntent(type=IntentType.BUY, size=1.0)
                
            return None
