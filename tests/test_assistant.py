from visionqc.assistant import AssistantContext, answer_question


def context():
    return AssistantContext(
        metrics={
            "Image Quality": {"focus_score": 30, "brightness": 130},
            "Color": {"color_uniformity": 55},
            "Texture": {"texture_uniformity": 48},
            "Surface": {"bubble_candidate_density": 26, "oily_region_candidate_percent": 4, "specular_reflection_percent": 3},
        },
        findings=[{"title":"Possible elevated bubble-like regions","triggered":True,"reason":"Circular structures detected.","recommendation":"Request manual review."}],
        visual_health_score=62,
        analysis_confidence=88,
        status="Attention",
    )


def test_quality_explanation_is_grounded():
    answer = answer_question("Why did quality drop?", context())
    assert answer.title == "توضیح وضعیت کیفیت"
    assert answer.confidence == 88
    assert any(("bubble" in reason.lower()) or ("حباب" in reason) for reason in answer.reasons)


def test_no_context_is_explicit():
    answer = answer_question("Why?", AssistantContext())
    assert answer.confidence == 0
    assert "بارگذاری" in answer.summary
