from __future__ import annotations

import json
from typing import Any

INSPECTION_SCHEMA = {
    "status": "acceptable | attention | manual_review | critical",
    "confidence": "number from 0 to 100",
    "operator_summary_fa": "خلاصه کوتاه و روشن به زبان فارسی",
    "visual_findings": [{
        "type": "stable_snake_case_code",
        "title_fa": "عنوان فارسی",
        "severity": "information | low | medium | high | critical",
        "confidence": "number from 0 to 100",
        "evidence_fa": "شرح شواهد قابل مشاهده به زبان فارسی",
        "possible_causes_fa": ["possible cause; not a confirmed diagnosis"],
    }],
    "recommended_actions": [{
        "action_code": "one of the allowed codes",
        "priority": "integer where 1 is highest",
        "message_fa": "اقدام ایمن و کوتاه به زبان فارسی",
        "requires_authorization": True,
    }],
    "manual_review_required": True,
    "limitations_fa": ["محدودیت‌های این ارزیابی بصری به زبان فارسی"],
}

ALLOWED_ACTIONS = [
    "CHECK_PROCESS_STAGE", "CHECK_VACUUM", "CHECK_TEMPERATURE",
    "CHECK_MIXING_TIME", "CHECK_MIXER_SPEED", "IMPROVE_LIGHTING",
    "CAPTURE_NEW_IMAGE", "COMPARE_GOLDEN_BATCH", "REQUEST_MANUAL_REVIEW",
    "REQUEST_QC_REVIEW", "NO_PROCESS_CHANGE",
]


def build_inspection_prompt(process_data: dict[str, Any] | None, opencv_context: dict[str, Any] | None) -> str:
    process_data = process_data or {}
    opencv_context = opencv_context or {}
    return f"""
You are the visual-analysis component of VisionQC, an industrial decision-support application for sausage batter inside stainless-steel mixing kettles.

Analyze only what can reasonably be inferred from the supplied image and context. Look for visual uniformity, bubble-like regions, oily/fat-separation-like regions, unusual color variation, foreign-object-like regions, reflections, blur, occlusion, and capture-quality problems.

When process context says temporal_contact_sheet=true, the image is a chronological contact sheet of recent live-camera frames, ordered from oldest to newest. In that mode:
- Compare frames as one continuous process session, not as unrelated photographs.
- Describe whether the process is stable, improving, deteriorating, or rapidly deteriorating.
- Identify when a visible change first appears and whether it persists or intensifies.
- Use rolling_metrics and previous_gemini_summary as temporal memory.
- Include the trend classification and near-term quality-risk forecast in operator_summary_fa.
- Do not claim a trend from a single ambiguous reflection, fold, or motion artifact.

Mandatory safety rules:
- Never claim microbiological, chemical, nutritional, or laboratory-confirmed food safety.
- Never approve or reject a production batch autonomously.
- Distinguish visible evidence from possible causes.
- Reflections, folds, shadows and active mixing may create false candidates.
- When evidence is weak, confidence must be low and manual_review_required must be true.
- Recommended actions must be non-destructive checks only and use an allowed action code.
- همه فیلدهای توضیحی و تمام متن‌های قابل نمایش یا قابل پخش برای اپراتور را فقط به زبان فارسی روان بنویس. کدهای فنی، status، severity و action_code باید همان مقادیر انگلیسی تعریف‌شده در schema باقی بمانند.

Process context supplied by operator:
{json.dumps(process_data, ensure_ascii=False, indent=2)}

OpenCV / VisionQC measurements supplied by software:
{json.dumps(opencv_context, ensure_ascii=False, indent=2)}

Allowed action codes:
{json.dumps(ALLOWED_ACTIONS)}

Return ONLY one valid JSON object matching this shape:
{json.dumps(INSPECTION_SCHEMA, ensure_ascii=False, indent=2)}
""".strip()


def build_chat_prompt(question: str, inspection: dict[str, Any] | None, local_context: dict[str, Any] | None) -> str:
    return f"""
You are VisionQC's Persian-speaking operator assistant. Answer the operator's question in clear, concise Persian using the supplied visual inspection and local OpenCV context. Do not invent measurements or claim laboratory food safety. Do not issue autonomous machine-control commands. Explain uncertainty and recommend only safe checks or qualified QC review.

Operator question:
{question}

Latest Gemini visual inspection:
{json.dumps(inspection or {}, ensure_ascii=False, indent=2)}

Local VisionQC context:
{json.dumps(local_context or {}, ensure_ascii=False, indent=2)}

Return ONLY valid JSON with this shape:
{{
  "answer_fa": "پاسخ روشن و کوتاه به زبان فارسی",
  "evidence_fa": ["evidence used"],
  "suggested_actions_fa": ["safe next action"],
  "confidence": 0,
  "safety_note_fa": "محدودیت کوتاه به زبان فارسی"
}}
""".strip()
