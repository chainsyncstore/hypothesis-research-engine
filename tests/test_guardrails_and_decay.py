"""Tests for Research Guardrails and Decay Tracking."""
import pytest
from analysis.regime import MarketRegime
from evaluation.guardrails import ResearchGuardrails, PromotionStatus
from evaluation.walk_forward import DecayTracker

# --- Guardrails Tests ---

def test_guardrails_min_trades():
    """Test minimum trade count enforcement."""
    g = ResearchGuardrails(min_trades=30)
    
    # Reject
    res = g.check_min_trades(29)
    assert res.status == PromotionStatus.REJECTED
    assert "Insufficient trades" in res.rejection_reason
    
    # Pass
    res = g.check_min_trades(30)
    assert res.status == PromotionStatus.PROMOTED

def test_guardrails_regime_coverage():
    """Test regime coverage enforcement."""
    g = ResearchGuardrails(min_regimes=2)
    
    # User tested only Uptrend
    res = g.check_regime_coverage([MarketRegime.TRENDING_UP, MarketRegime.TRENDING_UP])
    assert res.status == PromotionStatus.REJECTED
    assert "Insufficient regime coverage" in res.rejection_reason
    
    # User tested Uptrend and Downtrend
    res = g.check_regime_coverage([MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN])
    assert res.status == PromotionStatus.PROMOTED
    
    # Undefined should be ignored
    res = g.check_regime_coverage([MarketRegime.TRENDING_UP, MarketRegime.UNDEFINED])
    assert res.status == PromotionStatus.REJECTED

def test_guardrails_sharpe_decay():
    """Test Sharpe ratio decay enforcement."""
    g = ResearchGuardrails(max_sharpe_decay_pct=0.50)
    
    # IS Good, OS Good (small drop)
    res = g.check_sharpe_decay(in_sample_sharpe=2.0, out_sample_sharpe=1.5)
    # Drop = (2.0 - 1.5) / 2.0 = 0.25 (25%) < 50%
    assert res.status == PromotionStatus.PROMOTED
    
    # IS Good, OS Bad (large drop)
    res = g.check_sharpe_decay(in_sample_sharpe=2.0, out_sample_sharpe=0.5)
    # Drop = (2.0 - 0.5) / 2.0 = 0.75 (75%) > 50%
    assert res.status == PromotionStatus.REJECTED
    assert "Sharpe decay too high" in res.rejection_reason
    
    # IS Negative (Reject immediately)
    res = g.check_sharpe_decay(in_sample_sharpe=-0.5, out_sample_sharpe=1.0)
    assert res.status == PromotionStatus.REJECTED
    
    # OS Negative (Reject)
    res = g.check_sharpe_decay(in_sample_sharpe=1.0, out_sample_sharpe=-0.1)
    assert res.status == PromotionStatus.REJECTED
    
# --- Decay Tracker Tests ---

def test_decay_tracker():
    """Test decay tracking logic."""
    tracker = DecayTracker(decay_threshold_sharpe=0.50)
    
    # Case 1: Healthy survival
    is_metrics = {"sharpe_ratio": 2.0, "win_rate": 60.0, "max_drawdown": 10.0}
    os_metrics = {"sharpe_ratio": 1.8, "win_rate": 58.0, "max_drawdown": 12.0}
    
    res = tracker.analyze_decay(is_metrics, os_metrics)
    assert res.result_tag == "PASS"
    assert res.sharpe_change == pytest.approx(-0.2)
    assert res.drawdown_change == pytest.approx(2.0) # Increased DD
    
    # Case 2: Decay (Drop > 50%)
    is_metrics = {"sharpe_ratio": 2.0}
    os_metrics = {"sharpe_ratio": 0.5}
    
    res = tracker.analyze_decay(is_metrics, os_metrics)
    assert res.result_tag == "DECAY"
    
    # Case 3: Failure (Negative OS Sharpe)
    is_metrics = {"sharpe_ratio": 2.0}
    os_metrics = {"sharpe_ratio": -0.5}
    
    res = tracker.analyze_decay(is_metrics, os_metrics)
    assert res.result_tag == "FAIL"
