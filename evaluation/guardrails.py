"""
Research Guardrails.

Hard rules that prevent self-deception by rejecting hypotheses that fail strict criteria.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from analysis.regime import MarketRegime


class PromotionStatus(Enum):
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"


@dataclass
class GuardrailResult:
    status: PromotionStatus
    rejection_reason: Optional[str] = None


class ResearchGuardrails:
    """Enforces strict criteria for hypothesis promotion."""
    
    def __init__(
        self,
        min_trades: int = 30,
        min_regimes: int = 2,
        max_sharpe_decay_pct: float = 0.50
    ):
        """
        Initialize guardrails.
        
        Args:
            min_trades: Minimum number of trades required
            min_regimes: Minimum number of unique regimes tested
            max_sharpe_decay_pct: Maximum allowed percentage drop in Sharpe (IS vs OS)
        """
        self._min_trades = min_trades
        self._min_regimes = min_regimes
        self._max_sharpe_decay = max_sharpe_decay_pct
        
    def check_min_trades(self, trade_count: int) -> GuardrailResult:
        """Check if enough trades were executed."""
        if trade_count < self._min_trades:
            return GuardrailResult(
                status=PromotionStatus.REJECTED,
                rejection_reason=f"Insufficient trades: {trade_count} < {self._min_trades}"
            )
        return GuardrailResult(status=PromotionStatus.PROMOTED)
        
    def check_regime_coverage(self, regimes_tested: List[MarketRegime]) -> GuardrailResult:
        """Check if hypothesis was tested across enough unique regimes."""
        unique_regimes = set(regimes_tested)
        # Filter out UNDEFINED if present
        if MarketRegime.UNDEFINED in unique_regimes:
            unique_regimes.remove(MarketRegime.UNDEFINED)
            
        count = len(unique_regimes)
        
        if count < self._min_regimes:
            return GuardrailResult(
                status=PromotionStatus.REJECTED,
                rejection_reason=f"Insufficient regime coverage: {count} < {self._min_regimes}"
            )
        return GuardrailResult(status=PromotionStatus.PROMOTED)
        
    def check_sharpe_decay(self, in_sample_sharpe: float, out_sample_sharpe: float) -> GuardrailResult:
        """
        Check if performance decayed too much.
        
        Rule:
            - If IS Sharpe <= 0, REJECT (why promote a loser?)
            - If OS Sharpe < 0, REJECT
            - If Drop > Threshold, REJECT
        """
        if in_sample_sharpe <= 0:
            return GuardrailResult(
                status=PromotionStatus.REJECTED,
                rejection_reason=f"in-sample Sharpe non-positive: {in_sample_sharpe:.2f}"
            )
            
        if out_sample_sharpe < 0:
             return GuardrailResult(
                status=PromotionStatus.REJECTED,
                rejection_reason=f"out-of-sample Sharpe negative: {out_sample_sharpe:.2f}"
            )
            
        drop_pct = (in_sample_sharpe - out_sample_sharpe) / in_sample_sharpe
        
        if drop_pct > self._max_sharpe_decay:
            return GuardrailResult(
                status=PromotionStatus.REJECTED,
                rejection_reason=f"Sharpe decay too high: {drop_pct:.1%} > {self._max_sharpe_decay:.1%}"
            )
            
        return GuardrailResult(status=PromotionStatus.PROMOTED)
        
    def verify_all(
        self,
        trade_count: int,
        regimes_tested: List[MarketRegime],
        in_sample_sharpe: float,
        out_sample_sharpe: float
    ) -> GuardrailResult:
        """Run all checks."""
        # 1. Min Trades
        res = self.check_min_trades(trade_count)
        if res.status == PromotionStatus.REJECTED:
            return res
            
        # 2. Regime Coverage
        res = self.check_regime_coverage(regimes_tested)
        if res.status == PromotionStatus.REJECTED:
            return res
            
        # 3. Sharpe Decay
        res = self.check_sharpe_decay(in_sample_sharpe, out_sample_sharpe)
        if res.status == PromotionStatus.REJECTED:
            return res
            
        return GuardrailResult(status=PromotionStatus.PROMOTED)
