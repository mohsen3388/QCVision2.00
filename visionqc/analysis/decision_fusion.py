from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityDecision:
    score: float
    status_fa: str
    level: str
    requires_ai: bool
    continue_production: bool
    headline_fa: str


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


def classify_quality(score: float, *, critical_override: bool = False) -> QualityDecision:
    score = clamp(score)
    if critical_override or score < 50:
        return QualityDecision(score, "بحرانی", "critical", True, False,
                               "شواهد قوی از وضعیت خارج از محدوده مشاهده شد؛ اقدام فوری لازم است.")
    if score < 70:
        return QualityDecision(score, "هشدار سطح بالا", "high", True, False,
                               "چند شاخص مهم در محدوده نامطلوب قرار دارند؛ بررسی فوری فرایند لازم است.")
    if score < 80:
        return QualityDecision(score, "هشدار سطح متوسط", "warning", True, True,
                               "افت معنادار در شاخص‌های کیفیت مشاهده شد؛ فرایند و محصول بررسی شوند.")
    if score < 90:
        return QualityDecision(score, "نیاز به پایش", "monitor", False, True,
                               "تغییرات جزئی مشاهده شده است؛ اقدام فوری لازم نیست و پایش ادامه یابد.")
    return QualityDecision(score, "پایدار", "stable", False, True,
                           "فرایند پایدار است و ادامه تولید توصیه می‌شود.")


def requires_ai_review(score: float, *, critical_override: bool = False, predictive: bool = False) -> bool:
    """Return True only when the final fused score is below 80.

    The UI promise is intentionally strict: a score of 80 or more never
    consumes cloud quota. Local critical flags remain visible in the decision
    and operator alert, but they do not bypass this quota gate.
    """
    return float(score) < 80.0


def executive_summary_fa(decision: QualityDecision, reasons: list[str] | None = None,
                         actions: list[str] | None = None, confidence: float | None = None,
                         product_health: float | None = None, process_health: float | None = None,
                         process_label_fa: str = "سلامت فرایند") -> str:
    reasons = [x.strip() for x in (reasons or []) if x and x.strip()][:4]
    actions = [x.strip() for x in (actions or []) if x and x.strip()][:3]
    lines = [f"وضعیت کلی: {decision.status_fa}"]
    if product_health is not None:
        lines.append(f"سلامت محصول: {clamp(product_health):.1f} از 100")
    if process_health is not None:
        lines.append(f"{process_label_fa}: {clamp(process_health):.1f} از 100")
    lines.append(f"امتیاز تصمیم نهایی: {decision.score:.1f} از 100")
    if confidence is not None:
        lines.append(f"اطمینان تحلیل: {clamp(confidence):.1f}%")
    lines += ["", decision.headline_fa]
    if reasons:
        lines += ["", "دلیل تصمیم:"] + [f"• {x}" for x in reasons]
    if actions:
        lines += ["", "اقدام پیشنهادی:"] + [f"• {x}" for x in actions]
    return "\n".join(lines)
