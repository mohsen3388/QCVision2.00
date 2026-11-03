from __future__ import annotations

from typing import Any

from visionqc.ai.schemas import AIInspectionResult
from visionqc.models.results import AnalysisResult


def build_hybrid_payload(local: AnalysisResult, gemini: AIInspectionResult | None) -> dict[str, Any]:
    """Return the stable export contract for local + Gemini deep analysis."""
    return {
        "analysis_mode": "hybrid_local_and_gemini",
        "local_analysis": local.to_dict(),
        "gemini_analysis": gemini.to_dict() if gemini else None,
        "gemini_completed": gemini is not None,
    }


def build_hybrid_video_payload(local: Any, gemini: AIInspectionResult | None) -> dict[str, Any]:
    """Return the stable export contract for temporal + Gemini video review."""
    return {
        "analysis_mode": "hybrid_temporal_and_gemini",
        "local_temporal_analysis": local.to_dict(),
        "gemini_analysis": gemini.to_dict() if gemini else None,
        "gemini_completed": gemini is not None,
    }
