from visionqc.ai.schemas import AIInspectionResult
from visionqc.ui.gemini_review_formatter import format_gemini_qc_summary, format_gemini_technical_report


def _result():
    return AIInspectionResult.from_dict({
        'status':'attention', 'confidence':81, 'operator_summary_fa':'Possible surface reflectivity.',
        'visual_findings':[{
            'type':'surface_reflectivity','title_fa':'Elevated surface reflectivity','severity':'medium',
            'confidence':80,'evidence_fa':'Glossy patches were observed.',
            'possible_causes_fa':['Moist surface reflection','Steam interference']
        }],
        'recommended_actions':[{
            'action_code':'REQUEST_MANUAL_REVIEW','priority':1,
            'message_fa':'Inspect the batter surface and verify temperature.','requires_authorization':False
        }],
        'manual_review_required':True,
        'limitations_fa':['Steam reduces image clarity.']
    })


def test_qc_summary_is_concise_and_actionable():
    text = format_gemini_qc_summary(_result())
    assert 'خلاصه مدیریتی هوش مصنوعی' in text
    assert 'یافته اصلی:' in text
    assert 'یافته‌های بصری:' not in text
    assert len(text) < 900


def test_technical_report_preserves_evidence_and_limitations():
    text = format_gemini_technical_report(_result())
    assert 'گزارش فنی جمنای' in text
    assert 'شواهد:' in text
    assert 'محدودیت‌ها:' in text
