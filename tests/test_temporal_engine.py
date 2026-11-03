from __future__ import annotations

import numpy as np

from visionqc.analysis.engine import analyze_bgr
from visionqc.analysis.temporal import derive_events, sample_from_result, summarize_video
from visionqc.models.results import TemporalSample


def synthetic_frame(value: int = 130) -> np.ndarray:
    frame = np.full((180, 240, 3), value, dtype=np.uint8)
    frame[40:140, 60:180] = (90, 120, 165)
    return frame


def test_analyze_bgr_supports_in_memory_frame():
    result = analyze_bgr(synthetic_frame(), include_diagnostics=False)
    assert result.width == 240
    assert "Image Quality" in result.metrics
    assert result.visual_health_score >= 0


def test_temporal_summary_and_event_derivation():
    samples = [
        TemporalSample(0, 0.0, 92, 85, "Good", 130, 88, 90, 1, 2, 50, 0),
        TemporalSample(25, 1.0, 68, 84, "Attention", 128, 84, 65, 10, 14, 45, 2),
    ]
    events = derive_events(samples)
    assert events
    result = summarize_video("demo.mp4", 25.0, 50, 1.0, samples, {})
    assert result.analyzed_frames == 2
    assert result.process_stability <= 100
    assert result.status in {"پایدار", "نیاز به پایش", "هشدار سطح متوسط", "هشدار سطح بالا", "بحرانی"}


def test_sample_conversion_uses_existing_metric_names():
    result = analyze_bgr(synthetic_frame(), include_diagnostics=False)
    sample = sample_from_result(result, 10, 0.4)
    assert sample.brightness > 0
    assert sample.sharpness >= 0
