from __future__ import annotations
class ConnectorRegistry:
    def __init__(self): self._items={}
    def register(self,connector): self._items[connector.connector_id]=connector
    def all(self): return list(self._items.values())
    def get(self,connector_id): return self._items[connector_id]
    def health(self): return [item.health() for item in self.all()]
