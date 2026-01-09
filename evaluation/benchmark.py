"""
Benchmark comparison.

Provides buy-and-hold benchmark for comparison.
"""

from typing import List

from data.schemas import Bar


class BenchmarkCalculator:
    """
    Calculates buy-and-hold benchmark return.
    
    This provides a simple comparison baseline:
    - Buy at first bar close
    - Hold until last bar close
    - Calculate return
    """
    
    @staticmethod
    def calculate_buy_and_hold_return(
        bars: List[Bar],
        initial_capital: float,
        include_costs: bool = False,
        cost_bps: float = 0.0
    ) -> dict:
        """
        Calculate buy-and-hold benchmark.
        
        Args:
            bars: All market bars
            initial_capital: Starting capital
            include_costs: Whether to include transaction costs
            cost_bps: Total cost in basis points (if include_costs=True)
            
        Returns:
            Dictionary with benchmark metrics
        """
        if not bars:
            return {
                "benchmark_return_pct": 0.0,
                "benchmark_final_capital": initial_capital,
                "benchmark_pnl": 0.0
            }
        
        # Entry at first bar close
        entry_price = bars[0].close
        
        # Exit at last bar close
        exit_price = bars[-1].close
        
        # Apply costs if requested
        if include_costs:
            cost_factor = cost_bps / 10000.0
            # Entry costs
            effective_entry = entry_price * (1.0 + cost_factor)
            # Exit costs
            effective_exit = exit_price * (1.0 - cost_factor)
        else:
            effective_entry = entry_price
            effective_exit = exit_price
        
        # Calculate position size
        position_size = initial_capital / effective_entry
        
        # Calculate final value
        final_value = position_size * effective_exit
        
        # Calculate return
        pnl = final_value - initial_capital
        return_pct = (pnl / initial_capital) * 100.0 if initial_capital > 0 else 0.0
        
        return {
            "benchmark_return_pct": return_pct,
            "benchmark_final_capital": final_value,
            "benchmark_pnl": pnl,
            "benchmark_entry_price": effective_entry,
            "benchmark_exit_price": effective_exit,
            "benchmark_position_size": position_size
        }
