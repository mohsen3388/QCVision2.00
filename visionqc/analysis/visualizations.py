from __future__ import annotations

import cv2
import numpy as np


def _encode(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    return encoded.tobytes() if ok else b""


def build_visualizations(image: np.ndarray) -> dict[str, bytes]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Texture heatmap based on local standard deviation.
    f = gray.astype(np.float32)
    mean = cv2.blur(f, (15, 15))
    sq_mean = cv2.blur(f * f, (15, 15))
    std = np.sqrt(np.maximum(0, sq_mean - mean * mean))
    std_norm = cv2.normalize(std, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    texture_heat = cv2.applyColorMap(std_norm, cv2.COLORMAP_TURBO)
    texture_overlay = cv2.addWeighted(image, 0.55, texture_heat, 0.45, 0)

    # Edge and surface overlays.
    edges = cv2.Canny(gray, 50, 150)
    edge_overlay = image.copy()
    edge_overlay[edges > 0] = (0, 255, 255)

    sat, val = hsv[:, :, 1], hsv[:, :, 2]
    candidate = ((sat < 55) & (val > 165)).astype(np.uint8) * 255
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    surface_overlay = image.copy()
    contours, _ = cv2.findContours(candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        if cv2.contourArea(c) >= 12:
            cv2.drawContours(surface_overlay, [c], -1, (0, 165, 255), 2)

    return {
        "Original ROI": _encode(image),
        "Texture Heatmap": _encode(texture_overlay),
        "Edge Overlay": _encode(edge_overlay),
        "Surface Candidates": _encode(surface_overlay),
    }
