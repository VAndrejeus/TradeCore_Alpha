from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha1
from typing import Any

import requests

from app.models.market import CatalystEvent


class FinnhubNewsClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://finnhub.io/api/v1",
        timeout: int = 20,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def get_company_news(
        self,
        symbol: str,
        lookback_minutes: int = 1440,
    ) -> list[CatalystEvent]:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(minutes=lookback_minutes)

        url = f"{self.base_url}/company-news"
        params = {
            "symbol": symbol.upper(),
            "from": start_dt.date().isoformat(),
            "to": end_dt.date().isoformat(),
            "token": self.api_key,
        }

        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        news_items = response.json()
        events: list[CatalystEvent] = []

        for item in news_items:
            if not isinstance(item, dict):
                continue

            timestamp = item.get("datetime")
            if not timestamp:
                continue

            ts = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            if ts < start_dt:
                continue

            event = self._normalize(symbol.upper(), item)
            events.append(event)

        return events

    def _normalize(self, symbol: str, payload: dict[str, Any]) -> CatalystEvent:
        headline = payload.get("headline", "") or ""
        summary = payload.get("summary", "") or ""

        raw = f"{symbol}|{headline}|{payload.get('datetime', '')}"
        event_id = sha1(raw.encode("utf-8")).hexdigest()

        return CatalystEvent(
            symbol=symbol,
            event_id=event_id,
            ts=datetime.fromtimestamp(payload["datetime"], tz=timezone.utc),
            headline=headline.strip(),
            summary=summary.strip(),
            category="unclassified",
            raw_sentiment=None,
            source="finnhub",
            url=payload.get("url"),
            metadata={
                "related": payload.get("related", ""),
                "source": payload.get("source", ""),
            },
        )