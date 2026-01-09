
import pytest
from batch.aggregation import aggregate_results
from batch.models import GuardrailStatus

def test_aggregation_oos_only():
    # Mock run output
    run_output = {
        "mode": "WALK_FORWARD",
        "windows": [
            {
                "window": 1,
                "train_metrics": {"sharpe_ratio": 5.0, "total_return": 100}, # Should be ignored
                "test_metrics": {"sharpe_ratio": 1.0, "total_return": 10, "max_drawdown": 5, "profit_factor": 1.5},
                "market_regime": "TRENDING",
                "decay": None
            },
            {
                "window": 2,
                "train_metrics": {"sharpe_ratio": 5.0}, 
                "test_metrics": {"sharpe_ratio": 2.0, "total_return": 20, "max_drawdown": 2, "profit_factor": 2.5},
                "market_regime": "HIGH_VOL",
                "decay": None
            }
        ]
    }
    
    result = aggregate_results("h1", run_output)
    
    assert result.hypothesis_id == "h1"
    assert result.oos_sharpe == 1.5 # (1.0 + 2.0) / 2
    assert result.oos_mean_return == 15.0 # (10 + 20) / 2
    assert result.oos_max_drawdown == 5.0 # Max of (5, 2)
    assert result.profit_factor == 2.0 # (1.5 + 2.5) / 2
    assert result.regime_coverage_count == 2
    assert result.guardrail_status == GuardrailStatus.PASS

def test_aggregation_missing_mode():
    with pytest.raises(ValueError):
        aggregate_results("h1", {"mode": "SINGLE_PASS"})

def test_aggregation_empty():
    res = aggregate_results("h1", {"mode": "WALK_FORWARD", "windows": []})
    assert res.guardrail_status == GuardrailStatus.FAIL
