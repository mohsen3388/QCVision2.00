from __future__ import annotations

from pathlib import Path
import json
import os

APP_NAME = "VisionQC"
APP_VERSION = "4.7.0"
ENGINE_VERSION = "0.4.7"
ORGANIZATION_NAME = "VisionQC"


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".visionqc"))
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_settings() -> dict:
    base = app_data_dir()
    return {
        "first_run_complete": False,
        "factory_name": "My Factory",
        "operator_name": "Operator",
        "language": "English",
        "theme": "Factory Blue",
        "ui_scale": 100,
        "data_directory": str(base / "data"),
        "reports_directory": str(base / "reports"),
        "camera_index": 0,
        "analysis_interval_seconds": 3,
        "keep_data_on_uninstall": True,
    }


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def load_settings() -> dict:
    values = default_settings()
    path = settings_path()
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                values.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    Path(values["data_directory"]).mkdir(parents=True, exist_ok=True)
    Path(values["reports_directory"]).mkdir(parents=True, exist_ok=True)
    return values


def save_settings(values: dict) -> None:
    merged = default_settings()
    merged.update(values)
    Path(merged["data_directory"]).mkdir(parents=True, exist_ok=True)
    Path(merged["reports_directory"]).mkdir(parents=True, exist_ok=True)
    settings_path().write_text(json.dumps(merged, indent=2), encoding="utf-8")
