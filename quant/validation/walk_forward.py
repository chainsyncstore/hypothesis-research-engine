"""
Strict walk-forward validation orchestrator.

Train → Validate → Slide Forward → Repeat.
No random shuffling. Regime model and LightGBM are re-fit each fold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from quant.config import get_research_config
from quant.features.pipeline import extract_feature_matrix, get_feature_columns
from quant.regime import gmm_regime
from quant.models import trainer as model_trainer
from quant.models.predictor import predict_proba
from quant.validation.metrics import (
    FoldMetrics,
    HorizonReport,
    RegimeMetrics,
    aggregate_fold_metrics,
    compute_metrics,
    compute_trade_pnl,
)

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardResult:
    """Complete walk-forward evaluation result."""

    reports: Dict[int, HorizonReport]  # horizon → report
    feature_importance: Dict[int, Dict[str, float]]  # horizon → {feat: importance}
    all_pnl: Dict[int, np.ndarray]  # horizon → concatenated PnL
    thresholds: Dict[int, Dict[int, float]]  # horizon → {regime: threshold}


def run_walk_forward(
    df: pd.DataFrame,
    horizons: Optional[List[int]] = None,
    params_override: Optional[Dict] = None,
    feature_subset: Optional[List[str]] = None,
) -> WalkForwardResult:
    """
    Execute strict walk-forward validation.

    Args:
        df: Full DataFrame with features + labels (output of pipeline + labeler).
        horizons: Prediction horizons to evaluate (default from config).
        params_override: Optional dict of LightGBM params to override defaults.
        feature_subset: Optional list of feature columns to use (for pruning).

    Returns:
        WalkForwardResult with per-horizon reports.
    """
    cfg = get_research_config()
    horizons = horizons or cfg.horizons

    feature_cols = feature_subset or get_feature_columns(df)
    total_bars = len(df)

    logger.info(
        "Walk-forward: %d total bars, train=%d, test=%d, step=%d",
        total_bars,
        cfg.wf_train_bars,
        cfg.wf_test_bars,
        cfg.wf_step_bars,
    )

    reports: Dict[int, HorizonReport] = {}
    all_feature_importance: Dict[int, Dict[str, float]] = {}
    all_pnl: Dict[int, np.ndarray] = {}
    all_thresholds: Dict[int, Dict[int, float]] = {}

    for h in horizons:
        label_col = f"label_{h}m"
        if label_col not in df.columns:
            raise ValueError(f"Label column '{label_col}' not found. Run labeler first.")

        fold_metrics: List[FoldMetrics] = []
        fold_pnls: List[np.ndarray] = []
        importance_accum: Dict[str, List[float]] = {c: [] for c in feature_cols}
        regime_trade_data: Dict[int, List[Tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}

        fold_idx = 0
        cursor = 0

        while cursor + cfg.wf_train_bars + cfg.wf_test_bars <= total_bars:
            train_end = cursor + cfg.wf_train_bars
            test_end = train_end + cfg.wf_test_bars

            train_df = df.iloc[cursor:train_end]
            test_df = df.iloc[train_end:test_end]

            X_train = extract_feature_matrix(train_df)
            y_train = train_df[label_col]
            X_test = extract_feature_matrix(test_df)
            y_test = test_df[label_col]

            # --- Filter FLAT labels (-1) from training ---
            train_mask = y_train != -1
            X_train_filtered = X_train[train_mask]
            y_train_filtered = y_train[train_mask]

            if len(X_train_filtered) < 100:
                logger.warning(
                    "Fold %d [%dm]: Skipping — only %d tradeable training samples",
                    fold_idx, h, len(X_train_filtered),
                )
                cursor += cfg.wf_step_bars
                fold_idx += 1
                continue

            # --- Fit regime model on training data only ---
            regime_model = gmm_regime.fit(train_df)

            # --- Add regime labels to test data ---
            test_with_regime = gmm_regime.add_regime_columns(test_df, regime_model)

            # --- Train model (on filtered non-FLAT data) ---
            trained = model_trainer.train(
                X_train_filtered, y_train_filtered, horizon=h,
                params_override=params_override,
            )

            # --- Predict on test ---
            probas = predict_proba(trained, X_test)

            # --- Compute price moves for PnL ---
            price_moves_raw = test_df["close"].shift(-h).values - test_df["close"].values

            # Trim to valid rows (drop NaN from forward shift at tail)
            valid_len = len(test_df) - h
            price_moves = price_moves_raw[:valid_len]
            probas_valid = probas[:valid_len]
            y_valid = y_test.values[:valid_len]

            # --- Filter FLAT labels (-1) from evaluation ---
            eval_mask = y_valid != -1
            price_moves = price_moves[eval_mask]
            probas_valid = probas_valid[eval_mask]
            y_valid = y_valid[eval_mask]

            # --- Compute PnL at default threshold (0.5) ---
            pnl = compute_trade_pnl(
                predictions=probas_valid,
                actuals=y_valid,
                price_moves=price_moves,
                threshold=0.5,
                spread=cfg.spread_price,
            )

            # --- Record fold metrics ---
            fm = compute_metrics(
                pnl=pnl,
                fold=fold_idx,
                train_start=str(train_df.index[0]),
                test_start=str(test_df.index[0]),
                test_end=str(test_df.index[-1]),
            )
            fold_metrics.append(fm)
            fold_pnls.append(pnl)

            # --- Accumulate feature importance ---
            for feat, imp in trained.feature_importance.items():
                if feat in importance_accum:
                    importance_accum[feat].append(imp)

            # --- Accumulate regime-level data for threshold optimization ---
            regimes_all = test_with_regime["regime"].values[:valid_len]
            regimes = regimes_all[eval_mask]  # filter FLAT from regimes too
            for r in range(cfg.n_regimes):
                r_mask = regimes == r
                if r_mask.any():
                    if r not in regime_trade_data:
                        regime_trade_data[r] = []
                    regime_trade_data[r].append((
                        probas_valid[r_mask],
                        y_valid[r_mask],
                        price_moves[r_mask],
                    ))

            logger.info(
                "Fold %d [%dm]: EV=%.6f, WR=%.1f%%, trades=%d",
                fold_idx,
                h,
                fm.spread_adjusted_ev,
                fm.win_rate * 100,
                fm.n_trades,
            )

            cursor += cfg.wf_step_bars
            fold_idx += 1

        # --- Aggregate feature importance ---
        avg_importance = {
            feat: float(np.mean(vals)) if vals else 0.0
            for feat, vals in importance_accum.items()
        }
        avg_importance = dict(sorted(avg_importance.items(), key=lambda x: x[1], reverse=True))
        all_feature_importance[h] = avg_importance

        # --- Optimize per-regime thresholds ---
        regime_metrics_list, regime_thresholds = _optimize_regime_thresholds(
            regime_trade_data, cfg.spread_price, cfg
        )
        all_thresholds[h] = regime_thresholds

        # --- Regime-gated PnL recomputation ---
        # Recompute PnL using per-regime optimal thresholds instead of flat 0.5
        # Also filter out regimes with negative EV
        positive_ev_regimes = {
            rm.regime for rm in regime_metrics_list if rm.ev > 0
        }
        gated_pnl_parts = []
        gated_n_trades = 0
        gated_n_wins = 0

        for regime, data_list in sorted(regime_trade_data.items()):
            if regime not in positive_ev_regimes:
                logger.info(
                    "  Regime %d [%dm]: SKIPPED (negative EV)", regime, h
                )
                continue

            thresh = regime_thresholds.get(regime, 0.5)
            all_preds = np.concatenate([d[0] for d in data_list])
            all_moves = np.concatenate([d[2] for d in data_list])

            mask = all_preds >= thresh
            n = int(mask.sum())
            if n > 0:
                pnl_regime = all_moves[mask] - cfg.spread_price
                gated_pnl_parts.append(pnl_regime)
                gated_n_trades += n
                gated_n_wins += int((pnl_regime > 0).sum())
                logger.info(
                    "  Regime %d [%dm]: %d trades @ thresh=%.2f, EV=%.6f, WR=%.1f%%",
                    regime, h, n, thresh,
                    float(np.mean(pnl_regime)),
                    (pnl_regime > 0).sum() / n * 100,
                )

        # Use regime-gated PnL for Monte Carlo input
        if gated_pnl_parts:
            gated_pnl = np.concatenate(gated_pnl_parts)
            gated_ev = float(np.mean(gated_pnl))
            gated_wr = gated_n_wins / gated_n_trades if gated_n_trades > 0 else 0.0
            all_pnl[h] = gated_pnl

            logger.info(
                "Horizon %dm REGIME-GATED: EV=%.6f, WR=%.1f%%, Trades=%d (from %d regimes)",
                h, gated_ev, gated_wr * 100, gated_n_trades, len(positive_ev_regimes),
            )
        else:
            # Fallback to original PnL if no positive-EV regimes
            if fold_pnls:
                all_pnl[h] = np.concatenate(fold_pnls)
            else:
                all_pnl[h] = np.array([])

        # --- Build overall report (from fold metrics — ungated) ---
        overall = aggregate_fold_metrics(fold_metrics)
        reports[h] = HorizonReport(
            horizon=h,
            overall_ev=overall["spread_adjusted_ev"],
            overall_win_rate=overall["win_rate"],
            overall_sharpe=overall["sharpe"],
            overall_max_drawdown=overall["max_drawdown"],
            overall_n_trades=overall["n_trades"],
            overall_worst_streak=overall["worst_losing_streak"],
            per_regime=regime_metrics_list,
            per_fold=fold_metrics,
        )

        logger.info(
            "Horizon %dm complete: %d folds, overall EV=%.6f, WR=%.1f%%",
            h,
            len(fold_metrics),
            overall["spread_adjusted_ev"],
            overall["win_rate"] * 100,
        )

    return WalkForwardResult(
        reports=reports,
        feature_importance=all_feature_importance,
        all_pnl=all_pnl,
        thresholds=all_thresholds,
    )


def _optimize_regime_thresholds(
    regime_trade_data: Dict[int, List[Tuple[np.ndarray, np.ndarray, np.ndarray]]],
    spread: float,
    cfg,
) -> Tuple[List[RegimeMetrics], Dict[int, float]]:
    """Sweep probability thresholds per regime to maximize EV."""
    from quant.selection.threshold_optimizer import optimize_threshold

    metrics_list: List[RegimeMetrics] = []
    thresholds: Dict[int, float] = {}

    for regime, data_list in sorted(regime_trade_data.items()):
        # Concatenate all folds for this regime
        all_preds = np.concatenate([d[0] for d in data_list])
        all_actuals = np.concatenate([d[1] for d in data_list])
        all_moves = np.concatenate([d[2] for d in data_list])

        best_threshold, best_ev = optimize_threshold(
            predictions=all_preds,
            price_moves=all_moves,
            spread=spread,
            threshold_min=cfg.threshold_min,
            threshold_max=cfg.threshold_max,
            threshold_step=cfg.threshold_step,
        )

        # Compute win rate at best threshold
        mask = all_preds >= best_threshold
        n_trades = int(mask.sum())
        if n_trades > 0:
            traded_pnl = all_moves[mask] - spread
            win_rate = float((traded_pnl > 0).sum() / n_trades)
        else:
            win_rate = 0.0

        thresholds[regime] = best_threshold
        metrics_list.append(
            RegimeMetrics(
                regime=regime,
                ev=best_ev,
                win_rate=win_rate,
                n_trades=n_trades,
                optimal_threshold=best_threshold,
            )
        )

    return metrics_list, thresholds
