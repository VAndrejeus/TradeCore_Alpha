from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WatchlistItem:
    symbol: str
    source: str = "manual"
    thesis: str = ""
    catalyst: str = ""
    trigger_min: float | None = None
    trigger_max: float | None = None
    stop_hint: float | None = None
    target_hint: float | None = None
    note: str = ""
    priority: int = 0
    manual_override: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchlistItem":
        return cls(
            symbol=str(data.get("symbol", "")).upper().strip(),
            source=str(data.get("source", "manual")).strip(),
            thesis=str(data.get("thesis", "")).strip(),
            catalyst=str(data.get("catalyst", "")).strip(),
            trigger_min=_to_float_or_none(data.get("trigger_min")),
            trigger_max=_to_float_or_none(data.get("trigger_max")),
            stop_hint=_to_float_or_none(data.get("stop_hint")),
            target_hint=_to_float_or_none(data.get("target_hint")),
            note=str(data.get("note", "")).strip(),
            priority=int(data.get("priority", 0) or 0),
            manual_override=bool(data.get("manual_override", False)),
        )


@dataclass
class Watchlist:
    name: str
    items: list[WatchlistItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Watchlist":
        raw_items = data.get("items", [])
        items = [WatchlistItem.from_dict(item) for item in raw_items if isinstance(item, dict)]
        return cls(
            name=str(data.get("name", "Untitled Watchlist")).strip(),
            items=items,
        )

    def symbols(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        for item in self.items:
            symbol = item.symbol.upper().strip()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            ordered.append(symbol)

        return ordered


def _to_float_or_none(value: Any) -> float | None:
    if value in (None, "", "None"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None