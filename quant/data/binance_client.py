"""
Binance Futures REST API client for historical data.

Fetches OHLCV (with taker buy/sell volumes), funding rates, and open interest.
No authentication required for read-only historical data.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

from quant.config import get_binance_config, BinanceAPIConfig

logger = logging.getLogger(__name__)


class BinanceClient:
    """Client for Binance Futures REST API (read-only historical data)."""

    # Binance rate limit: 2400 weight/min. Klines = 2 weight each.
    _MIN_REQUEST_INTERVAL = 0.1  # 100ms between requests

    def __init__(self, config: Optional[BinanceAPIConfig] = None) -> None:
        self._cfg = config if config else get_binance_config()
        self._last_request_time: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._MIN_REQUEST_INTERVAL:
            time.sleep(self._MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, params: dict) -> dict | list:
        self._throttle()
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # OHLCV with taker buy/sell volumes
    # ------------------------------------------------------------------
    def fetch_historical(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: Optional[str] = None,
        interval: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical klines (OHLCV + taker volumes).

        Binance kline response fields:
        [open_time, open, high, low, close, volume, close_time,
         quote_volume, trades, taker_buy_base_vol, taker_buy_quote_vol, ignore]

        Returns:
            DataFrame with columns: open, high, low, close, volume,
            taker_buy_volume, taker_sell_volume
            and a UTC DatetimeIndex named 'timestamp'.
        """
        symbol = symbol or self._cfg.symbol
        interval = interval or self._cfg.interval
        url = f"{self._cfg.base_url}/fapi/v1/klines"

        start_ms = int(date_from.timestamp() * 1000)
        end_ms = int(date_to.timestamp() * 1000)
        all_frames: list[pd.DataFrame] = []

        while start_ms < end_ms:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": self._cfg.max_bars_per_request,
            }

            data = self._get(url, params)
            if not data:
                break

            chunk = self._parse_klines(data)
            all_frames.append(chunk)

            # Move cursor past last bar
            last_close_time = int(data[-1][6])  # close_time in ms
            start_ms = last_close_time + 1

            logger.info(
                "Fetched %d bars up to %s (%d total)",
                len(chunk),
                chunk.index[-1],
                sum(len(f) for f in all_frames),
            )

        if not all_frames:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume",
                         "taker_buy_volume", "taker_sell_volume"]
            )

        df = pd.concat(all_frames)
        df = df[~df.index.duplicated(keep="first")]
        df = df.sort_index()

        # Trim to exact requested range
        ts_from = pd.Timestamp(date_from).tz_localize("UTC") if date_from.tzinfo is None else pd.Timestamp(date_from)
        ts_to = pd.Timestamp(date_to).tz_localize("UTC") if date_to.tzinfo is None else pd.Timestamp(date_to)
        df = df[df.index >= ts_from]
        df = df[df.index <= ts_to]

        return df

    @staticmethod
    def _parse_klines(data: list) -> pd.DataFrame:
        records = []
        for k in data:
            ts = pd.Timestamp(int(k[0]), unit="ms", tz="UTC")
            vol = float(k[5])
            taker_buy = float(k[9])
            records.append({
                "timestamp": ts,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": vol,
                "taker_buy_volume": taker_buy,
                "taker_sell_volume": vol - taker_buy,
            })
        df = pd.DataFrame(records)
        return df.set_index("timestamp")

    # ------------------------------------------------------------------
    # Funding rates (8H intervals, forward-filled to match kline freq)
    # ------------------------------------------------------------------
    def fetch_funding_rates(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical funding rates.

        Returns:
            DataFrame with 'funding_rate' column and UTC DatetimeIndex.
            Rates are at 8H intervals (00:00, 08:00, 16:00 UTC).
        """
        symbol = symbol or self._cfg.symbol
        url = f"{self._cfg.base_url}/fapi/v1/fundingRate"

        start_ms = int(date_from.timestamp() * 1000)
        end_ms = int(date_to.timestamp() * 1000)
        all_records: list[dict] = []

        while start_ms < end_ms:
            params = {
                "symbol": symbol,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1000,
            }
            data = self._get(url, params)
            if not data:
                break

            for item in data:
                all_records.append({
                    "timestamp": pd.Timestamp(int(item["fundingTime"]), unit="ms", tz="UTC"),
                    "funding_rate_raw": float(item["fundingRate"]),
                })

            # Move past last entry
            start_ms = int(data[-1]["fundingTime"]) + 1

            logger.info("Fetched %d funding rate entries", len(all_records))

        if not all_records:
            return pd.DataFrame(columns=["funding_rate_raw"])

        df = pd.DataFrame(all_records).set_index("timestamp")
        df = df[~df.index.duplicated(keep="first")]
        df = df.sort_index()
        return df

    # ------------------------------------------------------------------
    # Open interest (5-min intervals from Binance, resampled to kline freq)
    # ------------------------------------------------------------------
    def fetch_open_interest(
        self,
        date_from: datetime,
        date_to: datetime,
        symbol: Optional[str] = None,
        period: str = "1h",
    ) -> pd.DataFrame:
        """
        Fetch historical open interest.

        Uses /futures/data/openInterestHist (data available from ~2020).

        Returns:
            DataFrame with 'open_interest' column and UTC DatetimeIndex.
        """
        symbol = symbol or self._cfg.symbol
        url = f"{self._cfg.base_url}/futures/data/openInterestHist"

        start_ms = int(date_from.timestamp() * 1000)
        end_ms = int(date_to.timestamp() * 1000)
        all_records: list[dict] = []

        # Binance OI endpoint limits date range to ~30 days per request
        CHUNK_MS = 29 * 24 * 3600 * 1000  # 29 days in ms

        chunk_start = start_ms
        while chunk_start < end_ms:
            chunk_end = min(chunk_start + CHUNK_MS, end_ms)
            cursor = chunk_start

            while cursor < chunk_end:
                params = {
                    "symbol": symbol,
                    "period": period,
                    "startTime": cursor,
                    "endTime": chunk_end,
                    "limit": 500,
                }
                try:
                    data = self._get(url, params)
                except Exception as e:
                    logger.warning("OI fetch failed at %s: %s", cursor, e)
                    data = []

                if not data:
                    break

                for item in data:
                    all_records.append({
                        "timestamp": pd.Timestamp(int(item["timestamp"]), unit="ms", tz="UTC"),
                        "open_interest": float(item["sumOpenInterest"]),
                        "open_interest_value": float(item["sumOpenInterestValue"]),
                    })

                cursor = int(data[-1]["timestamp"]) + 1

            chunk_start = chunk_end + 1
            logger.info("Fetched %d open interest entries so far", len(all_records))

        if not all_records:
            return pd.DataFrame(columns=["open_interest", "open_interest_value"])

        df = pd.DataFrame(all_records).set_index("timestamp")
        df = df[~df.index.duplicated(keep="first")]
        df = df.sort_index()
        return df

    # ------------------------------------------------------------------
    # Merge supplementary data into OHLCV
    # ------------------------------------------------------------------
    @staticmethod
    def merge_supplementary(
        ohlcv: pd.DataFrame,
        funding: pd.DataFrame,
        oi: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Left-join funding rates and open interest onto OHLCV by timestamp.

        Funding rates (8H) are forward-filled to 1H resolution.
        Open interest is joined directly (already 1H).
        """
        result = ohlcv.copy()

        # Merge funding rates (forward-fill since 8H -> 1H)
        if not funding.empty:
            result = result.join(funding, how="left")
            result["funding_rate_raw"] = result["funding_rate_raw"].ffill()

        # Merge open interest
        if not oi.empty:
            result = result.join(oi, how="left")
            result["open_interest"] = result["open_interest"].ffill()
            result["open_interest_value"] = result["open_interest_value"].ffill()

        return result
