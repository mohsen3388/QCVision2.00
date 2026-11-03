from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

_ALLOWED_STATUS = {"acceptable", "attention", "manual_review", "critical"}
_ALLOWED_SEVERITY = {"information", "low", "medium", "high", "critical"}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any, default: str = "") -> str:
    return str(value).strip() if value is not None else default


@dataclass(slots=True)
class AIFinding:
    type: str
    title_fa: str
    severity: str
    confidence: float
    evidence_fa: str
    possible_causes_fa: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIFinding":
        severity = _text(data.get("severity"), "medium").lower()
        if severity not in _ALLOWED_SEVERITY:
            severity = "medium"
        confidence = max(0.0, min(100.0, _as_float(data.get("confidence"), 0.0)))
        causes = data.get("possible_causes_fa") or []
        return cls(
            type=_text(data.get("type"), "unknown_visual_finding"),
            title_fa=_text(data.get("title_fa"), "یافته بصری مشخص نشده است"),
            severity=severity,
            confidence=confidence,
            evidence_fa=_text(data.get("evidence_fa"), "پاسخ هوش مصنوعی شواهد کافی ارائه نکرده است."),
            possible_causes_fa=[_text(item) for item in causes if _text(item)][:6],
        )


@dataclass(slots=True)
class AIRecommendedAction:
    action_code: str
    priority: int
    message_fa: str
    requires_authorization: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIRecommendedAction":
        try:
            priority = int(data.get("priority", 99))
        except (TypeError, ValueError):
            priority = 99
        return cls(
            action_code=_text(data.get("action_code"), "REQUEST_MANUAL_REVIEW").upper(),
            priority=max(1, min(priority, 99)),
            message_fa=_text(data.get("message_fa"), "بازبینی اپراتور و واحد کنترل کیفیت انجام شود."),
            requires_authorization=bool(data.get("requires_authorization", True)),
        )


@dataclass(slots=True)
class AIInspectionResult:
    status: str
    confidence: float
    operator_summary_fa: str
    visual_findings: list[AIFinding] = field(default_factory=list)
    recommended_actions: list[AIRecommendedAction] = field(default_factory=list)
    manual_review_required: bool = True
    limitations_fa: list[str] = field(default_factory=list)
    raw_response: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], raw_response: str = "") -> "AIInspectionResult":
        status = _text(data.get("status"), "manual_review").lower()
        if status not in _ALLOWED_STATUS:
            status = "manual_review"
        confidence = max(0.0, min(100.0, _as_float(data.get("confidence"), 0.0)))
        findings = [AIFinding.from_dict(item) for item in (data.get("visual_findings") or []) if isinstance(item, dict)]
        actions = [AIRecommendedAction.from_dict(item) for item in (data.get("recommended_actions") or []) if isinstance(item, dict)]
        actions.sort(key=lambda item: item.priority)
        limitations = [_text(item) for item in (data.get("limitations_fa") or []) if _text(item)][:8]
        manual = bool(data.get("manual_review_required", status != "acceptable" or confidence < 80.0))
        if confidence < 60.0:
            status = "manual_review"
            manual = True
        return cls(
            status=status,
            confidence=confidence,
            operator_summary_fa=_text(data.get("operator_summary_fa"), "بررسی هوش مصنوعی کامل نیست و نیاز به تأیید انسانی دارد."),
            visual_findings=findings,
            recommended_actions=actions,
            manual_review_required=manual,
            limitations_fa=limitations,
            raw_response=raw_response,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw_response", None)
        return data


@dataclass(slots=True)
class AIChatAnswer:
    answer_fa: str
    evidence_fa: list[str] = field(default_factory=list)
    suggested_actions_fa: list[str] = field(default_factory=list)
    confidence: float = 0.0
    safety_note_fa: str = "این پاسخ جایگزین ارزیابی آزمایشگاهی یا تصمیم کارشناس واجد صلاحیت کنترل کیفیت نیست."
    raw_response: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], raw_response: str = "") -> "AIChatAnswer":
        return cls(
            answer_fa=_text(data.get("answer_fa"), "پاسخ قابل اتکایی دریافت نشد."),
            evidence_fa=[_text(x) for x in (data.get("evidence_fa") or []) if _text(x)][:8],
            suggested_actions_fa=[_text(x) for x in (data.get("suggested_actions_fa") or []) if _text(x)][:8],
            confidence=max(0.0, min(100.0, _as_float(data.get("confidence"), 0.0))),
            safety_note_fa=_text(data.get("safety_note_fa"), "این پاسخ جایگزین ارزیابی آزمایشگاهی یا تصمیم کارشناس واجد صلاحیت کنترل کیفیت نیست."),
            raw_response=raw_response,
        )
