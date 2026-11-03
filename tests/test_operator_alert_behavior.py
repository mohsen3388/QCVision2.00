from visionqc.ai.schemas import AIInspectionResult
from visionqc.application.services.operator_alert_service import evaluate_image_alert, evaluate_video_alert
from visionqc.models.results import AnalysisResult, RuleFinding, VideoAnalysisResult, TemporalEvent


def _image(status='Acceptable', finding=None):
    return AnalysisResult(
        source_path='x.jpg', width=100, height=100, roi=None, metrics={}, findings=[] if finding is None else [finding],
        visual_health_score=90, analysis_confidence=90, status=status
    )


def test_healthy_image_is_silent():
    decision = evaluate_image_alert(_image(), AIInspectionResult.from_dict({
        'status':'acceptable','confidence':95,'operator_summary_fa':'سالم','visual_findings':[],
        'recommended_actions':[],'manual_review_required':False,'limitations_fa':[]
    }))
    assert decision.level == 'silent'
    assert decision.should_speak is False


def test_high_image_alert_has_emergency_actions():
    finding = RuleFinding('R1','Fat separation','High',True,90,'fat separation observed',{},'check mixer')
    decision = evaluate_image_alert(_image('Attention', finding), None)
    assert decision.level == 'silent'
    assert decision.should_speak is False
    assert decision.immediate_actions_fa == []


def test_predictive_video_alert_speaks_and_gives_actions():
    video = VideoAnalysisResult(
        source_path='x.mp4', duration_seconds=10, source_fps=25, frame_count=250,
        sampling_interval_seconds=1, analyzed_frames=10, samples=[],
        events=[TemporalEvent(4,'trend','High','quality trend is deteriorating',70)],
        overall_health_score=65, overall_confidence=85, process_stability=55, status='Attention'
    )
    decision = evaluate_video_alert(video, None)
    assert decision.predictive is True
    assert decision.level in {'high','critical'}
    assert decision.should_speak is True
    assert decision.immediate_actions_fa


def test_attention_image_is_spoken_concisely():
    finding = RuleFinding('R2','Surface reflection','Medium',True,80,'reflection observed',{},'manual review')
    decision = evaluate_image_alert(_image('Attention', finding), None)
    assert decision.level == 'silent'
    assert decision.should_speak is False


def test_attention_ai_review_is_spoken_concisely():
    decision = evaluate_image_alert(_image(), AIInspectionResult.from_dict({
        'status':'attention','confidence':81,'operator_summary_fa':'Possible surface reflection',
        'visual_findings':[], 'recommended_actions':[], 'manual_review_required':True,
        'limitations_fa':[]
    }))
    assert decision.level == 'warning'
    assert decision.should_speak is True
    assert decision.voice_message_fa
