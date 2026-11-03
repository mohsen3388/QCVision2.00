from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from visionqc.ai.schemas import AIInspectionResult
from visionqc.core.settings import app_data_dir
from visionqc.analysis.decision_fusion import classify_quality


@dataclass(slots=True)
class OperatorAlertDecision:
    level: str
    should_speak: bool
    # Field names are preserved for backward-compatible JSON exports.
    # Values are English-only in this release.
    voice_message_fa: str = ""
    immediate_actions_fa: list[str] = field(default_factory=list)
    reason: str = ""
    predictive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_LEVEL_RANK = {"silent": 0, "warning": 1, "high": 2, "critical": 3}


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower()


def _max_local_severity(local: Any) -> str:
    rank = {"information": 0, "low": 0, "attention": 1, "warning": 1, "medium": 1, "high": 2, "critical": 3}
    best = "silent"
    best_rank = 0
    for finding in getattr(local, "findings", []) or []:
        if not getattr(finding, "triggered", False):
            continue
        severity = _normalise(getattr(finding, "severity", ""))
        current = rank.get(severity, 1)
        if current > best_rank:
            best_rank = current
            best = "critical" if current >= 3 else "high" if current == 2 else "warning"
    return best


def _ai_level(ai: AIInspectionResult | None) -> str:
    if ai is None:
        return "silent"
    status = _normalise(ai.status)
    level = {
        "acceptable": "silent",
        "attention": "warning",
        "manual_review": "high",
        "critical": "critical",
    }.get(status, "high")
    for finding in ai.visual_findings:
        severity = _normalise(finding.severity)
        candidate = "critical" if severity == "critical" else "high" if severity == "high" else "warning" if severity in {"medium", "warning"} else "silent"
        if _LEVEL_RANK[candidate] > _LEVEL_RANK[level]:
            level = candidate
    return level


def _combined_level(local_level: str, ai_level: str) -> str:
    return local_level if _LEVEL_RANK[local_level] >= _LEVEL_RANK[ai_level] else ai_level


def _collect_text(local: Any, ai: AIInspectionResult | None) -> str:
    chunks: list[str] = []
    for finding in getattr(local, "findings", []) or []:
        if getattr(finding, "triggered", False):
            chunks.extend([
                str(getattr(finding, "title", "")),
                str(getattr(finding, "reason", "")),
                str(getattr(finding, "recommendation", "")),
            ])
    if ai:
        chunks.append(ai.operator_summary_fa)
        for finding in ai.visual_findings:
            chunks.extend([finding.type, finding.title_fa, finding.evidence_fa, *finding.possible_causes_fa])
    return " ".join(chunks).lower()


def _playbook(text: str, ai: AIInspectionResult | None, predictive: bool) -> list[str]:
    actions: list[str] = []
    if any(key in text for key in ("foreign", "contamin", "metal fragment", "plastic fragment")):
        actions.extend([
            "محصول مشکوک را مطابق دستورالعمل مصوب کارخانه جدا و شناسایی کنید.",
            "فوراً واحد کنترل کیفیت و سرپرست شیفت را مطلع کنید.",
            "آخرین نقطه کنترل سالم و محدوده محصول احتمالاً تحت‌تأثیر را مشخص کنید.",
        ])
    elif any(key in text for key in ("fat separation", "emulsion", "oil separation")):
        actions.extend([
            "دمای خمیر و زمان اختلاط را با دستور ساخت مصوب مقایسه کنید.",
            "وضعیت میکسر، تیغه‌ها و ترتیب افزودن مواد را بررسی کنید.",
            "تا پایان تأیید کنترل کیفیت، نمونه‌برداری را مطابق دستورالعمل کارخانه افزایش دهید.",
        ])
    elif any(key in text for key in ("air pocket", "bubble", "void")):
        actions.extend([
            "سیستم خلأ و احتمال ورود ناخواسته هوا را بررسی کنید.",
            "زمان اختلاط و شرایط پرکنی را با حدود مصوب مقایسه کنید.",
            "یک نمونه جدید برای بررسی و تأیید کنترل کیفیت آماده کنید.",
        ])
    elif any(key in text for key in ("seal", "vacuum", "packag")):
        actions.extend([
            "فک‌های دوخت، دمای دوخت و فشار بسته‌بندی را بررسی کنید.",
            "بسته‌های مشکوک را جدا و آزمون مصوب سلامت بسته‌بندی را انجام دهید.",
            "پس از اصلاح، پیش از ادامه تولید عادی یک نمونه تأییدی ثبت کنید.",
        ])
    elif any(key in text for key in ("label", "barcode", "date", "expiry")):
        actions.extend([
            "چاپگر، حسگر لیبل و اطلاعات بچ را بررسی کنید.",
            "محصولات دارای اطلاعات ناقص یا نادرست را جدا کنید.",
            "پیش از آزادسازی محصول، تأیید کنترل کیفیت دریافت شود.",
        ])
    elif any(key in text for key in ("temperature", "cook", "thermal")):
        actions.extend([
            "دما را با حسگر معتبر یا مقدار PLC تأیید کنید و فقط به تصویر نمایشگر تکیه نکنید.",
            "محصول احتمالاً تحت‌تأثیر را مطابق دستورالعمل کارخانه نگه‌داری یا جدا کنید.",
            "پیش از تصمیم درباره ادامه تولید، کنترل کیفیت و مسئول فرایند را مطلع کنید.",
        ])
    else:
        actions.extend([
            "نمونه مشکوک را جدا کرده و برای بررسی کنترل کیفیت نگه دارید.",
            "شرایط فرایند را با تنظیمات مصوب این ایستگاه مقایسه کنید.",
            "پس از اقدام اصلاحی، یک نمونه جدید ثبت و بررسی کنید.",
        ])

    if predictive:
        actions.insert(0, "روند کیفیت به محدوده نامطلوب نزدیک می‌شود؛ نمونه‌برداری را مطابق دستورالعمل افزایش دهید.")

    if ai:
        for action in ai.recommended_actions:
            message = action.message_fa.strip()
            if message and message not in actions:
                actions.append(message)
    return actions[:4]


