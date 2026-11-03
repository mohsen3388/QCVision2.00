from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import cv2


@dataclass(slots=True)
class SourceInfo:
    opened: bool
    width: int = 0
    height: int = 0
    fps: float = 0.0
    message: str = ""


def normalize_camera_source(value: str | int) -> str | int:
    if isinstance(value, int):
        return value
    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    return stripped


def validate_network_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"rtsp", "rtsps", "http", "https"}:
        return False, "Use an RTSP, RTSPS, HTTP or HTTPS stream URL."
    if not parsed.netloc:
        return False, "The stream URL does not contain a host."
    return True, "URL format is valid."


def probe_source(source: str | int, timeout_frames: int = 15) -> SourceInfo:
    source = normalize_camera_source(source)
    cap = cv2.VideoCapture(source, cv2.CAP_DSHOW) if isinstance(source, int) else cv2.VideoCapture(source)
    if not cap.isOpened():
        return SourceInfo(False, message="Could not open the camera or stream.")
    ok = False
    frame = None
    for _ in range(max(1, timeout_frames)):
        ok, frame = cap.read()
        if ok and frame is not None:
            break
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or (frame.shape[1] if frame is not None else 0))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or (frame.shape[0] if frame is not None else 0))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    cap.release()
    return SourceInfo(bool(ok), width, height, fps, "Connection successful." if ok else "Opened source but no frame was received.")
