"""
Counter-Trend Hypothesis

Logic: Buy after 3 consecutive down days, exit after 2 up days or 5 bar max hold.
Expected: Works in mean-reverting regimes, dies in trends.
"""

from hypotheses.base import Hypothesis, TradeIntent, IntentType
from state.market_state import MarketState
from state.position_state import PositionState
from clock.clock import Clock
from market.regime import MarketRegime


class CounterTrendHypothesis(Hypothesis):
    """Buy after consecutive down days, exit on reversal."""
    
    def __init__(self, down_days: int = 3, up_days_exit: int = 2, max_hold: int = 5, **kwargs):
        self.down_days = down_days
        self.up_days_exit = up_days_exit
        self.max_hold = max_hold
        self._bars_held = 0
        self._consecutive_up = 0
    
    @property
    def hypothesis_id(self) -> str:
        return "counter_trend"
    
    @property
    def allowed_regimes(self) -> list[MarketRegime]:
        # Only allow in Choppy or Neutral markets. 
        # Fails in strong trends (Bull/Bear).
        return [MarketRegime.CHOPPY, MarketRegime.NEUTRAL]
    
    @property
    def parameters(self) -> dict:
        return {
            "down_days": self.down_days,
            "up_days_exit": self.up_days_exit,
            "max_hold": self.max_hold
        }
    
    def on_bar(
        self, 
        market_state: MarketState, 
        position_state: PositionState, 
        clock: Clock
    ) -> TradeIntent | None:
        
        bar = market_state.current_bar()
        is_up_bar = bar.close > bar.open
        
        if position_state.has_position:
            self._bars_held += 1
            
            if is_up_bar:
                self._consecutive_up += 1
            else:
                self._consecutive_up = 0
            
            # Exit conditions
            if self._bars_held >= self.max_hold or self._consecutive_up >= self.up_days_exit:
                self._bars_held = 0
                self._consecutive_up = 0
                return TradeIntent(type=IntentType.CLOSE, size=1.0)
                
            return None
        else:
            self._bars_held = 0
            self._consecutive_up = 0
            
            # Check for N consecutive down bars
            if market_state.bar_count() < self.down_days:
                return None
                
            history = market_state.get_bars(self.down_days)
            if len(history) < self.down_days:
                return None
                
            all_down = all(b.close < b.open for b in history)
            
            if all_down:
                return TradeIntent(type=IntentType.BUY, size=1.0)
                
            return None
