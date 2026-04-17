from collections import defaultdict
from typing import Any, Callable


EventHandler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event_type: str, payload: Any) -> None:
        for handler in self._handlers.get(event_type, []):
            handler(payload)