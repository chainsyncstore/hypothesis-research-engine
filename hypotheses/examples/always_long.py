"""
Always Long hypothesis - sanity test example.

Enters a long position on the first bar and never exits.
Used for baseline testing and validation.
"""

from typing import Optional

from clock.clock import Clock
from hypotheses.base import Hypothesis, TradeIntent, IntentType
from state.market_state import MarketState
from state.position_state import PositionState


class AlwaysLongHypothesis(Hypothesis):
    """
    Sanity test hypothesis: Buy once, hold forever.
    
    This hypothesis:
    1. Buys on the first bar (when no position is open)
    2. Holds forever (never closes)
    
    Expected behavior:
    - Should generate exactly 1 trade entry
    - Final PnL should match buy-and-hold benchmark (minus costs)
    """
    
    def __init__(self, **kwargs):
        """Accept any parameters (ignored)."""
        pass

    @property
    def hypothesis_id(self) -> str:
        """Hypothesis identifier."""
        return "always_long"
    
    @property
    def parameters(self) -> dict:
        """Hypothesis parameters."""
        return {
            "strategy": "buy_and_hold",
            "version": "1.0"
        }
    
    def on_bar(
        self,
        market_state: MarketState,
        position_state: PositionState,
        clock: Clock
    ) -> Optional[TradeIntent]:
        """
        Decision logic: Buy if we don't have a position, otherwise hold.
        
        Args:
            market_state: Market state (not used)
            position_state: Position state
            clock: Clock (not used)
            
        Returns:
            BUY intent if no position, None otherwise
        """
        # If we don't have a position, buy
        if not position_state.has_position:
            return TradeIntent(type=IntentType.BUY, size=1.0)
        
        # Otherwise, hold
        return None
