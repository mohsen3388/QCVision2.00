from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class IndicatorScore:
    key: str
    title_fa: str
    score: float
    detail_fa: str


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


def _m(result, group: str, name: str, default: float = 0.0) -> float:
    return float(result.metrics.get(group, {}).get(name, default))


def score_indicators(result, sample, history: list) -> list[IndicatorScore]:
    iq = result.metrics.get("Image Quality", {})
    focus = _clamp(iq.get("focus_score", min(100.0, iq.get("sharpness_laplacian", getattr(sample, "sharpness", 0.0)) / 4.0)))
    exposure = _clamp(iq.get("exposure_quality", max(0.0, 100.0 - abs(float(getattr(sample, "brightness", 128.0)) - 128.0) * 0.75)))
    noise = float(iq.get("noise_mean_absolute", 0.0))
    image_quality = _clamp(0.42*focus + 0.42*exposure + 0.16*(100-min(100, noise*5)))
    raw_color = _clamp(_m(result, "Color", "color_uniformity", getattr(sample, "color_uniformity", 0.0)))
    raw_texture = _clamp(_m(result, "Texture", "texture_uniformity", getattr(sample, "texture_uniformity", 0.0)))
    color = raw_color
    texture = raw_texture
    bubbles = _m(result, "Surface", "bubble_candidate_density", getattr(sample, "bubble_candidate_density", 0.0))
    oil = _m(result, "Surface", "oily_region_candidate_percent", getattr(sample, "oily_region_candidate_percent", 0.0))
    spec = _m(result, "Surface", "specular_reflection_percent", 0.0)
    # For still images there is no temporal baseline, so conservative absolute
    # scoring is used. For video/camera streams, reflections and circular folds
    # are common and must be judged relative to the accepted opening baseline.
    baseline = history[:min(5, len(history))] if history else []
    if baseline:
        base_color = median([float(x.color_uniformity) for x in baseline])
        base_texture = median([float(x.texture_uniformity) for x in baseline])
        color_consistency = _clamp(100.0 - abs(raw_color - base_color) * 2.5)
        texture_consistency = _clamp(100.0 - abs(raw_texture - base_texture) * 2.5)
        # In video, consistency relative to the accepted opening condition is
        # more meaningful than an uncalibrated absolute texture number.
        color = _clamp(0.20 * raw_color + 0.80 * color_consistency)
        texture = _clamp(0.20 * raw_texture + 0.80 * texture_consistency)
        base_bubbles = median([float(x.bubble_candidate_density) for x in baseline])
        base_oil = median([float(x.oily_region_candidate_percent) for x in baseline])
        bubble_delta = max(0.0, bubbles - base_bubbles)
        oil_delta = max(0.0, oil - base_oil)
        # Only sustained growth away from the video's own baseline lowers health.
        aeration = _clamp(100 - min(100, bubble_delta * 10.0))
        surface = _clamp(100 - min(100, oil_delta * 9.0 + max(0.0, spec - 12.0) * 0.8))
    else:
        aeration = _clamp(100 - min(100, bubbles * 4.0))
        surface = _clamp(100 - min(100, oil * 3.4 + spec * 2.0))
    raw_motion = _clamp(getattr(sample, "motion_stability", 100.0))
    raw_mixing = _clamp(getattr(sample, "mixing_coverage", 100.0))
    motion = raw_motion
    mixing = raw_mixing
    if baseline:
        base_motion = median([float(getattr(x, "motion_stability", raw_motion)) for x in baseline])
        base_mixing = median([float(getattr(x, "mixing_coverage", raw_mixing)) for x in baseline])
        motion = _clamp(0.25 * raw_motion + 0.75 * (100.0 - abs(raw_motion - base_motion) * 1.5))
        mixing = _clamp(0.25 * raw_mixing + 0.75 * (100.0 - abs(raw_mixing - base_mixing) * 1.5))

    recent = history[-60:] if history else [sample]
    health_values = [float(x.visual_health_score) for x in recent]
    texture_values = [float(x.texture_uniformity) for x in recent]
    color_values = [float(x.color_uniformity) for x in recent]
    variation = (
        (max(health_values)-min(health_values) if health_values else 0) +
        (max(texture_values)-min(texture_values) if texture_values else 0) +
        (max(color_values)-min(color_values) if color_values else 0)
    ) / 3.0
    process = _clamp(100 - variation*1.8)

    if baseline:
        diffs = [
            abs(float(sample.visual_health_score)-median([float(x.visual_health_score) for x in baseline])),
            abs(float(sample.texture_uniformity)-median([float(x.texture_uniformity) for x in baseline])),
            abs(float(sample.color_uniformity)-median([float(x.color_uniformity) for x in baseline])),
            abs(float(sample.bubble_candidate_density)-median([float(x.bubble_candidate_density) for x in baseline]))*2.0,
            abs(float(sample.oily_region_candidate_percent)-median([float(x.oily_region_candidate_percent) for x in baseline]))*2.0,
        ]
        reference = _clamp(100 - sum(diffs)/len(diffs)*2.0)
    else:
        reference = _clamp(sample.visual_health_score)

    health = _clamp(sample.visual_health_score)
    trend_penalty = 0.0
    if len(recent) >= 4:
        trend_penalty = max(0.0, float(recent[-4].visual_health_score)-float(recent[-1].visual_health_score))*2.0
    risk_control = _clamp(0.28*health + 0.16*texture + 0.12*color + 0.14*surface + 0.10*aeration + 0.10*motion + 0.10*process - trend_penalty)

    return [
        IndicatorScore("image", "کیفیت تصویر", image_quality, "قابلیت اعتماد تصویر"),
        IndicatorScore("color", "ثبات رنگ", color, "یکنواختی رنگ محصول"),
        IndicatorScore("texture", "یکنواختی بافت", texture, "پایداری بافت"),
        IndicatorScore("surface", "سلامت سطح", surface, "روغنی‌شدن و بازتاب غیرعادی"),
        IndicatorScore("aeration", "سلامت هوادهی", aeration, "نشانه‌های حباب مشکوک"),
        IndicatorScore("motion", "ثبات حرکت", motion, "هماهنگی حرکت فرایند"),
        IndicatorScore("mixing", "پوشش اختلاط", mixing, "پوشش حرکت در ناحیه بررسی"),
        IndicatorScore("reference", "تطابق با مرجع", reference, "مقایسه با خط مبنای شروع پایش"),
        IndicatorScore("process", "ثبات فرایند", process, "نوسان شاخص‌ها در بازه اخیر"),
        IndicatorScore("lighting", "نوردهی", exposure, "نور مناسب برای تحلیل"),
        IndicatorScore("focus", "وضوح تصویر", focus, "فوکوس و تاری"),
        IndicatorScore("risk", "کنترل ریسک", risk_control, "جمع‌بندی چندشاخصی"),
    ]



