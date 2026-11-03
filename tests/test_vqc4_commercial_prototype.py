import numpy as np
from visionqc.configuration import ConfigurationRuntime, default_detector_registry
from visionqc.quality import sausage_mixing_commercial_template, build_management_summary
from visionqc.quality.calibration import CalibrationService

def test_v4_registry_has_real_plugins():
    r=default_detector_registry(); keys={m.key for m in r.manifests()}
    assert 'product.texture_uniformity' in keys
    assert 'reference.color_similarity' in keys
    assert 'image.exposure_health' in keys

def test_v4_template_has_12_metrics_and_valid_weights():
    t=sausage_mixing_commercial_template()
    assert len(t.metrics)==12
    assert sum(m.weight for m in t.metrics if m.group_name=='سلامت محصول')==100
    assert sum(m.weight for m in t.metrics if m.group_name=='سلامت فرایند')==100
    assert t.ai_review_below==80

def test_v4_runtime_produces_management_summary():
    frame=np.full((240,320,3),128,dtype=np.uint8)
    result=ConfigurationRuntime().analyze_frame(frame,sausage_mixing_commercial_template())
    assert 0 <= result['final_score'] <= 100
    assert 'تصمیم نهایی' in result['management_summary']
    assert result['ai_review_required'] == (result['final_score'] < 80)

def test_calibration_requires_both_classes():
    service=CalibrationService()
    try:
        service.recommend([],['bad.png'],sausage_mixing_commercial_template())
        assert False
    except ValueError:
        assert True
