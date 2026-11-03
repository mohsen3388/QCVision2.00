from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4


class VoiceIntent(StrEnum):
    GREETING = "greeting"
    HELP = "help"
    RECENT_CASES = "recent_cases"
    CASE_SUMMARY = "case_summary"
    SIMILAR_CASES = "similar_cases"
    REJECT_TREND = "reject_trend"
    DEFECT_SUMMARY = "defect_summary"
    RECOMMENDED_ACTIONS = "recommended_actions"
    QUALITY_STATUS = "quality_status"
    PREDICTIVE_RISK = "predictive_risk"
    FACTORY_ENGINEER = "factory_engineer"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class VoiceMessage:
    role: str
    text: str
    message_uuid: str = field(default_factory=lambda: str(uuid4()))
    intent: VoiceIntent = VoiceIntent.UNKNOWN
    confidence: float = 1.0
    source: str = "typed"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class VoiceConversation:
    title: str = "Operator conversation"
    conversation_uuid: str = field(default_factory=lambda: str(uuid4()))
    factory_name: str = ""
    operator_name: str = ""
    selected_case_id: int | None = None
    messages: list[VoiceMessage] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


@dataclass(slots=True)
class VoiceResponse:
    text: str
    intent: VoiceIntent
    confidence: float
    evidence: list[str] = field(default_factory=list)
    suggested_prompts: list[str] = field(default_factory=list)
    safety_note: str = "این پاسخ فقط پشتیبان تصمیم‌گیری است. تغییرات فرایند باید توسط مسئول تولید یا کنترل کیفیت تأیید شود."
