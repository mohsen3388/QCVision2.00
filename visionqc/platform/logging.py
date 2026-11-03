from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_directory: Path, level: int = logging.INFO) -> Path:
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "visionqc.log"
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == str(log_path) for h in root.handlers):
        handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        root.addHandler(handler)
    return log_path
