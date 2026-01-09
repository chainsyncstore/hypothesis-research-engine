import logging
from typing import List, Dict, Optional
from datetime import datetime

from data.schemas import Bar
from hypotheses.base import TradeIntent, IntentType
from execution.simulator import ExecutionSimulator
from execution.cost_model import CostModel, CostSide
from state.market_state import MarketState
from state.position_state import PositionState, PositionSide
from portfolio.models import PortfolioState, PortfolioAllocation
from portfolio.ensemble import Ensemble
from portfolio.risk import RiskRule
from clock.clock import Clock

logger = logging.getLogger(__name__)

class MetaExecutionSimulator(ExecutionSimulator):
    """
    Simulator that interprets intent.size as absolute UNITS (shares/contracts).
    Used for rebalancing meta-portfolio.
    """
    def _execute_entry(
        self,
        side: PositionSide,
        execution_bar: Bar,
        decision: object, # QueuedDecision
        position_state: PositionState,
        size: float
    ) -> Optional[object]:
        # Size here is treated as UNITS
        target_units = size
        if target_units <= 0:
            return None
            
        # Check capital
        base_price = execution_bar.open
        cost_side = CostSide.BUY if side == PositionSide.LONG else CostSide.SELL
        effective_price = self._cost_model.apply_costs(base_price, cost_side)
        
        required_capital = target_units * effective_price
        
        if required_capital > self._available_capital:
            # Clip to available
            if effective_price > 0:
                target_units = self._available_capital / effective_price
                required_capital = target_units * effective_price
            else:
                target_units = 0
                required_capital = 0
            
        total_cost = self._cost_model.calculate_cost_amount(
            base_price, target_units, cost_side
        )
        
        position_state.open_position(
            side=side,
            entry_price=effective_price,
            size=target_units,
            entry_timestamp=execution_bar.timestamp,
            entry_capital=required_capital
        )
        
        self._available_capital -= required_capital
        
        from execution.simulator import CompletedTrade
        
        trade = CompletedTrade(
            trade_type="ENTRY",
            side=side.value,
            execution_price=effective_price,
            size=target_units,
            execution_timestamp=execution_bar.timestamp,
            decision_timestamp=decision.decision_timestamp,
            cost_bps=self._cost_model.get_total_cost_bps(),
            total_cost=total_cost
        )
        self._completed_trades.append(trade)
        return trade

