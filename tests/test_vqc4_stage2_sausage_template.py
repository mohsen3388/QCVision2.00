import numpy as np

from visionqc.configuration import ConfigurationRuntime, default_detector_registry
from visionqc.quality import sausage_mixing_commercial_template


def _moving_frames(count=8):
    frames=[]
    for i in range(count):
        f=np.full((240,320,3),120,dtype=np.uint8)
        x=30+i*12
        f[80:160,x:x+70]=170
        frames.append(f)
    return frames


def test_temporal_detectors_registered():
    keys={m.key for m in default_detector_registry().manifests()}
    assert 'process.motion_stability' in keys
    assert 'process.mixing_coverage' in keys
    assert 'process.dead_zone_health' in keys
    assert 'process.temporal_consistency' in keys


def test_image_marks_temporal_metrics_not_applicable():
    result=ConfigurationRuntime().analyze_frame(np.full((240,320,3),128,dtype=np.uint8),sausage_mixing_commercial_template())
    temporal=[m for m in result['metrics'] if m['key'].startswith('process.') and m['key']!='process.assessability']
    assert temporal
    assert all(m['status']=='NOT_APPLICABLE' for m in temporal)
    assert result['mode']=='image'


def test_video_executes_temporal_metrics_and_triggers():
    frames=_moving_frames()
    result=ConfigurationRuntime().analyze_video_frames(frames,list(range(len(frames))),sausage_mixing_commercial_template())
    by_key={m['key']:m for m in result['metrics']}
    assert by_key['process.motion']['status']=='OK'
    assert by_key['process.mixing_coverage']['status']=='OK'
    assert by_key['process.dead_zone']['status']=='OK'
    assert by_key['process.temporal']['status']=='OK'
    assert isinstance(result['triggers'],list)
    assert result['ai_review_required']==(result['final_score']<80)


def test_product_health_limits_final_decision():
    from visionqc.quality.decision import fuse
    final,status=fuse(62,98)
    assert final<=69
    assert status=='هشدار سطح بالا'
