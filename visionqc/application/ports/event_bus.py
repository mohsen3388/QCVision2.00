from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from visionqc.domain.events import DomainEvent

EventHandler = Callable[[DomainEvent], None]


class EventBus(Protocol):
    def subscribe(self, event_name: str, handler: EventHandler) -> None: ...
    def unsubscribe(self, event_name: str, handler: EventHandler) -> None: ...
    def publish(self, event: DomainEvent) -> None: ...
