from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Any
import numpy as np
from visionqc.configuration.models import DetectorManifest

@dataclass(slots=True)
class DetectorPlugin:
    manifest: DetectorManifest
    function: Any

class DetectorProvider(Protocol):
    def detectors(self) -> list[DetectorPlugin]: ...
