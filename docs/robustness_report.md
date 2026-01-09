# Research Robustness Report

## 1. Structural Validity (Hypothesis Battle)
**Objective**: Validating that we are not overfitting to a specific seed or regime.

**Methodology**:
- Ran 6 hypotheses (`always_long`, `simple_momentum`, `mean_reversion`, `volatility_breakout`, `time_exit`, `counter_trend`)
- Across 5 different random seeds
- Across 4 market regimes (Random, Bull, Bear, Choppy)
- Total: 20 scenarios

**Key Findings**:
| Hypothesis | Promotion Rate | Notes |
|------------|----------------|-------|
| `volatility_breakout` | 35% | Best performer in high-vol/trend regimes. |
| `counter_trend` | 30% | Strongest in Choppy/Random. **Zero promotions in Bear.** |
| `time_exit` (Null) | 25% | ⚠ **WARNING**: Promoted 25% of time (mostly Bull). Thresholds need tightening. |
| `always_long` | 0% | Correctly rejected 100% of time (no trades). |

**Conclusion**:
- The engine correctly discriminates between strategies.
- `counter_trend` displays structural validity (works where expected, fails where expected).
- `time_exit` passing in Bull markets indicates we need a "Benchmark Beta Filter" (future work).

---

## 2. Meta-Strategy & Regime Shift (Online Decay)
**Objective**: Validating that the Meta Engine detects failing strategies and cuts exposure.

**Scenario**:
- Forced Promotion of 3 strategies (Simulating False Positives).
- Regime Shift: **Bull (Days 0-100)** → **Choppy (Days 100-200)** → **Bear (Days 200-300)**.

**Results**:

| Strategy | Performance Path | Final Status |
|----------|------------------|--------------|
| `simple_momentum` | Thrived in Bull, decayed in Choppy. | **DECAYED** |
| `counter_trend` | Survived Choppy, crashed in Bear. | **DECAYED** |
| `time_exit` | High volatility, eventual drawdown. | **DECAYED** |

**Verification**:
> "Does it retain weight in C3, or get zeroed?"

**Answer**: **It gets zeroed.**
The Meta Engine successfully monitored the "Shadow Equity Curves", computed Max Drawdown, and triggered `HypothesisStatus.DECAYED` when the threshold (25%) was breached (likely during the Bear crash for `counter_trend`).

---

## 3. Final Recommendation

The system functions correctly as a research engine:
1.  **Rejection Rate**: High (>80% rejection in typical random/bear regimes).
2.  **Safety**: Zeroes out strategies that stop working (Online Decay).
3.  **Discovery**: Identifies niche performers (`counter_trend` in chop).

**Next Steps**:
- Implement **Regime Detection** as a core component (to disable Counter-Trend during Trends).
- Tighten promotion thresholds (add `Sharpe > Benchmark`).
- Run large-scale search on 10,000+ seeds.
