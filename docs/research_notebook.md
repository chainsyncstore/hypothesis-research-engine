# Research Notebook

> "The goal is not to find strategies that work. The goal is to find strategies that *survive*."

---

## Hypothesis Log

### H1: Always Long (Buy & Hold)
- **ID**: `always_long`
- **Logic**: Enter long on first bar, never exit
- **Status**: ⚠️ REJECTED (No trades to evaluate)
- **Notes**: 
  - Serves as a benchmark, not a tradeable strategy
  - Produces 0 closed trades → fails guardrails
  - Expected behavior: Should match buy-and-hold return

---

### H2: Simple Momentum
- **ID**: `simple_momentum`  
- **Logic**: Buy on any up-bar (close > open), exit after 3 bars
- **Status**: 🟢 PROMOTED
- **Sharpe**: 1.25 (demo data)
- **Decay Checks**: 0/N survived
- **Notes**:
  - Extremely naive momentum signal
  - High trade frequency = high transaction cost sensitivity
  - Hypothesis: Will decay when tested on real volatility

---

### H3: Mean Reversion (Pullback)
- **ID**: `mean_reversion`
- **Logic**: Buy when price drops 2% below 10-day SMA, exit on mean reversion or after 5 bars
- **Status**: ⚪ CANDIDATE (Pending evaluation)
- **Notes**:
  - Classic counter-trend approach
  - Expects to fail in trending markets
  - Need regime filtering

---

### H4: Volatility Breakout
- **ID**: `volatility_breakout`
- **Logic**: Buy when today's range exceeds 1.5× ATR(10), exit after fixed hold
- **Status**: ⚪ CANDIDATE
- **Notes**:
  - Attempts to catch expansion moves
  - Hypothesis: Performs well in high-vol, dies in chop

---

### H5: Time-Based Exit (Control / Null Hypothesis)
- **ID**: `time_exit`
- **Logic**: Enter every 7th bar (pseudo-random), exit after exactly 5 bars
- **Status**: ⚪ CANDIDATE
- **Notes**:
  - This is a NULL HYPOTHESIS - should have ~0 edge
  - If this passes promotion, thresholds are too loose
  - Critical for research validation

---

### H6: Counter-Trend
- **ID**: `counter_trend`
- **Logic**: Buy after 3 consecutive down days, exit after 2 up days or 5 bar max hold
- **Status**: ⚪ CANDIDATE
- **Notes**:
  - Classic "buy the dip" strategy
  - Expected to work in ranging markets
  - Expected to fail in strong trends

---

## Decay History

| Hypothesis | Promoted Date | Decay Date | Reason | Final Sharpe |
|------------|---------------|------------|--------|--------------|
| always_long | 2026-01-08 | - | N/A (Benchmark) | - |
| simple_momentum | 2026-01-08 | - | Active | 1.25 |

---

## Regime Performance Matrix

| Hypothesis | Bull | Bear | Sideways | High Vol | Low Vol |
|------------|------|------|----------|----------|---------|
| always_long | ✓ | ✗ | ~ | ~ | ~ |
| simple_momentum | ? | ? | ? | ? | ? |
| mean_reversion | ? | ? | ? | ? | ? |

---

## Research Lessons Learned

### 2026-01-08: Initial System Build
- Walk-forward with 252/63 train/test windows
- Transaction costs: 5 bps + 5 bps slippage
- Guardrails: Min 10 trades, Sharpe > 0.5, DD < 25%

### Key Insight
> Most hypotheses should fail. If everything passes, your thresholds are too loose.

---

## Next Steps

1. [ ] Implement `volatility_breakout` hypothesis
2. [ ] Implement `time_exit` hypothesis (control)
3. [ ] Run full batch on 5 years of synthetic data
4. [ ] Analyze decay patterns
5. [ ] Test meta-portfolio netting benefits

---

## Methodology Notes

### Walk-Forward Validation
- **Train Window**: 252 bars (1 year)
- **Test Window**: 63 bars (1 quarter)
- **Step Size**: 63 bars (rolling quarterly)

### Promotion Thresholds (WF_V1 Policy)
- Min Sharpe: 0.5
- Min Return: 5%
- Max Drawdown: 25%
- Min Trades: 10

### Decay Thresholds
- Sharpe decay > 30% from promotion → DECAYED
- Max DD breach → DECAYED
- 3 consecutive negative windows → DECAYED

---

*Last Updated: 2026-01-08*
