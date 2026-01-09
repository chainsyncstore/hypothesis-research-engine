"""
Clock module - single source of time truth for the system.

The Clock is the only component that tracks the current simulation time.
No other module should use datetime.now() or similar functions.
"""

from datetime import datetime


class Clock:
    """
    Single source of time truth for the replay engine.
    
    The clock is updated only by the replay engine as it advances through
    market data. This ensures deterministic behavior and prevents accidental
    use of real-world time.
    """
    
    def __init__(self, initial_time: datetime | None = None):
        """
        Initialize the clock.
        
        Args:
            initial_time: Optional initial time. If None, clock starts uninitialized.
        """
        self._current_time: datetime | None = initial_time
        self._is_initialized: bool = initial_time is not None
    
    def set_time(self, new_time: datetime) -> None:
        """
        Set the current time.
        
        This should only be called by the replay engine. Time can only move forward
        or stay the same - it cannot go backwards.
        
        Args:
            new_time: New timestamp
            
        Raises:
            ValueError: If new_time is before current_time (time travel not allowed)
        """
        if self._is_initialized and self._current_time is not None:
            if new_time < self._current_time:
                raise ValueError(
                    f"Time cannot go backwards: {self._current_time} -> {new_time}"
                )
        
        self._current_time = new_time
        self._is_initialized = True
    
    def now(self) -> datetime:
        """
        Get the current simulation time.
        
        Returns:
            Current timestamp
            
        Raises:
            RuntimeError: If clock has not been initialized
        """
        if not self._is_initialized or self._current_time is None:
            raise RuntimeError(
                "Clock has not been initialized. "
                "The replay engine must set the initial time."
            )
        
        return self._current_time
    
    def is_initialized(self) -> bool:
        """
        Check if the clock has been initialized.
        
        Returns:
            True if clock has been set, False otherwise
        """
        return self._is_initialized
    
    def reset(self) -> None:
        """
        Reset the clock to uninitialized state.
        
        This should only be used for testing or when starting a new evaluation run.
        """
        self._current_time = None
        self._is_initialized = False
    
    def __str__(self) -> str:
        """String representation of the clock."""
        if self._is_initialized and self._current_time:
            return f"Clock({self._current_time.isoformat()})"
        return "Clock(uninitialized)"
    
    def __repr__(self) -> str:
        """Developer representation of the clock."""
        return self.__str__()
