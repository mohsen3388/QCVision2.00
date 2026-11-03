from visionqc.ai.schemas import AIInspectionResult
from visionqc.application.services.hybrid_analysis_service import build_hybrid_payload, build_hybrid_video_payload
from visionqc.models.results import AnalysisResult


def _local():
    return AnalysisResult(
        source_path="sample.jpg", width=100, height=80, roi=None, metrics={"color": {"brightness": 50.0}},
        findings=[], visual_health_score=88.0, analysis_confidence=91.0, status="Acceptable"
    )


def test_hybrid_payload_keeps_local_result_when_gemini_is_unavailable():
    payload = build_hybrid_payload(_local(), None)
    assert payload["gemini_completed"] is False
    assert payload["local_analysis"]["visual_health_score"] == 88.0


def test_hybrid_payload_merges_gemini_result():
    ai = AIInspectionResult.from_dict({
        "status": "attention", "confidence": 84, "operator_summary_fa": "نیازمند بررسی",
        "visual_findings": [], "recommended_actions": [], "manual_review_required": True, "limitations_fa": []
    })
    payload = build_hybrid_payload(_local(), ai)
    assert payload["gemini_completed"] is True
    assert payload["gemini_analysis"]["status"] == "attention"


def test_video_hybrid_payload_preserves_temporal_result():
    class Temporal:
        def to_dict(self): return {"status": "Attention", "analyzed_frames": 8}
    payload = build_hybrid_video_payload(Temporal(), None)
    assert payload["analysis_mode"] == "hybrid_temporal_and_gemini"
    assert payload["local_temporal_analysis"]["analyzed_frames"] == 8
