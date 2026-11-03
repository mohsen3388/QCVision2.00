from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import AIInspectionResult

APPROVED_ACTIONS = {
    "CHECK_PROCESS_STAGE": "مرحله فرایند توسط اپراتور تأیید شود.",
    "CHECK_VACUUM": "وضعیت و مقدار خلأ بررسی و ثبت شود.",
    "CHECK_TEMPERATURE": "دمای محصول با ابزار کالیبره بررسی شود.",
    "CHECK_MIXING_TIME": "زمان اختلاط با دستور ساخت مقایسه شود.",
    "CHECK_MIXER_SPEED": "سرعت میکسر با دستور ساخت مقایسه شود.",
    "IMPROVE_LIGHTING": "نور و زاویه دوربین اصلاح و تصویر تکرار شود.",
    "CAPTURE_NEW_IMAGE": "یک تصویر واضح‌تر و بدون بازتاب شدید ثبت شود.",
    "COMPARE_GOLDEN_BATCH": "تصویر با بچ مرجع همان محصول و همان مرحله مقایسه شود.",
    "REQUEST_MANUAL_REVIEW": "بررسی دستی اپراتور انجام شود.",
    "REQUEST_QC_REVIEW": "نتیجه برای مسئول کنترل کیفیت ارسال شود.",
    "NO_PROCESS_CHANGE": "صرفاً بر اساس این تحلیل، تغییری در فرایند اعمال نشود.",
}

@dataclass(slots=True)
class FinalDecision:
    status: str
    confidence: float
    summary_fa: str
    approved_actions_fa: list[str] = field(default_factory=list)
    warnings_fa: list[str] = field(default_factory=list)


def make_final_decision(result: AIInspectionResult) -> FinalDecision:
    status = result.status
    warnings: list[str] = []
    if result.confidence < 60:
        status = "manual_review"
        warnings.append("اعتماد تحلیل پایین است؛ تصمیم تولیدی بر اساس این نتیجه مجاز نیست.")
    if result.manual_review_required and status == "acceptable":
        status = "attention"
    approved: list[str] = []
    for action in result.recommended_actions:
        approved_text = APPROVED_ACTIONS.get(action.action_code)
        if approved_text and approved_text not in approved:
            approved.append(approved_text)
    if not approved:
        approved = [APPROVED_ACTIONS["REQUEST_MANUAL_REVIEW"], APPROVED_ACTIONS["NO_PROCESS_CHANGE"]]
    if result.manual_review_required and APPROVED_ACTIONS["REQUEST_MANUAL_REVIEW"] not in approved:
        approved.append(APPROVED_ACTIONS["REQUEST_MANUAL_REVIEW"])
    return FinalDecision(status, result.confidence, result.operator_summary_fa, approved, warnings)
