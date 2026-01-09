from dataclasses import dataclass
from typing import List, Optional
import uuid

@dataclass(frozen=True)
class BatchConfig:
    """
    Defines the experimental scope. Immutable once execution begins.
    """
    batch_id: str
    policy_id: str # Explicit Policy ID
    market_symbol: str
    hypotheses: List[str]
    # Data params can stay as they effectively define the "Universe" or "Environment"
    synthetic: bool = False 
    synthetic_bars: Optional[int] = None
    assumed_costs_bps: int = 0

    def __post_init__(self):
        if not self.batch_id:
            object.__setattr__(self, 'batch_id', str(uuid.uuid4())[:8])
            
        if not self.hypotheses:
            raise ValueError("Batch must have at least one hypothesis")

        if not self.policy_id:
            raise ValueError("Batch must have a policy_id")
            
        if self.assumed_costs_bps < 0:
            raise ValueError("assumed_costs_bps cannot be negative.")
            
        if self.synthetic:
            if self.synthetic_bars is None or self.synthetic_bars <= 0:
                 raise ValueError("synthetic_bars must be positive if synthetic is True.")