def _decision_to_alert(decision, local: Any, ai: AIInspectionResult | None, predictive: bool = False) -> OperatorAlertDecision:
    if decision.level in {"stable", "monitor"}:
        return OperatorAlertDecision(level="silent", should_speak=False, reason=decision.headline_fa, predictive=predictive)
    ai_level = _ai_level(ai)
    level = "critical" if decision.level == "critical" or ai_level == "critical" else "high" if decision.level == "high" or ai_level == "high" else "warning"
    text = _collect_text(local, ai)
    actions = _playbook(text, ai, predictive=predictive)
    if level == "critical":
        voice = "هشدار بحرانی کیفیت. فرایند را متوقف کرده و فوراً واحد کنترل کیفیت را مطلع کنید."
    elif level == "high":
        voice = "هشدار سطح بالا. شاخص‌های کیفیت در محدوده نامطلوب هستند. فرایند و محصول را فوراً بررسی کنید."
    else:
        voice = "هشدار سطح متوسط کیفیت. محصول و شرایط فرایند را بررسی کنید."
    return OperatorAlertDecision(level=level, should_speak=True, voice_message_fa=voice, immediate_actions_fa=actions, reason=decision.headline_fa, predictive=predictive)


def evaluate_image_alert(local: Any, ai: AIInspectionResult | None) -> OperatorAlertDecision:
    health = float(getattr(local, "visual_health_score", 100.0) or 0.0)
    critical_override = any(getattr(f, "triggered", False) and _normalise(getattr(f, "severity", "")) == "critical" for f in (getattr(local, "findings", []) or []))
    decision = classify_quality(health, critical_override=critical_override)
    if ai is not None and _ai_level(ai) in {"warning", "high", "critical"} and decision.level in {"stable", "monitor"}:
        # An explicit specialist review may escalate the result, but local minor
        # findings alone cannot contradict a healthy fused score.
        from visionqc.analysis.decision_fusion import QualityDecision
        ai_level = _ai_level(ai)
        decision = QualityDecision(health, "هشدار سطح متوسط" if ai_level == "warning" else "هشدار سطح بالا" if ai_level == "high" else "بحرانی", ai_level, True, ai_level == "warning", "بازبینی هوش مصنوعی یک مورد قابل اقدام را تأیید کرده است.")
    return _decision_to_alert(decision, local, ai, predictive=False)


def evaluate_video_alert(local: Any, ai: AIInspectionResult | None) -> OperatorAlertDecision:
    health = float(getattr(local, "overall_health_score", 100.0) or 0.0)
    stability = float(getattr(local, "process_stability", 100.0) or 0.0)
    events = getattr(local, "events", []) or []
    critical_override = any(_normalise(getattr(event, "severity", "")) == "critical" for event in events)
    predictive = health < 70.0 or stability < 70.0
    decision = classify_quality(health, critical_override=critical_override)
    return _decision_to_alert(decision, local, ai, predictive=predictive)


def record_operator_event(source: str, local: Any, ai: AIInspectionResult | None, decision: OperatorAlertDecision) -> Path:
    path = app_data_dir() / "operator_monitoring_events.jsonl"
    payload = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "decision": decision.to_dict(),
        "local_analysis": local.to_dict() if hasattr(local, "to_dict") else {},
        "gemini_analysis": ai.to_dict() if ai else None,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path
