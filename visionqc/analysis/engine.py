from __future__ import annotations

from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from visionqc.analysis.features import color_metrics, distributions, image_quality_metrics, surface_metrics, texture_metrics
from visionqc.analysis.rules import evaluate_rules
from visionqc.analysis.visualizations import build_visualizations
from visionqc.models.results import AnalysisResult

ProgressCallback = Callable[[int, str], None]


class AnalysisError(RuntimeError):
    pass


def crop_roi(image: np.ndarray, roi: tuple[int, int, int, int] | None) -> np.ndarray:
    if roi is None:
        return image
    x, y, w, h = roi
    x = max(0, min(x, image.shape[1] - 1)); y = max(0, min(y, image.shape[0] - 1))
    w = max(1, min(w, image.shape[1] - x)); h = max(1, min(h, image.shape[0] - y))
    return image[y:y+h, x:x+w]


def analyze_bgr(image: np.ndarray, source_path: str = "memory://frame",
                roi: tuple[int, int, int, int] | None = None,
                progress: ProgressCallback | None = None,
                include_diagnostics: bool = True) -> AnalysisResult:
    def report(value: int, message: str) -> None:
        if progress:
            progress(value, message)
    if image is None or image.size == 0:
        raise AnalysisError("The image frame is empty.")
    height, width = image.shape[:2]
    report(10, "Validating source and ROI")
    work = crop_roi(image, roi)
    if min(work.shape[:2]) < 32:
        raise AnalysisError("The selected ROI is too small for reliable analysis.")
    report(20, "Measuring acquisition quality")
    quality = image_quality_metrics(work)
    report(35, "Extracting multi-space color statistics")
    color = color_metrics(work)
    report(52, "Computing GLCM, LBP and texture descriptors")
    texture = texture_metrics(work)
    report(68, "Evaluating surface and candidate regions")
    surface = surface_metrics(work)
    metrics = {"Image Quality": quality, "Color": color, "Texture": texture, "Surface": surface}
    histograms = distributions(work) if include_diagnostics else {}
    visuals = build_visualizations(work) if include_diagnostics else {}
    report(88, "Applying explainable knowledge rules")
    findings = evaluate_rules(metrics)
    triggered = [f for f in findings if f.triggered]
    penalty = sum({"Critical": 24, "Warning": 13, "Attention": 7}.get(f.severity, 5) * max(f.confidence, 25) / 100 for f in triggered)
    health = max(0.0, min(100.0, 100.0 - penalty))
    acquisition_reliability = np.mean([quality["exposure_quality"], quality["focus_score"], min(100.0, quality["dynamic_range_p1_p99"] / 1.7)])
    sample_factor = min(100.0, work.shape[0] * work.shape[1] / 180000 * 100)
    confidence = max(20.0, min(99.0, 0.78 * acquisition_reliability + 0.22 * sample_factor))
    if any(f.severity == "Critical" and f.triggered for f in findings): status = "Review Required"
    elif health < 72 or any(f.severity == "Warning" and f.triggered for f in findings): status = "Attention"
    else: status = "Good"
    report(100, "Analysis completed")
    return AnalysisResult(source_path, width, height, roi, metrics, findings, round(health, 2), round(float(confidence), 2), status, histograms, visuals)


def analyze_image(path: str, roi: tuple[int, int, int, int] | None = None,
                  progress: ProgressCallback | None = None) -> AnalysisResult:
    if progress: progress(3, "Loading image source")
    image = cv2.imread(str(Path(path)))
    if image is None:
        raise AnalysisError("The selected image could not be loaded.")
    return analyze_bgr(image, str(path), roi, progress, True)
