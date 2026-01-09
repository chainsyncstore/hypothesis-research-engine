"""
Project settings and configuration.

Centralizes all configurable parameters for the research engine.
"""

from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """
    Project configuration.
    
    All settings are immutable and frozen at runtime.
    """
    model_config = ConfigDict(frozen=True)
    
    # Capital management
    starting_capital: float = Field(default=100000.0, description="Initial account equity")
    
    # Transaction costs (in basis points)
    transaction_cost_bps: float = Field(default=10.0, description="Commission per trade (bps)")
    slippage_bps: float = Field(default=5.0, description="Estimated slippage execution (bps)")
    
    # Execution parameters
    execution_delay_bars: int = Field(
        default=1, 
        ge=1, 
        description="Delay between decision and execution (bars). Must be >= 1 to prevent look-ahead."
    )
    
    # Data parameters
    lookback_window: int = Field(default=100, description="Number of bars to keep in memory")
    
    # Storage
    database_path: str = Field(
        default="results/research.db",
        description="Path to SQLite results database"
    )
    
    def ensure_directories(self):
        """Ensure necessary directories exist."""
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)


_settings = None

def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_directories()
    return _settings
