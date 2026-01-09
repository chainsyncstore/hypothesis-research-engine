"""
Cost model for transaction costs.

Applies slippage and fees in basis points.
"""

from enum import Enum


class CostSide(str, Enum):
    """Side of the transaction for cost calculation."""
    BUY = "BUY"
    SELL = "SELL"


class CostModel:
    """
    Simple cost model using basis points.
    
    Applies:
    - Transaction costs (commissions/fees)
    - Slippage
    
    All costs are in basis points (1 bps = 0.01% = 0.0001).
    """
    
    def __init__(
        self,
        transaction_cost_bps: float = 10.0,
        slippage_bps: float = 5.0
    ):
        """
        Initialize cost model.
        
        Args:
            transaction_cost_bps: Transaction cost in basis points
            slippage_bps: Slippage in basis points
        """
        self._transaction_cost_bps = transaction_cost_bps
        self._slippage_bps = slippage_bps
    
    def apply_costs(
        self,
        price: float,
        side: CostSide
    ) -> float:
        """
        Apply costs to a price.
        
        For buys: costs increase the effective price
        For sells: costs decrease the effective price
        
        Args:
            price: Base price
            side: Transaction side (BUY or SELL)
            
        Returns:
            Effective price after costs
        """
        # Total cost in basis points
        total_cost_bps = self._transaction_cost_bps + self._slippage_bps
        
        # Convert to decimal
        cost_factor = total_cost_bps / 10000.0
        
        if side == CostSide.BUY:
            # Buying costs increase the price
            return price * (1.0 + cost_factor)
        else:  # SELL
            # Selling costs decrease the price
            return price * (1.0 - cost_factor)
    
    def get_total_cost_bps(self) -> float:
        """
        Get total cost in basis points.
        
        Returns:
            Total cost (transaction + slippage)
        """
        return self._transaction_cost_bps + self._slippage_bps
    
    def get_transaction_cost_bps(self) -> float:
        """Get transaction cost in basis points."""
        return self._transaction_cost_bps
    
    def get_slippage_bps(self) -> float:
        """Get slippage in basis points."""
        return self._slippage_bps
    
    def calculate_cost_amount(
        self,
        price: float,
        size: float,
        side: CostSide
    ) -> float:
        """
        Calculate the total cost amount for a trade.
        
        Args:
            price: Base price
            size: Position size
            side: Transaction side
            
        Returns:
            Total cost amount in currency units
        """
        effective_price = self.apply_costs(price, side)
        cost_per_unit = abs(effective_price - price)
        return cost_per_unit * size
