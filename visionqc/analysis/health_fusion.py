from __future__ import annotations

from dataclasses import dataclass

from visionqc.analysis.decision_fusion import clamp
from visionqc.analysis.indicator_scoring import IndicatorScore


@dataclass(frozen=True)
class HealthBreakdown:
    product_health: float
    process_health: float
    final_score: float
    product_weak_count: int
    process_weak_count: int
    still_image: bool = False


_PRODUCT_WEIGHTS = {
    "color": 0.16,
    "texture": 0.24,
    "surface": 0.16,
    "aeration": 0.10,
    "mixing": 0.14,
    "reference": 0.20,
}

_PROCESS_WEIGHTS = {
    "motion": 0.30,
    "process": 0.34,
    "image": 0.14,
    "lighting": 0.08,
    "focus": 0.06,
    "risk": 0.08,
}

_STILL_PRODUCT_WEIGHTS = {
    "color": 0.20,
    "texture": 0.22,
    "surface": 0.20,
    "aeration": 0.05,
    "mixing": 0.08,
    "reference": 0.25,
}

_STILL_RELIABILITY_WEIGHTS = {
    "image": 0.42,
    "lighting": 0.28,
    "focus": 0.20,
    "risk": 0.10,
}


def _weighted(values: dict[str, float], weights: dict[str, float], default: float = 85.0) -> float:
    return clamp(sum(float(weights[k]) * float(values.get(k, default)) for k in weights))


def split_health_scores(scores: list[IndicatorScore], *, still_image: bool = False) -> HealthBreakdown:
    """Separate product condition from process execution.

    Product quality has decision priority. A stable machine or a clear camera may
    increase confidence, but cannot hide a visibly poor product. For still
    images, the second score represents assessment reliability rather than true
    temporal process health.
    """
    values = {item.key: float(item.score) for item in scores}
    product_weights = _STILL_PRODUCT_WEIGHTS if still_image else _PRODUCT_WEIGHTS
    product = _weighted(values, product_weights)
    process = _weighted(values, _STILL_RELIABILITY_WEIGHTS if still_image else _PROCESS_WEIGHTS)

    product_core = sorted(values.get(k, 85.0) for k in product_weights)
    product_weak = sum(1 for x in product_core if x < 80.0)
    process_keys = _STILL_RELIABILITY_WEIGHTS if still_image else _PROCESS_WEIGHTS
    process_weak = sum(1 for k in process_keys if values.get(k, 85.0) < 80.0)

    if still_image:
        # A still frame is intentionally simple: product appearance dominates;
        # image reliability only moderates confidence. One unconfirmed detector
        # is never allowed to turn a healthy-looking frame into a critical case.
        final = 0.86 * product + 0.14 * process
        if len(product_core) >= 2:
            first, second = product_core[0], product_core[1]
            if first < 45 and second < 60:
                final = min(final, 49.0)
            elif first < 60 and second < 70:
                final = min(final, 69.0)

    else:
        final = 0.72 * product + 0.28 * process
        # Product condition is the governing constraint. Good process stability
        # must not mask poor colour, texture, surface or mixing quality.
        if product < 50:
            final = min(final, 49.0)
        elif product < 70:
            final = min(final, 69.0)
        elif product < 80:
            final = min(final, 79.0)

    return HealthBreakdown(
        product_health=clamp(product),
        process_health=clamp(process),
        final_score=clamp(final),
        product_weak_count=product_weak,
        process_weak_count=process_weak,
        still_image=still_image,
    )


def managerial_reasons_fa(scores: list[IndicatorScore], breakdown: HealthBreakdown) -> list[str]:
    values = {x.key: x for x in scores}
    reasons: list[str] = []
    if breakdown.product_health >= 90:
        reasons.append("رنگ، بافت، سطح و توزیع محصول در محدوده مناسب قرار دارند.")
    else:
        product_items = sorted((values[k] for k in _PRODUCT_WEIGHTS if k in values), key=lambda x: x.score)
        for item in product_items[:2]:
            if item.score < 80:
                reasons.append(f"{item.title_fa} پایین‌تر از محدوده مطلوب است ({item.score:.0f}/100).")
    if breakdown.still_image:
        if breakdown.process_health >= 80:
            reasons.append("کیفیت تصویر برای قضاوت تک‌فریم قابل قبول است.")
        else:
            reasons.append("کیفیت تصویر، نور یا فوکوس اطمینان ارزیابی را کاهش داده است.")
    else:
        if breakdown.process_health >= 90:
            reasons.append("حرکت و روند زمانی فرایند پایدار هستند.")
        elif breakdown.process_health < 80:
            reasons.append("اجرای فرایند یا پایداری زمانی نیازمند بررسی است.")
    return reasons[:4]


def decision_action_fa(level: str, *, still_image: bool = False) -> list[str]:
    if level == "stable":
        return ["ادامه تولید و پایش معمول توصیه می‌شود."]
    if level == "monitor":
        return ["اقدام فوری لازم نیست؛ شاخص‌های ضعیف در بررسی بعدی دوباره کنترل شوند."]
    if level == "warning":
        return ["یک نمونه توسط کنترل کیفیت بررسی و با محصول مرجع مقایسه شود."]
    if level == "high":
        return ["ادامه فرایند بدون بررسی اپراتور توصیه نمی‌شود؛ علت شاخص‌های ضعیف بررسی شود."]
    return ["فرایند متوقف و محصول توسط مسئول کنترل کیفیت ارزیابی شود."]
