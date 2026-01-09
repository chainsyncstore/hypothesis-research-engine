
import pytest
from batch.batch_config import BatchConfig

def test_batch_config_immutability():
    config = BatchConfig(
        batch_id="test_batch",
        policy_id="TEST_POLICY",
        market_symbol="OPTS",
        hypotheses=["h1", "h2"],
        synthetic=True,
        synthetic_bars=100,
        assumed_costs_bps=5.0
    )
    
    # Check fields
    assert config.batch_id == "test_batch"
    assert config.policy_id == "TEST_POLICY"
    assert config.market_symbol == "OPTS"
    assert config.hypotheses == ["h1", "h2"]
    
    # Validation Failure
    with pytest.raises(ValueError):
        BatchConfig(
            batch_id="b1", policy_id="", market_symbol="m", hypotheses=["h"],
            synthetic=True, synthetic_bars=100, assumed_costs_bps=5.0
        )
        
    # No hypotheses
    with pytest.raises(ValueError):
        BatchConfig(
            batch_id="b1", policy_id="P", market_symbol="X", hypotheses=[],
            synthetic=True, synthetic_bars=10, assumed_costs_bps=0
        )


    # Synthetic without bars
    with pytest.raises(ValueError):
        BatchConfig(
            batch_id="b1", policy_id="P", market_symbol="X", hypotheses=["h"],
            synthetic=True, synthetic_bars=None, assumed_costs_bps=0
        )
