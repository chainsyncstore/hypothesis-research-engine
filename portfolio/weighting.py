from typing import Protocol, Dict, List
from hypotheses.base import Hypothesis
from storage.repositories import EvaluationRepository
from promotion.models import HypothesisStatus

class WeightingStrategy(Protocol):
    """
    Protocol for determining capital allocation weights for hypotheses.
    """
    def calculate_weights(
        self, 
        hypotheses: List[Hypothesis], 
        repo: EvaluationRepository,
        policy_id: str,
        current_statuses: Dict[str, HypothesisStatus]
    ) -> Dict[str, float]:
        """
        Calculate weights for a list of hypotheses.
        
        Returns:
            Dictionary mapping hypothesis_id to weight (0.0 to 1.0).
            Sum of weights should ideally be <= 1.0 (unless leverage logic handled elsewhere).
        """
        ...

class EqualWeighting:
    """
    Allocates equal capital to all hypotheses.
    """
    def calculate_weights(
        self, 
        hypotheses: List[Hypothesis], 
        repo: EvaluationRepository,
        policy_id: str,
        current_statuses: Dict[str, HypothesisStatus]
    ) -> Dict[str, float]:
        # Filter for ACTIVE/PROMOTED only
        active = [h for h in hypotheses if current_statuses.get(h.hypothesis_id) == HypothesisStatus.PROMOTED]
        
        if not active:
            return {h.hypothesis_id: 0.0 for h in hypotheses}
        
        count = len(active)
        weight = 1.0 / count
        
        weights = {h.hypothesis_id: 0.0 for h in hypotheses}
        for h in active:
            weights[h.hypothesis_id] = weight
            
        return weights

class RobustnessWeighting:
    """
    Allocates capital based on robustness score (e.g. Sharpe Ratio).
    """
    def calculate_weights(
        self, 
        hypotheses: List[Hypothesis], 
        repo: EvaluationRepository,
        policy_id: str,
        current_statuses: Dict[str, HypothesisStatus]
    ) -> Dict[str, float]:
        weights = {h.hypothesis_id: 0.0 for h in hypotheses}
        
        # Filter for ACTIVE/PROMOTED only
        active = [h for h in hypotheses if current_statuses.get(h.hypothesis_id) == HypothesisStatus.PROMOTED]
        
        if not active:
            return weights
        
        scores = {}
        total_score = 0.0
        
        for h in active:
            # Fetch latest evaluation to get Sharpe
            # Note: We might want a "Robustness Score" pre-calculated in DB, 
            # but for C3 MVP we use latest Sharpe.
            # Using get_latest_evaluation for this policy context
            eval_record = repo.get_latest_evaluation(h.hypothesis_id, policy_id=policy_id)
            
            sharpe = 0.0
            if eval_record:
                sharpe = eval_record.get('sharpe_ratio', 0.0) or 0.0
            
            # Floor at 0 for weighting (don't allocate to negative Sharpe)
            score = max(0.0, sharpe)
            scores[h.hypothesis_id] = score
            total_score += score
            
        if total_score > 0:
            for hid, score in scores.items():
                weights[hid] = score / total_score
        else:
            # Fallback to equal weight among ACTIVE if no positive scores
            eq_weights = EqualWeighting().calculate_weights(hypotheses, repo, policy_id, current_statuses)
            return eq_weights
            
        return weights
