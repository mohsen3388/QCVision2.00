from __future__ import annotations
from abc import ABC, abstractmethod
from visionqc.domain.enterprise_integration import ConnectorHealth

class BaseConnector(ABC):
    connector_id: str
    name: str
    @abstractmethod
    def health(self) -> ConnectorHealth: ...
    def start(self) -> None: return None
    def stop(self) -> None: return None
