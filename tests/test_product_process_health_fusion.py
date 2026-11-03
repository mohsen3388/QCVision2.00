from types import SimpleNamespace

from visionqc.analysis.health_fusion import split_health_scores
from visionqc.analysis.indicator_scoring import IndicatorScore, score_still_indicators


def _scores(**overrides):
    values = {
        "image": 90, "color": 90, "texture": 90, "surface": 90,
        "aeration": 90, "motion": 90, "mixing": 90, "reference": 90,
        "process": 90, "lighting": 90, "focus": 90, "risk": 90,
    }
    values.update(overrides)
    return [IndicatorScore(k, k, v, "") for k, v in values.items()]


def test_poor_product_is_not_hidden_by_stable_process():
    b = split_health_scores(_scores(color=55, texture=50, surface=60, mixing=55, reference=58,
                                    motion=98, process=98, image=95, lighting=95, focus=90), still_image=False)
    assert b.product_health < 70
    assert b.process_health > 90
    assert b.final_score < 70


def test_healthy_product_and_process_are_stable():
    b = split_health_scores(_scores(), still_image=False)
    assert b.product_health == 90
    assert b.process_health == 90
    assert b.final_score == 90


def test_still_single_bubble_detector_does_not_create_critical_result():
    result = SimpleNamespace(metrics={
        "Image Quality": {"focus_score": 82, "exposure_quality": 92, "noise_mean_absolute": 1},
        "Color": {"color_uniformity": 88},
        "Texture": {"texture_uniformity": 84},
        "Surface": {"bubble_candidate_density": 45, "oily_region_candidate_percent": 2, "specular_reflection_percent": 8},
    })
    sample = SimpleNamespace(visual_health_score=89, color_uniformity=88, texture_uniformity=84,
                             bubble_candidate_density=45, oily_region_candidate_percent=2)
    scores = score_still_indicators(result, sample)
    b = split_health_scores(scores, still_image=True)
    assert b.product_health >= 75
    assert b.final_score >= 75
