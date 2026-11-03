from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from visionqc.plugins.base import VisionQCPlugin
from visionqc.platform.container import ServiceContainer

logger = logging.getLogger(__name__)


class PluginManager:
    def __init__(self, container: ServiceContainer, plugin_directory: Path) -> None:
        self.container = container
        self.plugin_directory = plugin_directory
        self.loaded: dict[str, VisionQCPlugin] = {}

    def load_all(self) -> dict[str, VisionQCPlugin]:
        self.plugin_directory.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.plugin_directory.glob("*.py")):
            if path.name.startswith("_"):
                continue
            self._load_file(path)
        return dict(self.loaded)

    def _load_file(self, path: Path) -> None:
        spec = importlib.util.spec_from_file_location(f"visionqc_external_plugin_{path.stem}", path)
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            plugin = getattr(module, "plugin", None)
            if not isinstance(plugin, VisionQCPlugin):
                logger.warning("Ignoring %s: module must expose 'plugin' VisionQCPlugin instance", path)
                return
            plugin.register(self.container)
            self.loaded[plugin.metadata.plugin_id] = plugin
            logger.info("Loaded plugin %s %s", plugin.metadata.name, plugin.metadata.version)
        except Exception:
            logger.exception("Failed to load plugin %s", path)
