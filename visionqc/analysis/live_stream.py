from __future__ import annotations

import cv2
import numpy as np


def build_temporal_contact_sheet(frame_payloads: list[bytes], fallback_jpeg: bytes, *, max_frames: int = 6) -> bytes:
    """Build one chronological JPEG contact sheet from recent live-camera frames."""
    frames = list(frame_payloads[-max_frames:]) or [fallback_jpeg]
    decoded: list[np.ndarray] = []
    for index, payload in enumerate(frames, 1):
        arr = np.frombuffer(payload, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            continue
        image = cv2.resize(image, (480, 320), interpolation=cv2.INTER_AREA)
        cv2.rectangle(image, (0, 0), (480, 34), (12, 24, 34), -1)
        cv2.putText(
            image,
            f"T{index} (oldest to newest)",
            (12, 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        decoded.append(image)
    if not decoded:
        return fallback_jpeg
    while len(decoded) < 4:
        decoded.insert(0, decoded[0].copy())
    rows: list[np.ndarray] = []
    for start in range(0, len(decoded), 3):
        row = decoded[start:start + 3]
        while len(row) < 3:
            row.append(np.full_like(decoded[0], 32))
        rows.append(cv2.hconcat(row))
    sheet = cv2.vconcat(rows)
    ok, encoded = cv2.imencode('.jpg', sheet, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return encoded.tobytes() if ok else fallback_jpeg
