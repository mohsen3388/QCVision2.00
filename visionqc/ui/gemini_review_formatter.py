from __future__ import annotations

from visionqc.ai.schemas import AIInspectionResult


def _main_finding(result: AIInspectionResult) -> str:
    if result.visual_findings:
        return result.visual_findings[0].title_fa or result.visual_findings[0].type.replace("_", " ")
    return result.operator_summary_fa or "یافته بصری مشخصی گزارش نشد."


def _possible_causes(result: AIInspectionResult, limit: int = 3) -> list[str]:
    causes: list[str] = []
    for finding in result.visual_findings:
        for cause in finding.possible_causes_fa:
            clean = str(cause).strip()
            if clean and clean not in causes:
                causes.append(clean)
            if len(causes) >= limit:
                return causes
    return causes


def _recommended_action(result: AIInspectionResult) -> str:
    if result.recommended_actions:
        return result.recommended_actions[0].message_fa
    return "پیش از هر تصمیم تولیدی، بازبینی توسط کارشناس کنترل کیفیت انجام شود."


def _status_fa(status: str) -> str:
    return {
        "acceptable": "قابل قبول",
        "attention": "نیازمند توجه",
        "manual_review": "نیازمند بازبینی دستی",
        "critical": "بحرانی",
    }.get(str(status).lower(), str(status))


def _severity_fa(severity: str) -> str:
    return {
        "information": "اطلاع‌رسانی",
        "low": "کم",
        "medium": "متوسط",
        "high": "بالا",
        "critical": "بحرانی",
    }.get(str(severity).lower(), str(severity))


def format_gemini_qc_summary(result: AIInspectionResult | None, error: str = "") -> str:
    """Level 2: concise Persian QC/management summary shown by default."""
    if result is None:
        return (
            "خلاصه مدیریتی هوش مصنوعی\n\n"
            + (f"وضعیت: در دسترس نیست\nعلت: {error}" if error else "وضعیت: در دسترس نیست")
            + "\n\nتحلیل محلی همچنان در دسترس است و نتیجه ثبت شده است."
        )

    lines = [
        "خلاصه مدیریتی هوش مصنوعی",
        "",
        f"وضعیت: {_status_fa(result.status)}",
        f"میزان اطمینان: {result.confidence:.1f}٪",
        "",
        "یافته اصلی:",
        _main_finding(result),
    ]
    causes = _possible_causes(result)
    if causes:
        lines.extend(["", "علت‌های احتمالی:"])
        lines.extend([f"• {cause}" for cause in causes])
    lines.extend([
        "",
        "اقدام پیشنهادی:",
        _recommended_action(result),
        "",
        f"بازبینی دستی: {'پیشنهاد می‌شود' if result.manual_review_required else 'بر اساس بررسی هوش مصنوعی ضروری نیست'}",
    ])
    return "\n".join(lines)


def format_gemini_technical_report(result: AIInspectionResult | None, error: str = "") -> str:
    """Level 3: complete Persian technical report, hidden until explicitly opened."""
    if result is None:
        return (
            "گزارش فنی جمنای\n\n"
            + (f"بررسی در دسترس نیست: {error}" if error else "هیچ بررسی جمنای برای این تحلیل در دسترس نیست.")
            + "\n\nتحلیل محلی همچنان در دسترس است و نتیجه ثبت شده است."
        )

    lines = [
        "گزارش فنی جمنای",
        "",
        f"وضعیت: {_status_fa(result.status)}",
        f"میزان اطمینان: {result.confidence:.1f}٪",
        f"نیاز به بازبینی دستی: {'بله' if result.manual_review_required else 'خیر'}",
        "",
        "ارزیابی اجرایی:",
        result.operator_summary_fa or "ارزیابی اجرایی ارائه نشد.",
        "",
        "یافته‌های بصری:",
    ]
    if not result.visual_findings:
        lines.append("یافته بصری مشخصی گزارش نشد.")
    for index, finding in enumerate(result.visual_findings, 1):
        lines.extend([
            f"{index}. {finding.title_fa}",
            f"   نوع: {finding.type}",
            f"   شدت: {_severity_fa(finding.severity)}",
            f"   میزان اطمینان: {finding.confidence:.1f}٪",
            f"   شواهد: {finding.evidence_fa}",
        ])
        if finding.possible_causes_fa:
            lines.append("   علت‌های احتمالی: " + "؛ ".join(finding.possible_causes_fa))

    lines.extend(["", "بررسی‌ها و اقدامات پیشنهادی:"])
    if not result.recommended_actions:
        lines.append("اقدام مشخصی ارائه نشد؛ بازبینی توسط کارشناس کنترل کیفیت انجام شود.")
    for action in result.recommended_actions:
        authorization = "نیازمند مجوز" if action.requires_authorization else "نیاز به مجوز اضافه اعلام نشده است"
        lines.append(f"- اولویت {action.priority}: {action.message_fa} ({authorization})")

    lines.extend(["", "محدودیت‌ها:"])
    if result.limitations_fa:
        lines.extend([f"- {item}" for item in result.limitations_fa])
    else:
        lines.append("- این ابزار صرفاً پشتیبان تصمیم‌گیری بصری است و جایگزین ارزیابی آزمایشگاهی یا تصمیم کارشناس کنترل کیفیت نیست.")
    return "\n".join(lines)


def format_gemini_review(result: AIInspectionResult | None, error: str = "") -> str:
    return format_gemini_qc_summary(result, error)
