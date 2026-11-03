from __future__ import annotations

import cv2
import numpy as np


def _gray(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _flow_magnitude(prev: np.ndarray, cur: np.ndarray) -> np.ndarray:
    a = cv2.resize(_gray(prev), (320, 240))
    b = cv2.resize(_gray(cur), (320, 240))
    flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    return np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)


def motion_stability(frames: list[np.ndarray], params: dict | None = None) -> float:
    """0..1; high when motion magnitude is consistent through time."""
    if len(frames) < 3:
        return float('nan')
    medians = [float(np.median(_flow_magnitude(a, b))) for a, b in zip(frames, frames[1:])]
    mean = float(np.mean(medians))
    if mean < 0.02:
        return 0.35
    cv = float(np.std(medians) / max(mean, 1e-6))
    return float(np.clip(1.0 - cv / float((params or {}).get('cv_limit', 1.1)), 0, 1))


def mixing_coverage(frames: list[np.ndarray], params: dict | None = None) -> float:
    """0..1; fraction of ROI showing recurrent movement."""
    if len(frames) < 3:
        return float('nan')
    threshold = float((params or {}).get('motion_threshold', 0.20))
    masks = [(_flow_magnitude(a, b) > threshold).astype(np.float32) for a, b in zip(frames, frames[1:])]
    persistence = np.mean(masks, axis=0)
    recurrent = persistence >= float((params or {}).get('persistence_ratio', 0.35))
    return float(np.clip(np.mean(recurrent), 0, 1))


def dead_zone_health(frames: list[np.ndarray], params: dict | None = None) -> float:
    """0..1; inverse of persistent low-motion area."""
    if len(frames) < 3:
        return float('nan')
    threshold = float((params or {}).get('motion_threshold', 0.16))
    mags = np.stack([_flow_magnitude(a, b) for a, b in zip(frames, frames[1:])])
    persistent_low = np.mean(mags < threshold, axis=0) >= float((params or {}).get('persistence_ratio', 0.75))
    return float(np.clip(1.0 - np.mean(persistent_low), 0, 1))


def temporal_consistency(score_history: dict[str, list[float]], params: dict | None = None) -> float:
    """0..1; stability across selected product metrics."""
    keys = (params or {}).get('keys') or ['product.texture', 'product.color', 'product.surface', 'product.aeration']
    cvs: list[float] = []
    for key in keys:
        values = np.asarray(score_history.get(key, []), dtype=float)
        values = values[np.isfinite(values)]
        if values.size >= 3:
            cvs.append(float(np.std(values) / max(np.mean(values), 1.0)))
    if not cvs:
        return float('nan')
    return float(np.clip(1.0 - np.mean(cvs) / float((params or {}).get('cv_limit', 0.25)), 0, 1))


TEMPORAL_FUNCTIONS = {
    'process.motion_stability': motion_stability,
    'process.mixing_coverage': mixing_coverage,
    'process.dead_zone_health': dead_zone_health,
}
