from __future__ import annotations

import logging
from collections import defaultdict
from threading import RLock

from visionqc.application.ports.event_bus import EventHandler
from visionqc.domain.events import DomainEvent

logger = logging.getLogger(__name__)


class InProcessEventBus:
    """Thread-safe synchronous event bus for decoupled desktop modules.

    Handlers are isolated: one failing subscriber is logged and does not stop
    delivery to other subscribers. A wildcard subscriber can use ``*``.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        if not event_name.strip():
            raise ValueError("event_name is required")
        with self._lock:
            if handler not in self._handlers[event_name]:
                self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._handlers.get(event_name, [])
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event: DomainEvent) -> None:
        with self._lock:
            handlers = tuple(self._handlers.get(event.name, ())) + tuple(self._handlers.get("*", ()))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler failed for %s", event.name)
