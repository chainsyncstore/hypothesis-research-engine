"""
Live signal generator for paper trading.

Loads production models and periodically fetches new bars from Capital.com.
For each new bar, it computes features, detects the current regime,
and generates a BUY/SELL/HOLD signal based on regime-gated thresholds.

Usage:
    python -m quant.live.signal_generator --model-dir models/production/model_XXXXXX
    python -m quant.live.signal_generator --model-dir models/production/model_XXXXXX --once
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from quant.config import get_research_config
from quant.data.capital_client import CapitalClient
from quant.data.session_filter import filter_sessions
from quant.features.pipeline import build_features, get_feature_columns
from quant.models.trainer import TrainedModel, load_model
from quant.models.predictor import predict_proba
from quant.regime import gmm_regime
from quant.regime.gmm_regime import RegimeModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# How many recent bars we need for feature computation (warmup)
WARMUP_BARS = 200
# Lookback window for regime model context
REGIME_LOOKBACK = 500


class SignalGenerator:
    """Live signal generator with regime-gated trading."""

    def __init__(self, model_dir: Path):
        self.model_dir = model_dir

        # Load config
        with open(model_dir / "config.json") as f:
            self.config = json.load(f)

        self.horizon: int = self.config["horizon"]
        self.feature_cols: list = self.config["feature_cols"]
        self.spread: float = self.config["spread"]

        # Parse regime config
        self.regime_config: Dict[int, dict] = {
            int(k): v for k, v in self.config["regime_config"].items()
        }
        self.regime_thresholds: Dict[int, float] = {
            int(k): v for k, v in self.config["regime_thresholds"].items()
        }
        self.tradeable_regimes = {
            r for r, cfg in self.regime_config.items() if cfg.get("tradeable", False)
        }

        # Load models
        logger.info("Loading LightGBM model from %s", model_dir)
        self.model: TrainedModel = load_model(model_dir / "lgbm_model.joblib")

        logger.info("Loading regime model from %s", model_dir)
        self.regime_model: RegimeModel = gmm_regime.load_model(
            model_dir / "regime_model.joblib"
        )

        # API client
        self.client = CapitalClient()
        self._authenticated = False

        # Signal log
        self.signal_log: list = []

        logger.info(
            "Signal generator initialized: horizon=%dm, tradeable regimes=%s",
            self.horizon,
            self.tradeable_regimes,
        )
        for r, cfg in sorted(self.regime_config.items()):
            status = "✅ TRADE" if cfg["tradeable"] else "❌ SKIP"
            logger.info(
                "  Regime %d: %s | thresh=%.2f | EV=%.6f | WR=%.1f%%",
                r, status, cfg["threshold"], cfg["ev"], cfg["win_rate"] * 100,
            )

    def _ensure_authenticated(self) -> None:
        if not self._authenticated:
            self.client.authenticate()
            self._authenticated = True

    def fetch_recent_bars(self, n_bars: int = 600) -> pd.DataFrame:
        """Fetch recent bars for feature computation."""
        self._ensure_authenticated()
        date_to = datetime.now(timezone.utc)
        # Fetch extra bars to account for weekends/closures
        date_from = date_to - timedelta(hours=n_bars * 2)

        df = self.client.fetch_historical(date_from, date_to)
        if df.empty:
            raise RuntimeError("No data received from API")

        return df

    def generate_signal(self, df: pd.DataFrame) -> dict:
        """
        Generate a trading signal from recent bar data.

        Returns:
            Dict with keys: signal, probability, regime, threshold,
            regime_tradeable, timestamp, close_price
        """
        # Feature engineering
        df_filtered = filter_sessions(df)
        df_features = build_features(df_filtered)
        feature_cols = get_feature_columns(df_features)

        # Verify feature alignment
        missing = set(self.feature_cols) - set(feature_cols)
        if missing:
            logger.warning("Missing features: %s — using available subset", missing)

        # Get the latest bar
        latest = df_features.iloc[[-1]]
        latest_ts = latest.index[0]
        close_price = float(latest["close"].iloc[0])

        # Detect regime
        labels, probas = gmm_regime.predict(self.regime_model, latest)
        current_regime = int(labels[0])
        regime_prob = float(probas[0].max())

        # Check if regime is tradeable
        regime_tradeable = current_regime in self.tradeable_regimes
        threshold = self.regime_thresholds.get(current_regime, 0.5)

        # Generate prediction
        X = latest[self.feature_cols]
        proba = float(predict_proba(self.model, X)[0])

        # Determine signal
        if not regime_tradeable:
            signal_type = "HOLD"
            reason = f"Regime {current_regime} has negative historical EV"
        elif proba >= threshold:
            signal_type = "BUY"
            reason = f"P(up)={proba:.3f} >= thresh={threshold:.2f}"
        elif proba <= (1 - threshold):
            signal_type = "SELL"
            reason = f"P(up)={proba:.3f} <= {1-threshold:.2f}"
        else:
            signal_type = "HOLD"
            reason = f"P(up)={proba:.3f} below threshold {threshold:.2f}"

        result = {
            "timestamp": str(latest_ts),
            "close_price": close_price,
            "signal": signal_type,
            "probability": round(proba, 4),
            "regime": current_regime,
            "regime_probability": round(regime_prob, 4),
            "regime_tradeable": regime_tradeable,
            "threshold": threshold,
            "reason": reason,
            "horizon": self.horizon,
        }

        self.signal_log.append(result)
        return result

    def run_once(self) -> dict:
        """Fetch data and generate a single signal."""
        logger.info("Fetching recent bars...")
        df = self.fetch_recent_bars()
        logger.info("Received %d bars, latest: %s", len(df), df.index[-1])

        signal = self.generate_signal(df)

        # Pretty print
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal["signal"], "❓")
        logger.info(
            "%s SIGNAL: %s @ %.5f | P(up)=%.3f | Regime=%d (%s) | Thresh=%.2f",
            emoji,
            signal["signal"],
            signal["close_price"],
            signal["probability"],
            signal["regime"],
            "tradeable" if signal["regime_tradeable"] else "SKIP",
            signal["threshold"],
        )
        logger.info("  Reason: %s", signal["reason"])

        return signal

    def run_loop(self, interval_seconds: int = 60) -> None:
        """
        Run continuous signal generation loop.

        Args:
            interval_seconds: Seconds between signal checks (default: 60 = 1 bar).
        """
        logger.info(
            "Starting signal loop (interval=%ds). Press Ctrl+C to stop.",
            interval_seconds,
        )

        running = True

        def stop_handler(signum, frame):
            nonlocal running
            running = False
            logger.info("Stopping signal loop...")

        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGTERM, stop_handler)

        while running:
            try:
                result = self.run_once()

                # Save signal log periodically
                if len(self.signal_log) % 10 == 0:
                    self._save_log()

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Signal generation error: %s", e)
                self._authenticated = False  # Force re-auth

            if running:
                time.sleep(interval_seconds)

        self._save_log()
        logger.info("Signal loop stopped. %d signals generated.", len(self.signal_log))

    def _save_log(self) -> None:
        """Save signal log to disk."""
        log_path = self.model_dir / "signal_log.json"
        with open(log_path, "w") as f:
            json.dump(self.signal_log, f, indent=2)
        logger.info("Signal log saved: %s (%d entries)", log_path, len(self.signal_log))


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Signal Generator")
    parser.add_argument(
        "--model-dir",
        type=str,
        required=True,
        help="Path to production model directory",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate a single signal and exit",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between signals (default: 60)",
    )
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        logger.error("Model directory not found: %s", model_dir)
        sys.exit(1)

    gen = SignalGenerator(model_dir)

    if args.once:
        gen.run_once()
    else:
        gen.run_loop(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
