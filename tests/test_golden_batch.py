from types import SimpleNamespace

from visionqc.analysis.golden import build_reference, compare_to_reference


def result(value_shift=0.0, confidence=90.0):
    metrics={
      "Image Quality":{"brightness":130+value_shift,"contrast_std":30,"focus_score":82,"exposure_quality":90},
      "Color":{"color_uniformity":82-value_shift,"lab_chroma_mean":25,"hue_concentration":0.75},
      "Texture":{"texture_uniformity":78-value_shift,"glcm_homogeneity":0.72,"glcm_contrast":18,"lbp_entropy":3.1},
      "Surface":{"bubble_candidate_density":4+value_shift/3,"oily_region_candidate_percent":1.5,"specular_reflection_percent":0.8},
    }
    return SimpleNamespace(metrics=metrics, analysis_confidence=confidence)


def test_identical_sample_matches():
    refs=build_reference([result(),result(1)])
    comparison=compare_to_reference(result(0.5),1,"Approved",refs)
    assert comparison.similarity_score > 90
    assert comparison.status == "Match"


def test_large_deviation_is_visible():
    refs=build_reference([result(),result(1),result(-1)])
    comparison=compare_to_reference(result(35),1,"Approved",refs)
    assert comparison.similarity_score < 75
    assert comparison.strongest_deviations
    assert any(d.status == "Out of Range" for d in comparison.deviations)
