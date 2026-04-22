from __future__ import annotations

import json
from pathlib import Path

from app.models.watchlist import Watchlist, WatchlistItem


class WatchlistService:
    def __init__(self, base_dir: str = "app/data/watchlists") -> None:
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def list_watchlists(self) -> list[str]:
        names = [path.stem for path in self.base_path.glob("*.json")]
        return sorted(names)

    def exists(self, name: str) -> bool:
        return self._get_path(name).exists()

    def load_watchlist(self, name: str) -> Watchlist:
        path = self._get_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Watchlist '{name}' not found")

        data = json.loads(path.read_text(encoding="utf-8"))
        return Watchlist.from_dict(data)

    def save_watchlist(self, watchlist: Watchlist) -> Path:
        path = self._get_path(watchlist.name)
        payload = watchlist.to_dict()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def delete_watchlist(self, name: str) -> None:
        path = self._get_path(name)
        if path.exists():
            path.unlink()

    def create_watchlist(self, name: str, symbols: list[str] | None = None) -> Watchlist:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Watchlist name cannot be empty")

        items = []
        for symbol in symbols or []:
            clean_symbol = symbol.upper().strip()
            if clean_symbol:
                items.append(WatchlistItem(symbol=clean_symbol))

        watchlist = Watchlist(name=clean_name, items=items)
        self.save_watchlist(watchlist)
        return watchlist

    def add_symbol(
        self,
        watchlist_name: str,
        symbol: str,
        thesis: str = "",
        catalyst: str = "",
        note: str = "",
        priority: int = 0,
        manual_override: bool = True,
    ) -> Watchlist:
        watchlist = self.load_watchlist(watchlist_name)
        clean_symbol = symbol.upper().strip()

        if not clean_symbol:
            raise ValueError("Symbol cannot be empty")

        if any(item.symbol == clean_symbol for item in watchlist.items):
            return watchlist

        watchlist.items.append(
            WatchlistItem(
                symbol=clean_symbol,
                source="manual",
                thesis=thesis,
                catalyst=catalyst,
                note=note,
                priority=priority,
                manual_override=manual_override,
            )
        )
        self.save_watchlist(watchlist)
        return watchlist

    def remove_symbol(self, watchlist_name: str, symbol: str) -> Watchlist:
        watchlist = self.load_watchlist(watchlist_name)
        clean_symbol = symbol.upper().strip()

        watchlist.items = [item for item in watchlist.items if item.symbol != clean_symbol]
        self.save_watchlist(watchlist)
        return watchlist

    def upsert_watchlist(self, watchlist: Watchlist) -> Watchlist:
        seen: set[str] = set()
        deduped: list[WatchlistItem] = []

        for item in watchlist.items:
            symbol = item.symbol.upper().strip()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            item.symbol = symbol
            deduped.append(item)

        watchlist.items = deduped
        self.save_watchlist(watchlist)
        return watchlist

    def _get_path(self, name: str) -> Path:
        safe_name = name.strip().replace("/", "_").replace("\\", "_")
        return self.base_path / f"{safe_name}.json"