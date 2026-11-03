from types import SimpleNamespace

from visionqc.analysis.decision_fusion import requires_ai_review
from visionqc.analysis.indicator_scoring import summarize_temporal_indicators, aggregate_indicator_score


def _sample(i: int):
    return SimpleNamespace(
        visual_health_score=84.0 + i * 0.2,
        analysis_confidence=90.0,
        color_uniformity=77.0 + i * 0.1,
        texture_uniformity=47.0 + i * 0.15,
        bubble_candidate_density=3.0 + i * 0.03,
        oily_region_candidate_percent=10.0 + i * 0.02,
        motion_stability=64.0 + i * 0.2,
        mixing_coverage=58.0 + i * 0.2,
        brightness=126.0,
        sharpness=205.0,
    )


def test_ai_review_never_runs_at_or_above_80():
    assert requires_ai_review(79.9)
    assert not requires_ai_review(80.0)
    assert not requires_ai_review(83.4, critical_override=True, predictive=True)


def test_stable_video_uses_temporal_consistency_not_raw_texture_only():
    scores = summarize_temporal_indicators([_sample(i) for i in range(6)])
    by_key = {x.key: x.score for x in scores}
    assert by_key["texture"] >= 80
    assert by_key["motion"] >= 80
    assert aggregate_indicator_score(scores) >= 80
