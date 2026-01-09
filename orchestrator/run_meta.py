import argparse
import logging
from datetime import datetime

from config.settings import get_settings
from config.policies import get_policy
from storage.repositories import EvaluationRepository
from portfolio.meta_engine import MetaPortfolioEngine
from portfolio.ensemble import Ensemble
from portfolio.weighting import EqualWeighting, RobustnessWeighting
from portfolio.risk import MaxDrawdownRule
from data.market_loader import MarketDataLoader
from hypotheses.registry import get_hypothesis
from promotion.models import HypothesisStatus
from execution.cost_model import CostModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Run meta-strategy simulation.")
    parser.add_argument("--policy", required=True, help="Research Policy ID")
    parser.add_argument("--symbol", default="SYNTHETIC", help="Market Symbol")
    parser.add_argument("--data-path", required=True, help="Path to market data CSV")
    parser.add_argument("--capital", type=float, default=100000.0, help="Initial Capital")
    parser.add_argument("--max-drawdown", type=float, default=0.20, help="Max Drawdown Limit")
    parser.add_argument("--weighting", default="equal", choices=["equal", "robustness"], help="Weighting strategy")
    parser.add_argument("--tag", default="META_RUN", help="Meta Run Tag")
    
    args = parser.parse_args()
    
    settings = get_settings()
    repo = EvaluationRepository(settings.database_path)
    policy = get_policy(args.policy)
    
    logger.info(f"Starting Meta-Strategy Simulation for policy {policy.policy_id} on {args.symbol}")
    
    # 1. Fetch Hypotheses
    promoted_ids = repo.get_hypotheses_by_status(
        HypothesisStatus.PROMOTED.value,
        policy_id=policy.policy_id
    )
    
    if not promoted_ids:
        logger.warning("No PROMOTED hypotheses found.")
        return

    logger.info(f"Found {len(promoted_ids)} promoted hypotheses: {promoted_ids}")
    
    hypotheses = []
    for hid in promoted_ids:
        details = repo.get_hypothesis_details(hid)
        params = {}
        if details and 'parameters_json' in details:
            import json
            try:
                params = json.loads(details['parameters_json'])
            except:
                logger.error(f"Failed to load params for {hid}")
        
        h_cls = get_hypothesis(hid)
        hypotheses.append(h_cls(**params))
        
    # 2. Configure Weighting
    weighting_strategy = EqualWeighting()
    if args.weighting == "robustness":
        weighting_strategy = RobustnessWeighting()
        
    ensemble = Ensemble(
        hypotheses=hypotheses,
        weighting_strategy=weighting_strategy,
        repo=repo,
        policy_id=policy.policy_id
    )
    
    logger.info(f"Initial Weights: {ensemble.weights}")
    
    # 3. Load Data
    bars = MarketDataLoader.load_from_csv(args.data_path, symbol=args.symbol)
    if not bars:
        logger.error("No market data found.")
        return
        
    # 4. Init Engine
    cost_model = CostModel(
        transaction_cost_bps=policy.transaction_cost_bps,
        slippage_bps=policy.slippage_bps
    )
    
    risk_rules = [
        MaxDrawdownRule(max_drawdown_pct=args.max_drawdown)
    ]
    
    engine = MetaPortfolioEngine(
        ensemble=ensemble,
        initial_capital=args.capital,
        cost_model=cost_model,
        risk_rules=risk_rules
    )
    
    # 5. Run
    history = engine.run(bars)
    
    # 6. Store
    logger.info(f"Simulation complete. Storing {len(history)} portfolio snapshots...")
    for state in history:
        repo.store_portfolio_evaluation(state, args.tag, policy.policy_id)
        
    final = history[-1]
    logger.info("--- Meta Portfolio Result ---")
    logger.info(f"Final Capital: ${final.total_capital:,.2f}")
    logger.info(f"Return: {((final.total_capital - args.capital) / args.capital * 100):.2f}%")
    logger.info(f"Max Drawdown: {final.drawdown_pct:.2f}%")

if __name__ == "__main__":
    main()