def score_still_indicators(result, sample) -> list[IndicatorScore]:
    """Conservative single-frame scoring.

    A still image cannot prove motion, process stability or bubble growth. Those
    indicators therefore use neutral spatial proxies and never allow one
    uncorroborated circle detector to collapse the managerial score.
    """
    iq = result.metrics.get("Image Quality", {})
    focus = _clamp(iq.get("focus_score", min(100.0, iq.get("sharpness_laplacian", 0.0) / 3.0)))
    exposure = _clamp(iq.get("exposure_quality", 100.0 - abs(float(iq.get("brightness_mean", 128.0)) - 128.0) * 0.65))
    noise = float(iq.get("noise_mean_absolute", 0.0))
    image_quality = _clamp(0.36 * focus + 0.46 * exposure + 0.18 * (100.0 - min(100.0, noise * 4.0)))
    color = _clamp(_m(result, "Color", "color_uniformity", getattr(sample, "color_uniformity", 80.0)))
    texture = _clamp(_m(result, "Texture", "texture_uniformity", getattr(sample, "texture_uniformity", 80.0)))
    bubbles = max(0.0, _m(result, "Surface", "bubble_candidate_density", getattr(sample, "bubble_candidate_density", 0.0)))
    oil = max(0.0, _m(result, "Surface", "oily_region_candidate_percent", getattr(sample, "oily_region_candidate_percent", 0.0)))
    spec = max(0.0, _m(result, "Surface", "specular_reflection_percent", 0.0))

    # Reflections are common on wet meat emulsion. Only the excess above a
    # tolerance band is penalised and oil must corroborate the reflection.
    surface_penalty = max(0.0, oil - 4.0) * 2.2 + max(0.0, spec - 18.0) * 0.45
    surface = _clamp(100.0 - min(45.0, surface_penalty))

    # Circle candidates alone are not proof of aeration. Preserve at least a
    # moderate score unless texture/surface evidence supports the hypothesis.
    bubble_penalty = min(35.0, max(0.0, bubbles - 1.5) * 2.0)
    corroboration = max(0.0, 78.0 - texture) * 0.35 + max(0.0, 75.0 - surface) * 0.25
    aeration = _clamp(100.0 - bubble_penalty - corroboration)

    # Spatial proxies are labelled as such in the detail text. They contribute
    # lightly to the score and must not be interpreted as temporal proof.
    mixing = _clamp(0.55 * texture + 0.25 * color + 0.20 * surface)
    motion = _clamp(82.0 + (mixing - 80.0) * 0.25)
    reference = _clamp(getattr(sample, "visual_health_score", 85.0))
    process = _clamp(0.35 * color + 0.35 * texture + 0.30 * surface)
    risk_control = _clamp(0.18 * image_quality + 0.16 * color + 0.20 * texture + 0.16 * surface + 0.10 * aeration + 0.10 * reference + 0.10 * process)

    return [
        IndicatorScore("image", "کیفیت تصویر", image_quality, "قابلیت اعتماد تک‌فریم"),
        IndicatorScore("color", "ثبات رنگ", color, "یکنواختی رنگ در تصویر"),
        IndicatorScore("texture", "یکنواختی بافت", texture, "پایداری فضایی بافت"),
        IndicatorScore("surface", "سلامت سطح", surface, "بازتاب و ناحیه روغنی با تحمل صنعتی"),
        IndicatorScore("aeration", "سلامت هوادهی", aeration, "احتمال حباب؛ نیازمند تأیید زمانی"),
        IndicatorScore("motion", "ثبات حرکت", motion, "برآورد غیرزمانی؛ در ویدئو دقیق‌تر است"),
        IndicatorScore("mixing", "پوشش اختلاط", mixing, "برآورد فضایی از توزیع محصول"),
        IndicatorScore("reference", "تطابق با مرجع", reference, "تطابق با سلامت بصری و مرجع موجود"),
        IndicatorScore("process", "ثبات فرایند", process, "برآورد تک‌فریم؛ روند زمانی در دسترس نیست"),
        IndicatorScore("lighting", "نوردهی", exposure, "نور مناسب برای تحلیل"),
        IndicatorScore("focus", "وضوح تصویر", focus, "فوکوس و تاری"),
        IndicatorScore("risk", "کنترل ریسک", risk_control, "جمع‌بندی محافظه‌کارانه تک‌فریم"),
    ]


