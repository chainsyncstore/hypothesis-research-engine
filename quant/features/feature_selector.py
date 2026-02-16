"""
Feature importance-based pruning.

Ranks features by mean importance across walk-forward folds and prunes
those that contribute below a cumulative importance threshold.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


def prune_features(
    importance_dict: Dict[str, List[float]],
    cumulative_threshold: float = 0.95,
    min_features: int = 10,
) -> List[str]:
    """
    Select features accounting for the top cumulative_threshold of importance.

    Args:
        importance_dict: Feature name -> list of importance values (one per fold).
        cumulative_threshold: Keep features accounting for this fraction of total
                              importance (default 0.95 = top 95%).
        min_features: Minimum number of features to retain regardless of threshold.

    Returns:
        List of feature names to keep (sorted by importance, descending).
    """
    # Compute mean importance per feature
    mean_importance = {
        feat: float(np.mean(vals))
        for feat, vals in importance_dict.items()
        if len(vals) > 0
    }

    # Sort by importance descending
    sorted_features = sorted(mean_importance.items(), key=lambda x: x[1], reverse=True)

    if not sorted_features:
        return list(importance_dict.keys())

    total = sum(imp for _, imp in sorted_features)
    if total <= 0:
        return [f for f, _ in sorted_features]

    # Accumulate until threshold is met
    cumulative = 0.0
    selected = []

    for feat, imp in sorted_features:
        selected.append(feat)
        cumulative += imp / total

        if cumulative >= cumulative_threshold and len(selected) >= min_features:
            break

    # Ensure minimum features
    if len(selected) < min_features:
        for feat, _ in sorted_features[len(selected):]:
            selected.append(feat)
            if len(selected) >= min_features:
                break

    n_pruned = len(sorted_features) - len(selected)

    logger.info(
        "Feature pruning: %d → %d features (pruned %d, cumulative importance=%.1f%%)",
        len(sorted_features),
        len(selected),
        n_pruned,
        cumulative * 100,
    )

    # Log pruned features
    pruned = [f for f, _ in sorted_features if f not in selected]
    if pruned:
        logger.info("Pruned features: %s", pruned)

    return selected
