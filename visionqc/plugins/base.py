from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from visionqc.platform.container import ServiceContainer


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    plugin_id: str
    name: str
    version: str
    industry: str = "Core"


class VisionQCPlugin(ABC):
    metadata: PluginMetadata

    @abstractmethod
    def register(self, container: ServiceContainer) -> None:
        """Register plugin services without importing or changing UI internals."""
