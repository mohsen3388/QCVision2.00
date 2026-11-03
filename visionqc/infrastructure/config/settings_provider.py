from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from visionqc.core.settings import load_settings, save_settings


class JsonSettingsProvider:
    """Infrastructure adapter around the legacy JSON settings store."""

    def load(self) -> dict[str, Any]:
        return deepcopy(load_settings())

    def save(self, values: Mapping[str, Any]) -> None:
        save_settings(dict(values))
