from enum import Enum
from dataclasses import dataclass
from typing import List

class HypothesisStatus(str, Enum):
    DRAFT = "DRAFT"
    EVALUATED = "EVALUATED"
    PROMOTED = "PROMOTED"
    FROZEN = "FROZEN"
    DECAYED = "DECAYED"
    RETIRED = "RETIRED"

@dataclass
class PromotionDecision:
    hypothesis_id: str
    batch_id: str
    decision: HypothesisStatus
    reasons: List[str]
