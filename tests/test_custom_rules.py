from visionqc.analysis.custom_rules import CustomRule, RuleCondition, evaluate_custom_rule


def test_and_rule_triggers():
    rule = CustomRule("Surface review", [
        RuleCondition("Surface", "bubble_candidate_density", ">", 18),
        RuleCondition("Texture", "texture_uniformity", "<", 60),
    ])
    metrics = {"Surface": {"bubble_candidate_density": 25}, "Texture": {"texture_uniformity": 51}}
    result = evaluate_custom_rule(rule, metrics)
    assert result.triggered
    assert all(item["matched"] for item in result.condition_results)


def test_scope_prevents_wrong_product():
    rule = CustomRule("Product A only", [RuleCondition("Color", "color_uniformity", "<", 65)], product_name="Product A")
    result = evaluate_custom_rule(rule, {"Color": {"color_uniformity": 40}}, product_name="Product B")
    assert not result.triggered
