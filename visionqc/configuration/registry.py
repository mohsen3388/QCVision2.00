from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
import numpy as np
from .models import DetectorManifest

DetectorFn = Callable[[np.ndarray, dict], float]

@dataclass(slots=True)
class RegisteredDetector:
    manifest: DetectorManifest
    function: DetectorFn

class DetectorRegistry:
    def __init__(self) -> None:
        self._items: dict[str, RegisteredDetector] = {}
    def register(self, manifest: DetectorManifest, function: DetectorFn, *, replace: bool=False) -> None:
        if manifest.key in self._items and not replace: raise ValueError(f"Detector already registered: {manifest.key}")
        self._items[manifest.key] = RegisteredDetector(manifest, function)
    def register_plugin(self, plugin, *, replace: bool=False) -> None:
        self.register(plugin.manifest, plugin.function, replace=replace)
    def get(self, key: str) -> RegisteredDetector:
        if key not in self._items: raise KeyError(f"Detector not found: {key}")
        return self._items[key]
    def manifests(self) -> list[DetectorManifest]:
        return [x.manifest for x in self._items.values()]
    def execute(self, key: str, frame: np.ndarray, params: dict | None = None) -> float:
        if frame is None or not getattr(frame, "size", 0): raise ValueError("Empty frame")
        value=self.get(key).function(frame, params or {})
        if not np.isfinite(value): raise ValueError(f"Detector returned invalid value: {key}")
        return float(value)

def default_detector_registry() -> DetectorRegistry:
    from visionqc.quality.detectors import all_plugins
    r=DetectorRegistry()
    for plugin in all_plugins(): r.register_plugin(plugin)
    return r
