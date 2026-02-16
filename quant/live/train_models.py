"""
Train production models and save artifacts for live signal generation.

Trains LightGBM + GMM regime model on the full available dataset,
runs walk-forward to discover regime thresholds, and saves everything
needed for live prediction.

Usage:
    python -m quant.live.train_models [--months 6]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from quant.config import get_research_config, get_path_config
from quant.data.capital_client import CapitalClient
from quant.data.session_filter import filter_sessions
from quant.data.storage import snapshot, validate_ohlcv, load_latest_snapshot
from quant.features.pipeline import build_features, get_feature_columns
from quant.labels.labeler import add_labels
from quant.models import trainer as model_trainer
from quant.models.predictor import predict_proba
from quant.regime import gmm_regime
from quant.validation.walk_forward import run_walk_forward

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Output directory for live model artifacts
MODELS_DIR = Path("models/production")


def train_production_models(
    df: pd.DataFrame,
    horizon: int = 3,
    params_override: Dict | None = None,
) -> Path:
    """
    Train production models and save all artifacts.

    Returns:
        Path to the saved model directory.
    """
    cfg = get_research_config()
    start_time = time.time()

    # --- Feature engineering ---
    logger.info("=" * 60)
    logger.info("STEP 1: Feature Engineering")
    logger.info("=" * 60)
    df_features = build_features(filter_sessions(df))
    feature_cols = get_feature_columns(df_features)
    logger.info("Features (%d): %s", len(feature_cols), feature_cols)

    # --- Labels ---
    logger.info("=" * 60)
    logger.info("STEP 2: Labeling")
    logger.info("=" * 60)
    df_labeled = add_labels(df_features)

    # --- Walk-forward to discover regime thresholds ---
    logger.info("=" * 60)
    logger.info("STEP 3: Walk-Forward (Regime Threshold Discovery)")
    logger.info("=" * 60)
    wf_result = run_walk_forward(df_labeled, params_override=params_override)

    # --- Extract regime config ---
    regime_thresholds = wf_result.thresholds.get(horizon, {})
    regime_report = wf_result.reports.get(horizon)
    positive_ev_regimes = {}
    if regime_report:
        for rm in regime_report.per_regime:
            positive_ev_regimes[rm.regime] = {
                "ev": rm.ev,
                "win_rate": rm.win_rate,
                "n_trades": rm.n_trades,
                "threshold": rm.optimal_threshold,
                "tradeable": rm.ev > 0,
            }

    # --- Train final model on all data ---
    logger.info("=" * 60)
    logger.info("STEP 4: Train Final Production Model")
    logger.info("=" * 60)
    label_col = f"label_{horizon}m"
    X_all = df_labeled[feature_cols]
    y_all = df_labeled[label_col]

    # Filter FLAT
    mask = y_all != -1
    X_train = X_all[mask]
    y_train = y_all[mask]

    trained = model_trainer.train(
        X_train, y_train, horizon=horizon, params_override=params_override
    )

    # --- Train final regime model on all data ---
    regime_model = gmm_regime.fit(df_labeled)

    # --- Save artifacts ---
    logger.info("=" * 60)
    logger.info("STEP 5: Save Artifacts")
    logger.info("=" * 60)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = MODELS_DIR / f"model_{ts}"
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save LightGBM model
    model_path = model_dir / "lgbm_model.joblib"
    model_trainer.save_model(trained, model_path)

    # Save regime model
    regime_path = model_dir / "regime_model.joblib"
    gmm_regime.save_model(regime_model, regime_path)

    # Save config
    config = {
        "horizon": horizon,
        "feature_cols": feature_cols,
        "regime_thresholds": {str(k): v for k, v in regime_thresholds.items()},
        "regime_config": {str(k): v for k, v in positive_ev_regimes.items()},
        "spread": cfg.spread_price,
        "trained_at": ts,
        "training_bars": len(df_labeled),
        "params_override": params_override,
    }
    config_path = model_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, default=str)

    duration = time.time() - start_time
    logger.info("Production model saved to: %s (%.1fs)", model_dir, duration)
    logger.info("Regime config: %s", positive_ev_regimes)

    return model_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train production models")
    parser.add_argument("--months", type=int, default=6, help="Months of history")
    parser.add_argument("--fetch", action="store_true", help="Fetch fresh data")
    parser.add_argument("--horizon", type=int, default=3, help="Prediction horizon")
    args = parser.parse_args()

    get_path_config()

    if args.fetch:
        client = CapitalClient()
        client.authenticate()
        date_to = datetime.now(timezone.utc)
        date_from = date_to - timedelta(days=args.months * 30)
        logger.info("Fetching EURUSD 1m data: %s → %s", date_from, date_to)
        df = client.fetch_historical(date_from, date_to)
        if df.empty:
            logger.error("No data received")
            sys.exit(1)
    else:
        df = load_latest_snapshot()
        if df is None:
            logger.error("No data found. Use --fetch")
            sys.exit(1)

    train_production_models(df, horizon=args.horizon)


if __name__ == "__main__":
    main()