def summarize_temporal_indicators(history: list) -> list[IndicatorScore]:
    """Build stable end-of-video scores from the median of recent samples.

    This prevents a single reflective or blurred frame from defining the final
    managerial decision. The first samples act as the session baseline.
    """
    if not history:
        return []
    from types import SimpleNamespace
    all_scores = []
    for idx, sample in enumerate(history):
        pseudo = SimpleNamespace(metrics={})
        all_scores.append(score_indicators(pseudo, sample, history[:idx + 1]))
    by_key = {}
    for group in all_scores:
        for item in group:
            by_key.setdefault(item.key, {"title": item.title_fa, "detail": item.detail_fa, "values": []})["values"].append(float(item.score))
    return [
        IndicatorScore(key, data["title"], _clamp(median(data["values"])), data["detail"])
        for key, data in by_key.items()
    ]


_INDICATOR_WEIGHTS = {
    "image": 0.05, "color": 0.10, "texture": 0.18, "surface": 0.14,
    "aeration": 0.09, "motion": 0.12, "mixing": 0.10, "reference": 0.10,
    "process": 0.07, "lighting": 0.02, "focus": 0.01, "risk": 0.02,
}

def aggregate_indicator_score(scores: list[IndicatorScore]) -> float:
    if not scores:
        return 0.0
    values = {item.key: float(item.score) for item in scores}
    total = sum(_INDICATOR_WEIGHTS.get(k, 0.0) * values.get(k, 100.0) for k in _INDICATOR_WEIGHTS)
    # A single genuinely poor core indicator must influence the final decision,
    # while minor isolated fluctuations must not contradict an otherwise healthy process.
    core = [values.get(k, 100.0) for k in ("texture", "surface", "aeration", "motion", "mixing", "reference")]
    ordered_core = sorted(core)
    minimum = ordered_core[0] if ordered_core else 100.0
    second = ordered_core[1] if len(ordered_core) > 1 else 100.0
    # One isolated detector (for example circular reflections interpreted as
    # bubbles) must not collapse the final score. A cap is applied only when a
    # second core indicator corroborates the problem.
    if minimum < 50 and second < 70:
        total = min(total, (minimum + second) / 2.0 + 14.0)
    elif minimum < 70 and second < 80:
        total = min(total, (minimum + second) / 2.0 + 16.0)
    return _clamp(total)

