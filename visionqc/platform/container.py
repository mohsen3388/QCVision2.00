from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")
Factory = Callable[["ServiceContainer"], Any]


class ServiceContainer:
    """Small dependency-injection container with singleton and factory scopes."""

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, Factory] = {}

    def register_instance(self, key: str, value: Any) -> None:
        self._instances[key] = value

    def register_factory(self, key: str, factory: Factory) -> None:
        self._factories[key] = factory

    def resolve(self, key: str) -> Any:
        if key in self._instances:
            return self._instances[key]
        if key in self._factories:
            return self._factories[key](self)
        raise KeyError(f"Service is not registered: {key}")

    def has(self, key: str) -> bool:
        return key in self._instances or key in self._factories
