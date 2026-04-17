from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from app.models.market import Bar, Quote


class AlpacaMarketDataClient:
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        trading_base_url: str,
        data_feed: str = "iex",
        data_base_url: str = "https://data.alpaca.markets",
        timeout: int = 20,
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.trading_base_url = trading_base_url.rstrip("/")
        self.data_base_url = data_base_url.rstrip("/")
        self.data_feed = data_feed
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update(
            {
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
                "Accept": "application/json",
            }
        )

    def get_latest_quote(self, symbol: str) -> Quote:
        url = f"{self.data_base_url}/v2/stocks/{symbol.upper()}/quotes/latest"
        params = {"feed": self.data_feed}

        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        payload = response.json()
        quote_data = payload.get("quote")

        if not isinstance(quote_data, dict):
            raise ValueError(f"No latest quote returned for {symbol}")

        return self._normalize_quote(symbol.upper(), quote_data)

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start: str | None = None,
        end: str | None = None,
        adjustment: str = "raw",
    ) -> list[Bar]:
        bars = self._fetch_bars(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            start=start,
            end=end,
            adjustment=adjustment,
        )

        if bars:
            return bars

        retry_start, retry_end = self._default_time_window(timeframe, limit)

        bars = self._fetch_bars(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            start=retry_start,
            end=retry_end,
            adjustment=adjustment,
        )

        return bars

    def _fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        start: str | None,
        end: str | None,
        adjustment: str,
    ) -> list[Bar]:
        url = f"{self.data_base_url}/v2/stocks/{symbol.upper()}/bars"
        params: dict[str, Any] = {
            "timeframe": timeframe,
            "limit": limit,
            "adjustment": adjustment,
            "feed": self.data_feed,
        }

        if start:
            params["start"] = start
        if end:
            params["end"] = end

        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        payload = response.json()
        bars_data = payload.get("bars")

        if not isinstance(bars_data, list):
            return []

        normalized: list[Bar] = []
        for item in bars_data:
            if not isinstance(item, dict):
                continue
            try:
                normalized.append(self._normalize_bar(symbol.upper(), timeframe, item))
            except (KeyError, TypeError, ValueError):
                continue

        return normalized

    def _default_time_window(self, timeframe: str, limit: int) -> tuple[str, str]:
        end_dt = datetime.now(timezone.utc)

        tf = timeframe.lower()
        if tf == "1day":
            start_dt = end_dt - timedelta(days=max(limit * 3, 30))
        elif tf == "5min":
            start_dt = end_dt - timedelta(days=10)
        elif tf == "15min":
            start_dt = end_dt - timedelta(days=15)
        else:
            start_dt = end_dt - timedelta(days=30)

        return start_dt.isoformat(), end_dt.isoformat()

    def test_connection(self) -> dict[str, Any]:
        url = f"{self.trading_base_url}/v2/account"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid account response from Alpaca")

        return payload

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        if not value:
            raise ValueError("Missing timestamp")

        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")

        return datetime.fromisoformat(value).astimezone(timezone.utc)

    def _normalize_quote(self, symbol: str, payload: dict[str, Any]) -> Quote:
        return Quote(
            symbol=symbol,
            bid=float(payload.get("bp", 0.0)),
            ask=float(payload.get("ap", 0.0)),
            bid_size=payload.get("bs"),
            ask_size=payload.get("as"),
            ts=self._parse_timestamp(payload["t"]),
            source="alpaca",
        )

    def _normalize_bar(self, symbol: str, timeframe: str, payload: dict[str, Any]) -> Bar:
        return Bar(
            symbol=symbol,
            timeframe=timeframe,
            open=float(payload.get("o", 0.0)),
            high=float(payload.get("h", 0.0)),
            low=float(payload.get("l", 0.0)),
            close=float(payload.get("c", 0.0)),
            volume=int(payload.get("v", 0)),
            ts=self._parse_timestamp(payload["t"]),
            source="alpaca",
        )