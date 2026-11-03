from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from visionqc.analysis.custom_rules import CustomRuleEvaluation


@dataclass(slots=True)
class AssistantContext:
    metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    visual_health_score: float | None = None
    analysis_confidence: float | None = None
    status: str = "Unknown"
    product_name: str = ""
    process_stage: str = ""
    golden_similarity: float | None = None
    custom_rule_results: list[CustomRuleEvaluation] = field(default_factory=list)


@dataclass(slots=True)
class AssistantAnswer:
    title: str
    summary: str
    reasons: list[str]
    actions: list[str]
    confidence: float
    safety_note: str = "این پاسخ فقط برای پشتیبانی تصمیم‌گیری است. تغییرات فرایندی باید توسط واحد تولید یا کنترل کیفیت تأیید شود."


def _triggered_findings(context: AssistantContext) -> list[dict[str, Any]]:
    return [item for item in context.findings if item.get("triggered")]


def _abnormal_metrics(context: AssistantContext) -> list[str]:
    values: list[str] = []
    lookup = [
        ("Image Quality", "focus_score", lambda x: x < 35, "امتیاز فوکوس پایین"),
        ("Image Quality", "brightness", lambda x: x < 70 or x > 200, "روشنایی خارج از محدوده تصویربرداری"),
        ("Color", "color_uniformity", lambda x: x < 65, "یکنواختی رنگ پایین"),
        ("Texture", "texture_uniformity", lambda x: x < 60, "یکنواختی بافت پایین"),
        ("Surface", "bubble_candidate_density", lambda x: x > 18, "افزایش نواحی شبیه حباب"),
        ("Surface", "oily_region_candidate_percent", lambda x: x > 12, "افزایش نواحی روغنی یا بازتابنده"),
        ("Surface", "specular_reflection_percent", lambda x: x > 8, "بازتاب شدید نور"),
    ]
    for group, metric, predicate, label in lookup:
        raw = context.metrics.get(group, {}).get(metric)
        if raw is not None and predicate(float(raw)):
            values.append(f"{label}: {float(raw):.2f}")
    return values


def answer_question(question: str, context: AssistantContext) -> AssistantAnswer:
    query = question.strip().casefold()
    findings = _triggered_findings(context)
    abnormal = _abnormal_metrics(context)
    custom = [item for item in context.custom_rule_results if item.triggered]
    confidence = float(context.analysis_confidence or 50.0)

    reasons = [f"{item.get('title', 'یافته')}: {item.get('reason', '')}" for item in findings[:5]]
    reasons.extend(abnormal[:5])
    reasons.extend([f"قاعده کارخانه «{item.name}» فعال شده است." for item in custom[:3]])
    actions = [item.get("recommendation", "") for item in findings[:4] if item.get("recommendation")]
    actions.extend([item.recommendation for item in custom[:3] if item.recommendation])

    if not context.metrics:
        return AssistantAnswer(
            "اطلاعات تحلیل در دسترس نیست",
            "پیش از طرح پرسش تشخیصی، یک خروجی VisionQC بارگذاری کنید یا تحلیل جدیدی انجام دهید.",
            [],
            ["بخش Deep Image Analysis را باز کرده و یک نمونه را تحلیل کنید."],
            0.0,
        )

    if any(term in query for term in ("bubble", "foam", "حباب")):
        bubble = context.metrics.get("Surface", {}).get("bubble_candidate_density", 0.0)
        reflection = context.metrics.get("Surface", {}).get("specular_reflection_percent", 0.0)
        return AssistantAnswer(
            "بررسی نواحی شبیه حباب",
            f"چگالی نواحی شبیه حباب {bubble:.2f} و میزان بازتاب {reflection:.2f} است. این موارد فقط کاندیداهای بصری هستند و وجود واقعی حباب را به‌طور قطعی تأیید نمی‌کنند.",
            reasons or ["در حال حاضر قاعده مرتبط با حباب فعال نشده است."],
            actions or ["ناحیه موردنظر را به‌صورت دستی بررسی کنید.", "بازتاب نور را کاهش داده و دوباره تصویربرداری کنید.", "نتیجه را با Golden Batch همان مرحله مقایسه کنید."],
            confidence,
        )
    if any(term in query for term in ("abnormal", "metric", "شاخص", "غیرعادی")):
        return AssistantAnswer(
            "بررسی شاخص‌های غیرعادی",
            f"تعداد {len(abnormal)} مورد خروج شاخص از محدوده موقت و {len(custom)} فعال‌شدن قاعده کارخانه شناسایی شد.",
            abnormal or ["هیچ خروج موقت از محدوده شاخص‌ها تشخیص داده نشد."],
            actions or ["یافته‌های فعال و مقایسه با Golden Batch بررسی شود."],
            confidence,
        )
    if any(term in query for term in ("why", "drop", "quality", "افت", "کیفیت", "دلیل")):
        health = "نامشخص" if context.visual_health_score is None else f"{context.visual_health_score:.1f}٪"
        golden = "در دسترس نیست" if context.golden_similarity is None else f"{context.golden_similarity:.1f}٪"
        summary = f"سلامت بصری فعلی {health}، وضعیت {context.status} و شباهت با Golden Batch برابر {golden} است. این توضیح بر پایه یافته‌های بصری فعال و قواعد تنظیم‌شده کارخانه ارائه شده است."
        return AssistantAnswer(
            "توضیح وضعیت کیفیت",
            summary,
            reasons or ["در حال حاضر هیچ قاعده فعالی افت کیفیت را توضیح نمی‌دهد."],
            actions or ["نور و فوکوس بررسی شود.", "محصول و مرحله فرایند تأیید شود.", "پیش از تغییر فرایند، بازبینی واحد کنترل کیفیت انجام شود."],
            confidence,
        )
    if any(term in query for term in ("action", "recommend", "what should", "اقدام", "پیشنهاد")):
        return AssistantAnswer(
            "اقدامات پیشنهادی بعدی",
            "اقدامات بر اساس یافته‌های فعال اولویت‌بندی شده‌اند و فرمان خودکار برای تغییر فرایند نیستند.",
            reasons[:4],
            actions or ["تصویربرداری در نور کنترل‌شده تکرار شود.", "با Golden Batch تأییدشده مقایسه شود.", "یادداشت اپراتور ثبت و بازبینی کنترل کیفیت درخواست شود."],
            confidence,
        )
    return AssistantAnswer(
        "خلاصه وضعیت VisionQC",
        f"وضعیت: {context.status}. سلامت بصری: {context.visual_health_score}. اطمینان تحلیل: {context.analysis_confidence}. یافته‌های داخلی فعال: {len(findings)}. قواعد کارخانه فعال: {len(custom)}.",
        reasons or ["در اطلاعات بارگذاری‌شده هشدار فعالی مشاهده نشد."],
        actions or ["می‌توانید درباره علت افت کیفیت، شاخص‌های غیرعادی، حباب‌ها یا اقدامات پیشنهادی سؤال کنید."],
        confidence,
    )
