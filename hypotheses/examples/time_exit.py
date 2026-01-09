"""
Time-Based Exit Hypothesis (Control/Null Hypothesis)

Logic: Enter randomly (every 7th bar), exit after exactly N bars.
Expected: Should have ~0 edge. If this passes, thresholds are too loose.
This is a proper null hypothesis for research validation.
"""

from hypotheses.base import Hypothesis, TradeIntent, IntentType
from state.market_state import MarketState
from state.position_state import PositionState
from clock.clock import Clock


class TimeExitHypothesis(Hypothesis):
    """Random entry, fixed time exit. Control hypothesis."""
    
    def __init__(self, entry_every_n: int = 7, hold_bars: int = 5, **kwargs):
        self.entry_every_n = entry_every_n
        self.hold_bars = hold_bars
        self._bars_held = 0
        self._bar_count = 0
    
    @property
    def hypothesis_id(self) -> str:
        return "time_exit"
    
    @property
    def parameters(self) -> dict:
        return {
            "entry_every_n": self.entry_every_n,
            "hold_bars": self.hold_bars
        }
    
    def on_bar(
        self, 
        market_state: MarketState, 
        position_state: PositionState, 
        clock: Clock
    ) -> TradeIntent | None:
        
        self._bar_count += 1
        
        if position_state.has_position:
            self._bars_held += 1
            
            # Exit after hold period
            if self._bars_held >= self.hold_bars:
                self._bars_held = 0
                return TradeIntent(type=IntentType.CLOSE, size=1.0)
                
            return None
        else:
            self._bars_held = 0
            
            # Entry: Every N bars (pseudo-random, deterministic)
            if self._bar_count % self.entry_every_n == 0:
                return TradeIntent(type=IntentType.BUY, size=1.0)
                
            return None
