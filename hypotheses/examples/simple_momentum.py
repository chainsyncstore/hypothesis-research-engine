"""
Simple Momentum Hypothesis - Actively trades for demo purposes.

Strategy: 
- Buy on any up bar (close > open), sell after 3 bars
- This ensures trades happen frequently in any market condition
"""

from hypotheses.base import Hypothesis, TradeIntent, IntentType
from state.market_state import MarketState
from state.position_state import PositionState
from clock.clock import Clock


class SimpleMomentumHypothesis(Hypothesis):
    """Simple momentum strategy guaranteed to trade."""
    
    def __init__(self, hold_bars: int = 3, **kwargs):
        self.hold_bars = hold_bars
        self._bars_held = 0
    
    @property
    def hypothesis_id(self) -> str:
        return "simple_momentum"
    
    @property
    def parameters(self) -> dict:
        return {"hold_bars": self.hold_bars}
    
    def on_bar(
        self, 
        market_state: MarketState, 
        position_state: PositionState, 
        clock: Clock
    ) -> TradeIntent | None:
        
        bar = market_state.current_bar()
        
        if position_state.has_position:
            self._bars_held += 1
            
            # Exit after hold period
            if self._bars_held >= self.hold_bars:
                self._bars_held = 0
                return TradeIntent(type=IntentType.CLOSE, size=1.0)
                
            return None
        else:
            self._bars_held = 0
            
            # Entry: Buy on up bar (close > open)
            if bar.close > bar.open:
                return TradeIntent(type=IntentType.BUY, size=1.0)
                
            return None
