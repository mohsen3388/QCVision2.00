from __future__ import annotations

from visionqc.models.results import RuleFinding


def evaluate_rules(metrics: dict[str, dict[str, float]]) -> list[RuleFinding]:
    q, c, t, s = metrics["Image Quality"], metrics["Color"], metrics["Texture"], metrics["Surface"]
    findings: list[RuleFinding] = []

    def add(rule_id: str, title: str, severity: str, triggered: bool, confidence: float,
            reason: str, evidence: dict, recommendation: str,
            source: str = "دانش بصری عمومی") -> None:
        findings.append(RuleFinding(rule_id, title, severity, triggered, round(float(confidence), 2),
                                    reason, evidence, recommendation, source))

    brightness = q["brightness"]
    add("IMG-BRIGHT-001", "روشنایی تصویر خارج از محدوده پیشنهادی است", "Warning",
        brightness < 70 or brightness > 200, min(98, 60 + abs(brightness - 135) / 2),
        "میانگین روشنایی تصویر خارج از محدوده موقت تصویربرداری است.",
        {"brightness": brightness, "preferred_range": "70–200"},
        "پیش از تفسیر کیفیت محصول، نور، زاویه دوربین و نوردهی بررسی شود.")

    focus = q["focus_score"]
    add("IMG-FOCUS-001", "اطمینان پایین از فوکوس تصویر", "Warning", focus < 35,
        min(97, 70 + max(0, 35 - focus)),
        "وضوح ناکافی لبه‌ها می‌تواند قابلیت اعتماد تحلیل بافت و سطح را کاهش دهد.",
        {"focus_score": focus, "minimum": 35, "laplacian": q["sharpness_laplacian"]},
        "لنز تمیز، دوربین ثابت و فوکوس دوباره تنظیم شود.")

    clipping = q["dark_clipping_percent"] + q["light_clipping_percent"]
    add("IMG-EXPOSURE-001", "از دست رفتن جزئیات نوردهی تشخیص داده شد", "Attention", clipping > 5,
        min(99, 75 + clipping), "بخشی از جزئیات در نواحی خیلی تاریک یا خیلی روشن از بین رفته است.",
        {"dark_clipping_percent": q["dark_clipping_percent"], "light_clipping_percent": q["light_clipping_percent"], "maximum_combined": 5},
        "بازتاب‌ها کاهش یابد یا نور و نوردهی تنظیم شود.")

    add("IMG-NOISE-001", "نویز تصویر ممکن است بر جزئیات ظریف اثر بگذارد", "Attention", q["snr_proxy_db"] < 25,
        min(92, 58 + max(0, 25-q["snr_proxy_db"]) * 2),
        "میزان نویز نسبت به شدت متوسط تصویر بالاست.",
        {"snr_proxy_db": q["snr_proxy_db"], "noise_std": q["noise_std"], "minimum_snr_proxy": 25},
        "نور افزایش یابد، Gain حسگر کاهش یابد یا پایه دوربین پایدارتر شود.")

    uniformity = c["color_uniformity"]
    add("COLOR-UNIFORM-001", "تغییرات رنگ نیازمند بازبینی است", "Attention", uniformity < 65,
        min(94, 65 + max(0, 65-uniformity)),
        "تغییرات کانال‌های رنگی از آستانه موقت یکنواختی بیشتر است.",
        {"color_uniformity": uniformity, "lab_chroma_std": c["lab_chroma_std"], "minimum": 65},
        "یکنواختی اختلاط بررسی و با نمونه مرجع تأییدشده مقایسه شود.")

    add("COLOR-SAT-001", "ناحیه بزرگ با اشباع رنگ پایین", "Attention", c["low_saturation_percent"] > 45,
        min(90, 45 + c["low_saturation_percent"]),
        "بخش بزرگی از ناحیه بررسی اشباع رنگ کمی دارد؛ این وضعیت می‌تواند ناشی از ظاهر محصول یا بازتاب نور باشد.",
        {"low_saturation_percent": c["low_saturation_percent"], "threshold": 45},
        "با پروفایل محصول مقایسه و بازتاب‌های نور بررسی شود.")

    texture_uniformity = t["texture_uniformity"]
    add("TEXTURE-UNIFORM-001", "یکنواختی بافت پایین‌تر از سطح پیشنهادی است", "Attention", texture_uniformity < 60,
        min(95, 65 + max(0, 60-texture_uniformity)),
        "تغییرات موضعی شدت تصویر نشان‌دهنده بافت بصری نایکنواخت است.",
        {"texture_uniformity": texture_uniformity, "local_variation": t["local_variation"], "minimum": 60},
        "مرحله اختلاط، وضعیت سطح و بازتاب‌های دوربین بررسی شود.")

    add("TEXTURE-HETERO-001", "ناهمگنی شدید بافت", "Warning",
        t["glcm_contrast"] > 8 and t["glcm_homogeneity"] < 0.55,
        min(92, 55 + t["glcm_contrast"] * 2),
        "شاخص‌های GLCM به‌طور هم‌زمان کنتراست موضعی بالا و همگنی پایین را نشان می‌دهند.",
        {"glcm_contrast": t["glcm_contrast"], "glcm_homogeneity": t["glcm_homogeneity"], "lbp_entropy": t["lbp_entropy"]},
        "نقشه حرارتی بررسی و ناحیه تصویر با بچ مرجع پذیرفته‌شده مقایسه شود.")

    bubbles = s["bubble_candidate_density"]
    bubble_conf = max(25, min(84, 35 + bubbles/2 - s["specular_reflection_percent"]/3))
    add("SURFACE-BUBBLE-001", "احتمال افزایش نواحی شبیه حباب", "Warning", bubbles > 18,
        bubble_conf,
        "ساختارهای دایره‌ای تشخیص داده شد، اما چین‌خوردگی‌ها و بازتاب‌ها می‌توانند هشدار کاذب ایجاد کنند.",
        {"candidate_count": s["bubble_candidate_count"], "candidate_density": bubbles,
         "specular_reflection_percent": s["specular_reflection_percent"], "provisional_threshold": 18},
        "پیش از تصمیم‌گیری درباره بچ، بازبینی دستی انجام و مرحله صحیح فرایند انتخاب شود.")

    oil = s["oily_region_candidate_percent"]
    add("SURFACE-OIL-001", "احتمال وجود نواحی روغنی یا بسیار بازتابنده", "Attention", oil > 12,
        min(90, 45 + oil*2),
        "نواحی روشن با اشباع پایین از آستانه موقت عبور کرده‌اند.",
        {"candidate_percent": oil, "region_count": s["bright_low_saturation_region_count"],
         "largest_region_percent": s["largest_bright_region_percent"], "threshold": 12},
        "سطح بررسی و بازتاب نور به‌عنوان علت احتمالی حذف یا تأیید شود.")

    add("SURFACE-REFLECT-001", "بازتاب آینه‌ای شدید", "Attention", s["specular_reflection_percent"] > 8,
        min(95, 55 + s["specular_reflection_percent"]*3),
        "بازتاب‌های شدید می‌توانند جزئیات سطح را پنهان کرده و هشدار کاذب حباب یا روغن ایجاد کنند.",
        {"specular_reflection_percent": s["specular_reflection_percent"], "threshold": 8},
        "زاویه نور تغییر کند، پخش‌کننده نور اضافه شود یا موقعیت دوربین اصلاح شود.")
    return findings