class MetaPortfolioEngine:
    """
    Orchestrates Dual-Track Simulation:
    1. Shadow Track: Simulates individual hypotheses (Virtual PnL).
    2. Meta Track: Simulates weighted net portfolio (Real PnL).
    """
    def __init__(
        self,
        ensemble: Ensemble,
        initial_capital: float,
        cost_model: CostModel,
        risk_rules: List[RiskRule] = None,
        decay_check_interval: int = 0
    ):
        self.ensemble = ensemble
        self.initial_capital = initial_capital
        self.cost_model = cost_model
        self.risk_rules = risk_rules or []
        self.decay_check_interval = decay_check_interval
        
        # 1. Shadow Track Initialization
        # We give each shadow sim a hypothetical capital (e.g. 1M) just to track % returns and positions accurately.
        # It doesn't affect the Meta capital.
        SHADOW_CAP = 1_000_000.0 
        self.shadow_simulators: Dict[str, ExecutionSimulator] = {}
        self.shadow_position_states: Dict[str, PositionState] = {}
        
        for h in ensemble.hypotheses:
            hid = h.hypothesis_id
            self.shadow_simulators[hid] = ExecutionSimulator(cost_model, SHADOW_CAP)
            self.shadow_position_states[hid] = PositionState()
            
        # 2. Meta Track Initialization
        self.meta_simulator = MetaExecutionSimulator(cost_model, initial_capital)
        self.meta_position_state = PositionState()
        
        # Globals
        self.clock = Clock()
        # Shared Market State
        # Must be large enough for Regime Detection (SMA200 requires >200 bars)
        self.market_state = MarketState(lookback_window=300) 

    def run(self, bars: List[Bar]) -> List[PortfolioState]:
        history: List[PortfolioState] = []
        peak_equity = self.initial_capital
        
        # Keep track of shadow equity curves for decay calculation
        shadow_equity_curves: Dict[str, List[float]] = {h.hypothesis_id: [] for h in self.ensemble.hypotheses}
        
        for bar_idx, bar in enumerate(bars):
            self.clock.set_time(bar.timestamp)
            self.market_state.update(bar)
            
            # --- Decay Check ---
            if self.decay_check_interval > 0 and bar_idx > 0 and bar_idx % self.decay_check_interval == 0:
                self._check_decay(shadow_equity_curves)
            
            # --- A. Shadow Track Execution ---
            
            # 1. Generate Intents from Hypotheses
            shadow_intents: Dict[str, TradeIntent] = {}
            for h in self.ensemble.hypotheses:
                intent = h.on_bar(
                    self.market_state,
                    self.shadow_position_states[h.hypothesis_id],
                    self.clock
                )
                if intent:
                    shadow_intents[h.hypothesis_id] = intent
                    
            # 2. Execute in Shadow Simulators
            from engine.decision_queue import QueuedDecision
            for h in self.ensemble.hypotheses:
                hid = h.hypothesis_id
                if hid in shadow_intents:
                    decision = QueuedDecision(
                        intent=shadow_intents[hid],
                        decision_timestamp=bar.timestamp,
                        decision_bar_index=bar_idx
                    )
                    self.shadow_simulators[hid].execute_decisions(
                        [decision], bar, self.shadow_position_states[hid]
                    )

            # --- B. Meta Track Execution ---
            
            # 3. Calculate Target Net Exposure
            # Regime Gating: If regime mismatch, exclude from Net Exposure.
            from market.regime import RegimeClassifier
            
            # Note: Ideally instantiated in __init__, but quick fix here or add to __init__
            if not hasattr(self, 'regime_classifier'):
                 self.regime_classifier = RegimeClassifier()
                 
            current_regime = self.regime_classifier.classify(self.market_state)
            
            net_exposure_target = 0.0
            
            for h in self.ensemble.hypotheses:
                hid = h.hypothesis_id
                
                # Check Regime
                if h.allowed_regimes and current_regime not in h.allowed_regimes:
                    # Gated!
                    # We continue tracking shadow performance, but contribution to Meta Portfolio is 0.
                    continue
                    
                weight = self.ensemble.weights.get(hid, 0.0)
                pos_state = self.shadow_position_states[hid]
                
                sign = 0.0
                if pos_state.has_position:
                    if pos_state.position.side == PositionSide.LONG:
                        sign = 1.0
                    else:
                        sign = -1.0
                
                net_exposure_target += (weight * sign)
            
            # 4. Determine Meta-Turn
            # If Target != Current Meta Exposure, we need to trade.
            
            current_meta_exposure = 0.0
            if self.meta_position_state.has_position:
                pos = self.meta_position_state.position
                sign = 1.0 if pos.side == PositionSide.LONG else -1.0
                # Exposure is relative to Capital?
                # In this simplified model, we treat the Meta Simulator as a single instrument trader
                # scaling position size by Target Exposure * Capital.
                
                # Check current size relative to capital?
                # This is tricky because price fluctuates.
                # Let's track "Target Size in Units".
                pass
            
            # IMPLEMENTATION SHORTCUT for C3 MVP:
            # Instead of continuous rebalancing (high transaction costs), 
            # we execute logic:
            # - Calculate desired position size in units: 
            #   (NetExposure * CurrentEquity) / Price
            
            curr_equity = self.meta_simulator.get_total_capital(bar.open, self.meta_position_state)
            target_value = net_exposure_target * curr_equity
            target_units = int(target_value / bar.open) # Integer shares
            
            current_units = 0
            if self.meta_position_state.has_position:
                pos = self.meta_position_state.position
                current_units = pos.size if pos.side == PositionSide.LONG else -pos.size
            
            diff_units = target_units - current_units
            
            meta_intent = None
            if diff_units > 0:
                # Buy
                meta_intent = TradeIntent(type=IntentType.BUY, size=abs(diff_units)) # Size is usually ratio? 
                # Wait, ExecutionSimulator uses logic: "Size=1.0" means ???
                # Simulator _execute_entry uses: position_size = capital_to_deploy / effective_price
                # It assumes intent.size is meaningless? Or wait.
                
                # Let's check Simulator._execute_entry again.
                # `position_size = capital_to_deploy / effective_price`
                # And `capital_to_deploy = self._available_capital`
                # The simulator implementation I viewed earlier was VERY simple: ALWAYS ALL IN.
                
                # CRITICAL: The Standard ExecutionSimulator is "All In".
                # It is NOT suitable for partial Meta-Portfolio rebalancing.
                # I need a "TargetPositionSimulator" or modify current one.
                
                pass 
                
            # Determine target value and units
            curr_equity = self.meta_simulator.get_total_capital(bar.open, self.meta_position_state)
            target_value = abs(net_exposure_target) * curr_equity
            
            # Floor to integer units (shares)
            target_units = 0
            if bar.open > 0:
                target_units = int(target_value / bar.open)
                
            # Determine target side
            target_side = PositionSide.LONG if net_exposure_target > 0 else PositionSide.SHORT
            if target_units == 0:
                target_side = None # Flat

            # Current State
            current_units = 0
            current_side = None
            if self.meta_position_state.has_position:
                pos = self.meta_position_state.position
                current_side = pos.side
                current_units = pos.size
            
            # Rebalancing Logic (Close & Re-Open Strategy)
            decisions = []
            
            # Case 1: Switch Side or Go Flat
            if current_side and (current_side != target_side or target_units == 0):
                # Close existing
                decisions.append(QueuedDecision(
                    intent=TradeIntent(type=IntentType.CLOSE, size=1.0),
                    decision_timestamp=bar.timestamp,
                    decision_bar_index=bar_idx
                ))
                current_units = 0
                current_side = None
            
            # Case 2: Size Change (Same Side)
            if current_side == target_side and current_side is not None:
                if current_units != target_units:
                    # Close & Reopen (Simplest safe implementation)
                    decisions.append(QueuedDecision(
                        intent=TradeIntent(type=IntentType.CLOSE, size=1.0),
                        decision_timestamp=bar.timestamp,
                        decision_bar_index=bar_idx
                    ))
                    current_units = 0
            
            # Case 3: Open Target (if not already there)
            if target_units > 0 and current_units == 0:
                intent_type = IntentType.BUY if target_side == PositionSide.LONG else IntentType.SELL
                # Note: SELL intent usually means Short Entry in this engine, check Simulator
                # Simulator: BUY -> LONG, SELL -> SHORT. Correct.
                
                decisions.append(QueuedDecision(
                    intent=TradeIntent(type=intent_type, size=target_units), # Size is UNITS for MetaSim
                    decision_timestamp=bar.timestamp,
                    decision_bar_index=bar_idx
                ))
            
            # Execute Meta Decisions
            if decisions:
                self.meta_simulator.execute_decisions(decisions, bar, self.meta_position_state)
                
            # --- C. Snapshot ---
            # Create snapshot...
            snapshot = self._create_snapshot(bar, peak_equity)
            history.append(snapshot)
            
            # Update peak equity
            if snapshot.total_capital > peak_equity:
                peak_equity = snapshot.total_capital
                
            # Update Shadow Equity Curves
            for hid, alloc in snapshot.allocations.items():
                if hid != "META_PORTFOLIO":
                    shadow_equity_curves[hid].append(alloc.allocated_capital)

        return history

    def _check_decay(self, equity_curves: Dict[str, List[float]]):
        """
        Check for decay based on equity curves.
        Simple logic for C3 MVP: Max Drawdown > 25% -> DECAYED.
        """
        from promotion.models import HypothesisStatus
        
        for hid, curve in equity_curves.items():
            if not curve:
                continue
            
            # Calculate Max DD
            peak = -1e9
            max_dd = 0.0
            for val in curve:
                if val > peak:
                    peak = val
                dd = (peak - val) / peak if peak > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd
            
            # Threshold: 25%
            if max_dd > 0.25:
                current = self.ensemble.current_statuses.get(hid)
                if current == HypothesisStatus.PROMOTED:
                    logger.info(f"Dynamic Decay Triggered for {hid} (DD={max_dd:.2%}). Demoting to DECAYED.")
                    self.ensemble.set_status(hid, HypothesisStatus.DECAYED)

    def _create_snapshot(self, bar: Bar, peak_equity: float) -> PortfolioState:
        # 1. Shadow Allocations (Virtual)
        allocations = {}
        for hid, sim in self.shadow_simulators.items():
            pos_state = self.shadow_position_states[hid]
            cap = sim.get_total_capital(bar.close, pos_state)
            unreal = pos_state.get_unrealized_pnl(bar.close) if pos_state.has_position else 0.0
            allocations[hid] = PortfolioAllocation(
                hypothesis_id=hid,
                allocated_capital=cap,
                current_position=pos_state.position if pos_state.has_position else None,
                unrealized_pnl=unreal,
                realized_pnl=cap - sim._initial_capital - unreal # Approx
            )
            
        # 2. Meta Portfolio (Real)
        total_cap = self.meta_simulator.get_total_capital(bar.close, self.meta_position_state)
        total_cash = self.meta_simulator.get_available_capital()
        total_unreal = 0.0
        if self.meta_position_state.has_position:
            total_unreal = self.meta_position_state.get_unrealized_pnl(bar.close)
            
        realized = total_cap - self.initial_capital - total_unreal
        
        drawdown = 0.0
        if peak_equity > 0:
            drawdown = max(0.0, (peak_equity - total_cap) / peak_equity * 100.0)

        # For MVP, we reuse PortfolioState. 
        # Ideally we'd add "Meta Position" to it.
        # We can stuff meta position info into a special "META" allocation key?
        allocations["META_PORTFOLIO"] = PortfolioAllocation(
            hypothesis_id="META",
            allocated_capital=total_cap,
            current_position=self.meta_position_state.position if self.meta_position_state.has_position else None,
            unrealized_pnl=total_unreal,
            realized_pnl=realized
        )

        return PortfolioState(
            timestamp=bar.timestamp,
            total_capital=total_cap,
            cash=total_cash,
            allocations=allocations,
            total_realized_pnl=realized,
            total_unrealized_pnl=total_unreal,
            drawdown_pct=drawdown
        )

