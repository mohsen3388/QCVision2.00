from __future__ import annotations

import cv2
import numpy as np


def motion_scores(previous_gray: np.ndarray | None, frame: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Return current gray frame, motion stability (0..100), and mixing coverage (0..100).

    Scores are conservative visual proxies and require per-camera calibration.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (320, 180), interpolation=cv2.INTER_AREA)
    if previous_gray is None or previous_gray.shape != gray.shape:
        return gray, 100.0, 100.0
    flow = cv2.calcOpticalFlowFarneback(previous_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    finite = mag[np.isfinite(mag)]
    if finite.size == 0:
        return gray, 50.0, 50.0
    mean = float(np.mean(finite))
    std = float(np.std(finite))
    # Stability rewards coherent movement. For near-static scenes, avoid a false alarm.
    coherence = 1.0 if mean < 0.05 else max(0.0, 1.0 - std / max(mean * 2.5, 0.15))
    stability = float(np.clip(55.0 + coherence * 45.0, 0.0, 100.0))
    # Coverage: fraction of a 6x4 grid with meaningful motion relative to the frame median.
    threshold = max(0.12, float(np.percentile(finite, 55)) * 0.65)
    active = []
    h, w = mag.shape
    for gy in range(4):
        for gx in range(6):
            cell = mag[gy*h//4:(gy+1)*h//4, gx*w//6:(gx+1)*w//6]
            active.append(float(np.mean(cell)) >= threshold)
    coverage = float(np.mean(active) * 100.0)
    # A genuinely static process is reported as low coverage, but softened until calibrated.
    if mean < 0.05:
        coverage = 65.0
    return gray, round(stability, 2), round(float(np.clip(coverage, 0, 100)), 2)
