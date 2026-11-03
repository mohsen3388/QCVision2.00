import numpy as np
from visionqc.configuration.registry import default_detector_registry
from visionqc.configuration.scoring import score_value
from visionqc.configuration.models import ScoringRule
from visionqc.configuration.seed import sausage_batter_template
from visionqc.configuration.validator import validate_template
from visionqc.configuration.runtime import ConfigurationRuntime

def test_registry_has_real_detectors():
    r=default_detector_registry(); keys={x.key for x in r.manifests()}
    assert 'product.texture_uniformity' in keys
    assert 'image.focus' in keys

def test_scoring_directions():
    assert score_value(.9,ScoringRule('higher_is_better',0,1))==90
    assert score_value(.1,ScoringRule('lower_is_better',0,1))==90

def test_seed_template_is_structurally_valid():
    t=sausage_batter_template(); errors=validate_template(t,default_detector_registry())
    assert errors==[]
    assert len(t.metrics)>=8 and len(t.triggers)>=3 and len(t.actions)>=2

def test_runtime_executes_all_enabled_metrics():
    frame=np.full((240,320,3),128,dtype=np.uint8)
    t=sausage_batter_template(); result=ConfigurationRuntime().analyze_frame(frame,t)
    assert len(result['metrics'])==len([m for m in t.metrics if m.enabled])
    assert 0 <= result['final_score'] <= 100
    assert isinstance(result['ai_review_required'],bool)
