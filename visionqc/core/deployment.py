from __future__ import annotations

import importlib
import json
import os
import platform
import shutil
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from visionqc.core.settings import APP_VERSION, load_settings

RUNTIME_MODULES = ("PySide6", "cv2", "numpy", "sqlalchemy", "reportlab")

@dataclass(frozen=True)
class DeploymentCheck:
    name: str
    ok: bool
    message: str


def is_frozen_build() -> bool:
    return bool(getattr(sys, "frozen", False))


def runtime_inventory(modules: Iterable[str] = RUNTIME_MODULES) -> list[dict]:
    rows: list[dict] = []
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "bundled")
            rows.append({"module": module_name, "available": True, "version": str(version)})
        except Exception as exc:
            rows.append({"module": module_name, "available": False, "version": "", "error": str(exc)})
    return rows


def deployment_readiness() -> dict:
    settings = load_settings()
    checks: list[DeploymentCheck] = []
    inventory = runtime_inventory()
    missing = [row["module"] for row in inventory if not row["available"]]
    checks.append(DeploymentCheck("Bundled application runtime", not missing, "All required Python modules are available." if not missing else "Missing: " + ", ".join(missing)))

    data_dir = Path(settings["data_directory"])
    reports_dir = Path(settings["reports_directory"])
    for label, path in (("Data directory", data_dir), ("Reports directory", reports_dir)):
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".visionqc_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            checks.append(DeploymentCheck(label, True, f"Writable: {path}"))
        except Exception as exc:
            checks.append(DeploymentCheck(label, False, f"Not writable: {path} ({exc})"))

    try:
        free = shutil.disk_usage(data_dir).free
        ok = free >= 500 * 1024 * 1024
        checks.append(DeploymentCheck("Free disk space", ok, f"{free / (1024**3):.2f} GB available"))
    except Exception as exc:
        checks.append(DeploymentCheck("Free disk space", False, str(exc)))

    checks.append(DeploymentCheck("64-bit Windows target", platform.system() == "Windows" and platform.machine().lower() in {"amd64", "x86_64"}, f"Detected {platform.system()} {platform.machine()}"))
    checks.append(DeploymentCheck("Standalone executable", is_frozen_build(), "Running as packaged VisionQC executable." if is_frozen_build() else "Development mode; the release installer will contain the standalone executable."))

    required_ok = all(c.ok for c in checks[:4])
    return {
        "visionqc_version": APP_VERSION,
        "status": "Ready" if required_ok else "Attention",
        "frozen": is_frozen_build(),
        "python_runtime": sys.version.split()[0],
        "platform": platform.platform(),
        "executable": sys.executable,
        "inventory": inventory,
        "checks": [asdict(c) for c in checks],
        "installation_note": "The Windows installer deploys VisionQC, Python runtime, Qt/PySide6, OpenCV, NumPy, SQLAlchemy and ReportLab together. The destination computer does not need Python or developer tools.",
    }


def export_deployment_report(destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(deployment_readiness(), indent=2), encoding="utf-8")
    return destination
