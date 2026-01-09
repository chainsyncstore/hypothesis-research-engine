"""
Volatility Breakout Hypothesis

Logic: Buy when today's range exceeds 1.5x ATR(10), exit after fixed hold period.
Expected: Performs in high-vol, dies in chop.
"""

from hypotheses.base import Hypothesis, TradeIntent, IntentType
from state.market_state import MarketState
from state.position_state import PositionState
from clock.clock import Clock


class VolatilityBreakoutHypothesis(Hypothesis):
    """Buy on volatility expansion, hold for fixed period."""
    
    def __init__(self, atr_period: int = 10, breakout_mult: float = 1.5, hold_bars: int = 5, **kwargs):
        self.atr_period = atr_period
        self.breakout_mult = breakout_mult
        self.hold_bars = hold_bars
        self._bars_held = 0
    
    @property
    def hypothesis_id(self) -> str:
        return "volatility_breakout"
    
    @property
    def parameters(self) -> dict:
        return {
            "atr_period": self.atr_period,
            "breakout_mult": self.breakout_mult,
            "hold_bars": self.hold_bars
        }
    
    def on_bar(
        self, 
        market_state: MarketState, 
        position_state: PositionState, 
        clock: Clock
    ) -> TradeIntent | None:
        
        # Need enough history for ATR
        if market_state.bar_count() < self.atr_period:
            return None
            
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
            
            # Calculate ATR
            history = market_state.get_bars(self.atr_period)
            if len(history) < self.atr_period:
                return None
                
            atr = sum(b.high - b.low for b in history) / len(history)
            
            # Today's range
            today_range = bar.high - bar.low
            
            # Entry: Volatility breakout
            if today_range > atr * self.breakout_mult:
                return TradeIntent(type=IntentType.BUY, size=1.0)
                
            return None
