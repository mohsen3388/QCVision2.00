from types import SimpleNamespace
from visionqc.analysis.indicator_scoring import score_indicators
from visionqc.models.results import AnalysisResult

def test_twelve_indicators_and_range():
    result=AnalysisResult("x",100,100,None,{
      "Image Quality":{"focus_score":80,"exposure_quality":90,"noise_mean_absolute":2},
      "Color":{"color_uniformity":88},"Texture":{"texture_uniformity":82},
      "Surface":{"bubble_candidate_density":2,"oily_region_candidate_percent":3,"specular_reflection_percent":1}},[],85,90,"Good")
    sample=SimpleNamespace(visual_health_score=85,analysis_confidence=90,color_uniformity=88,texture_uniformity=82,bubble_candidate_density=2,oily_region_candidate_percent=3,motion_stability=86,mixing_coverage=84)
    scores=score_indicators(result,sample,[sample])
    assert len(scores)==12
    assert all(0 <= x.score <= 100 for x in scores)
