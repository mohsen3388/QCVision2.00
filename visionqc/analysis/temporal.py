from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Callable

import cv2
import numpy as np

from visionqc.analysis.engine import AnalysisError, analyze_bgr
from visionqc.models.results import TemporalEvent, TemporalSample, VideoAnalysisResult
from visionqc.analysis.motion import motion_scores
from visionqc.analysis.decision_fusion import classify_quality

ProgressCallback = Callable[[int, str], None]
SampleCallback = Callable[[TemporalSample], None]


def _metric(result, group: str, name: str, default: float = 0.0) -> float:
    return float(result.metrics.get(group, {}).get(name, default))


def sample_from_result(result, frame_index: int, timestamp_seconds: float) -> TemporalSample:
    return TemporalSample(
        frame_index=frame_index,
        timestamp_seconds=round(timestamp_seconds, 3),
        visual_health_score=result.visual_health_score,
        analysis_confidence=result.analysis_confidence,
        status=result.status,
        brightness=_metric(result, "Image Quality", "brightness"),
        color_uniformity=_metric(result, "Color", "color_uniformity"),
        texture_uniformity=_metric(result, "Texture", "texture_uniformity"),
        bubble_candidate_density=_metric(result, "Surface", "bubble_candidate_density"),
        oily_region_candidate_percent=_metric(result, "Surface", "oily_region_candidate_percent"),
        sharpness=_metric(result, "Image Quality", "sharpness_laplacian"),
        triggered_findings=sum(1 for f in result.findings if f.triggered),
    )


def derive_events(samples: list[TemporalSample]) -> list[TemporalEvent]:
    events: list[TemporalEvent] = []
    if not samples:
        return events
    for sample in samples:
        if sample.status == "Review Required":
            events.append(TemporalEvent(sample.timestamp_seconds, "quality", "Critical", "Frame requires review.", sample.visual_health_score))
        elif sample.status == "Attention":
            events.append(TemporalEvent(sample.timestamp_seconds, "quality", "Warning", "Visual quality moved into attention range.", sample.visual_health_score))
        if sample.bubble_candidate_density > 8:
            events.append(TemporalEvent(sample.timestamp_seconds, "surface", "Attention", "Bubble candidate density is elevated.", sample.bubble_candidate_density))
        if sample.oily_region_candidate_percent > 12:
            events.append(TemporalEvent(sample.timestamp_seconds, "surface", "Attention", "Reflective/oily candidate area is elevated.", sample.oily_region_candidate_percent))
    for previous, current in zip(samples, samples[1:]):
        if previous.timestamp_seconds == current.timestamp_seconds:
            continue
        health_drop = current.visual_health_score - previous.visual_health_score
        texture_drop = current.texture_uniformity - previous.texture_uniformity
        if health_drop <= -12:
            events.append(TemporalEvent(current.timestamp_seconds, "trend", "Warning", "Rapid visual-health decrease detected.", health_drop))
        if texture_drop <= -15:
            events.append(TemporalEvent(current.timestamp_seconds, "trend", "Warning", "Texture uniformity decreased rapidly.", texture_drop))
    # Collapse duplicates of the same message within 2 seconds.
    collapsed: list[TemporalEvent] = []
    for event in sorted(events, key=lambda e: e.timestamp_seconds):
        if collapsed and event.message == collapsed[-1].message and event.timestamp_seconds - collapsed[-1].timestamp_seconds < 8.0:
            continue
        collapsed.append(event)
    return collapsed


def summarize_video(path: str, source_fps: float, frame_count: int, interval: float,
                    samples: list[TemporalSample], snapshots: dict[str, bytes]) -> VideoAnalysisResult:
    if not samples:
        raise AnalysisError("No valid video frames were analyzed.")
    health = np.array([s.visual_health_score for s in samples], dtype=float)
    confidence = np.array([s.analysis_confidence for s in samples], dtype=float)
    texture = np.array([s.texture_uniformity for s in samples], dtype=float)
    brightness = np.array([s.brightness for s in samples], dtype=float)
    variation = float(np.mean([np.std(health), np.std(texture), np.std(brightness) / 2]))
    stability = max(0.0, min(100.0, 100.0 - variation * 2.2))
    overall_health = float(np.mean(health))
    overall_confidence = float(np.mean(confidence))
    events = derive_events(samples)
    critical = any(e.severity == "Critical" for e in events)
    # Final state is driven by the fused health score. Stability is a supporting
    # indicator, not an independent source of contradictory warnings.
    fused_score = 0.78 * overall_health + 0.22 * stability
    decision = classify_quality(fused_score, critical_override=critical)
    status = decision.status_fa
    overall_health = decision.score
    duration = frame_count / source_fps if source_fps > 0 else samples[-1].timestamp_seconds
    return VideoAnalysisResult(
        source_path=path,
        duration_seconds=round(duration, 3),
        source_fps=round(source_fps, 3),
        frame_count=frame_count,
        sampling_interval_seconds=interval,
        analyzed_frames=len(samples),
        samples=samples,
        events=events,
        overall_health_score=round(overall_health, 2),
        overall_confidence=round(overall_confidence, 2),
        process_stability=round(stability, 2),
        status=status,
        snapshots_jpeg=snapshots,
    )


def analyze_video(path: str, sampling_interval_seconds: float = 1.0,
                  progress: ProgressCallback | None = None,
                  sample_callback: SampleCallback | None = None,
                  cancel_event: Event | None = None) -> VideoAnalysisResult:
    source = str(Path(path))
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        raise AnalysisError("The selected video could not be opened.")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0:
        fps = 25.0
    interval = max(0.2, float(sampling_interval_seconds))
    frame_step = max(1, int(round(fps * interval)))
    expected = max(1, int(np.ceil(frame_count / frame_step))) if frame_count > 0 else 1
    samples: list[TemporalSample] = []
    snapshots: dict[str, bytes] = {}
    frame_index = 0
    analyzed = 0
    previous_analysis_gray = None
    try:
        while True:
            if cancel_event and cancel_event.is_set():
                raise AnalysisError("Video analysis was cancelled by the user.")
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % frame_step == 0:
                timestamp = frame_index / fps
                result = analyze_bgr(frame, f"{source}#frame={frame_index}", include_diagnostics=False)
                sample = sample_from_result(result, frame_index, timestamp)
                previous_analysis_gray, sample.motion_stability, sample.mixing_coverage = motion_scores(previous_analysis_gray, frame)
                samples.append(sample)
                analyzed += 1
                if sample_callback:
                    sample_callback(sample)
                if len(snapshots) < 8 and (sample.status != "Good" or analyzed == 1 or analyzed % max(1, expected // 5) == 0):
                    success, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                    if success:
                        snapshots[f"{timestamp:.1f}s_{sample.status.replace(' ', '_')}"] = encoded.tobytes()
                percent = min(99, int(analyzed / expected * 100)) if frame_count > 0 else min(99, analyzed)
                if progress:
                    progress(percent, f"Analyzing frame {analyzed} at {timestamp:.1f} s")
            frame_index += 1
    finally:
        capture.release()
    if progress:
        progress(100, "Temporal analysis completed")
    return summarize_video(source, fps, frame_count or frame_index, interval, samples, snapshots)
