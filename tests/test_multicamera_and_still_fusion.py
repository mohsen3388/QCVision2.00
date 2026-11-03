from types import SimpleNamespace

from visionqc.analysis.indicator_scoring import score_still_indicators, aggregate_indicator_score
from visionqc.multicamera.models import CameraDefinition, CameraRegistry, profile_by_key


def test_single_bubble_detector_cannot_collapse_still_score():
    result = SimpleNamespace(metrics={
        "Image Quality": {"focus_score": 82, "exposure_quality": 92, "noise_mean_absolute": 1},
        "Color": {"color_uniformity": 86},
        "Texture": {"texture_uniformity": 67},
        "Surface": {"bubble_candidate_density": 40, "oily_region_candidate_percent": 3, "specular_reflection_percent": 8},
    })
    sample = SimpleNamespace(visual_health_score=89, color_uniformity=86, texture_uniformity=67,
                             bubble_candidate_density=40, oily_region_candidate_percent=3)
    scores = score_still_indicators(result, sample)
    values = {x.key: x.score for x in scores}
    assert values["aeration"] >= 55
    assert aggregate_indicator_score(scores) >= 70


def test_camera_registry_roundtrip(tmp_path):
    registry = CameraRegistry(tmp_path / "cameras.json")
    camera = CameraDefinition("cam1", "دیگ ۱", "سالن تولید", "دیگ ۱", "mixing", source_value="rtsp://camera")
    registry.upsert(camera)
    loaded = registry.list()
    assert len(loaded) == 1
    assert loaded[0].profile.title_fa == "دیگ و اختلاط"
    registry.delete("cam1")
    assert registry.list() == []


def test_hse_profile_has_separate_alert_route():
    profile = profile_by_key("hse")
    assert "کارشناس HSE" in profile.alert_targets_fa
    assert "کنترل مواد اولیه" != profile.title_fa
