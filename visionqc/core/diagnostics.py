from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import platform
import shutil
import sys
import zipfile

import cv2

from visionqc.core.settings import APP_NAME, APP_VERSION, ENGINE_VERSION, app_data_dir, load_settings, settings_path
from visionqc.core.database import database_path


def system_report() -> dict:
    s = load_settings()
    data_dir = Path(s["data_directory"])
    usage = shutil.disk_usage(data_dir)
    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "engine_version": ENGINE_VERSION,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "opencv": cv2.__version__,
        "settings_path": str(settings_path()),
        "database_path": str(database_path()),
        "data_directory": str(data_dir),
        "disk_free_gb": round(usage.free / (1024 ** 3), 2),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def camera_test(index: int = 0) -> tuple[bool, str]:
    cap = cv2.VideoCapture(index)
    try:
        if not cap.isOpened():
            return False, f"Camera {index} could not be opened."
        ok, frame = cap.read()
        if not ok or frame is None:
            return False, f"Camera {index} opened but did not provide a frame."
        h, w = frame.shape[:2]
        return True, f"Camera {index} is available ({w}×{h})."
    finally:
        cap.release()


def create_support_bundle(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = destination / f"VisionQC_Support_{stamp}.zip"
    report_path = app_data_dir() / "diagnostic_report.json"
    report_path.write_text(json.dumps(system_report(), indent=2), encoding="utf-8")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(report_path, "diagnostic_report.json")
        if settings_path().exists():
            archive.write(settings_path(), "settings.json")
        db = database_path()
        if db.exists():
            archive.write(db, "visionqc.db")
    return target
