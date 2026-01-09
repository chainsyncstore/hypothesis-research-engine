"""
Bar iterator that yields market data one bar at a time.

Enforces strict chronological ordering and stateful iteration without backtracking.
"""

from typing import Iterator, List

from data.schemas import Bar


class BarIterator:
    """
    Iterator that yields bars one at a time in chronological order.
    
    This enforces sequential access to market data and prevents look-ahead bias
    by making it impossible to access future bars.
    """
    
    def __init__(self, bars: List[Bar]):
        """
        Initialize the iterator.
        
        Args:
            bars: List of bars in chronological order
            
        Raises:
            ValueError: If bars list is empty or not chronologically ordered
        """
        if not bars:
            raise ValueError("Cannot create BarIterator with empty bars list")
        
        # Validate chronological ordering
        for i in range(1, len(bars)):
            if bars[i].timestamp <= bars[i-1].timestamp:
                raise ValueError(
                    f"Bars are not in chronological order at index {i}: "
                    f"{bars[i-1].timestamp} -> {bars[i].timestamp}"
                )
        
        self._bars = bars
        self._current_index = 0
        self._total_bars = len(bars)
    
    def __iter__(self) -> Iterator[Bar]:
        """Return the iterator itself."""
        return self
    
    def __next__(self) -> Bar:
        """
        Get the next bar in sequence.
        
        Returns:
            Next Bar object
            
        Raises:
            StopIteration: When all bars have been consumed
        """
        if self._current_index >= self._total_bars:
            raise StopIteration
        
        bar = self._bars[self._current_index]
        self._current_index += 1
        return bar
    
    def has_next(self) -> bool:
        """
        Check if there are more bars available.
        
        Returns:
            True if more bars are available, False otherwise
        """
        return self._current_index < self._total_bars
    
    def peek(self) -> Bar | None:
        """
        Peek at the next bar without advancing the iterator.
        
        Returns:
            Next Bar object or None if no more bars
        """
        if self.has_next():
            return self._bars[self._current_index]
        return None
    
    def current_position(self) -> int:
        """
        Get the current position in the iteration.
        
        Returns:
            Current index (0-based)
        """
        return self._current_index
    
    def total_bars(self) -> int:
        """
        Get the total number of bars.
        
        Returns:
            Total bar count
        """
        return self._total_bars
    
    def progress(self) -> float:
        """
        Get iteration progress as a percentage.
        
        Returns:
            Progress percentage (0.0 to 100.0)
        """
        if self._total_bars == 0:
            return 100.0
        return (self._current_index / self._total_bars) * 100.0
    
    def reset(self) -> None:
        """
        Reset the iterator to the beginning.
        
        Note: This should only be used for testing/debugging.
        In production, create a new iterator instead.
        """
        self._current_index = 0