def reasons_fa(scores: list[IndicatorScore]) -> list[str]:
    weak = sorted(scores, key=lambda x: x.score)
    result=[]
    for item in weak:
        if item.score >= 90:
            continue
        if item.score >= 80:
            result.append(f"{item.title_fa} کمی پایین‌تر از محدوده ایده‌آل است ({item.score:.0f}/100).")
        else:
            result.append(f"{item.title_fa} افت معنادار دارد ({item.score:.0f}/100).")
        if len(result) >= 3:
            break
    if not result:
        result = ["رنگ، بافت، سطح و روند فرایند در محدوده پایدار هستند."]
    return result

def recommendations_fa(scores: list[IndicatorScore]) -> list[str]:
    ordered = sorted(scores, key=lambda x: x.score)
    actions=[]
    mapping={
        "image":"لنز، نور و زاویه دوربین را بررسی کنید.",
        "color":"یک نمونه را با محصول مرجع و دستور ساخت مقایسه کنید.",
        "texture":"دمای خمیر، زمان اختلاط و تنظیمات میکسر را بررسی کنید.",
        "surface":"سطح محصول را از نظر جدایش چربی یا آب‌اندازی بازبینی کنید.",
        "aeration":"فشار خلأ و ورود احتمالی هوا به فرایند را بررسی کنید.",
        "motion":"سرعت و یکنواختی حرکت دستگاه را کنترل کنید.",
        "mixing":"ناحیه‌های کم‌تحرک و پوشش اختلاط را بررسی کنید.",
        "reference":"محصول فعلی از خط مبنای شروع پایش فاصله گرفته است؛ نمونه‌برداری انجام دهید.",
        "process":"روند فرایند ناپایدار است؛ تنظیمات اخیر را مرور کنید.",
        "lighting":"نور محیط یا بازتاب روی محصول را اصلاح کنید.",
        "focus":"فوکوس دوربین و تمیزی لنز را بررسی کنید.",
        "risk":"بازبینی کنترل کیفیت و ثبت اقدام اپراتور توصیه می‌شود.",
    }
    for item in ordered[:3]:
        if item.score < 85:
            actions.append(mapping[item.key])
    if not actions:
        actions.append("وضعیت شاخص‌های اصلی پایدار است؛ پایش را ادامه دهید.")
    return actions
