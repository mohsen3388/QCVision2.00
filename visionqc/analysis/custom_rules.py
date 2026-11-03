from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SUPPORTED_OPERATORS = (">", ">=", "<", "<=", "==", "!=", "between")


@dataclass(slots=True)
class RuleCondition:
    metric_group: str
    metric_name: str
    operator: str
    value: float
    second_value: float | None = None

    def validate(self) -> None:
        if self.operator not in SUPPORTED_OPERATORS:
            raise ValueError(f"Unsupported operator: {self.operator}")
        if self.operator == "between" and self.second_value is None:
            raise ValueError("The between operator requires second_value.")


@dataclass(slots=True)
class CustomRule:
    name: str
    conditions: list[RuleCondition]
    join_mode: str = "AND"
    severity: str = "Warning"
    message: str = "A configured quality condition was triggered."
    recommendation: str = "Request operator review."
    enabled: bool = True
    rule_id: int | None = None
    product_name: str = ""
    process_stage: str = ""

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Rule name is required.")
        if not self.conditions:
            raise ValueError("At least one condition is required.")
        if self.join_mode not in {"AND", "OR"}:
            raise ValueError("join_mode must be AND or OR.")
        for condition in self.conditions:
            condition.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CustomRuleEvaluation:
    rule_id: int | None
    name: str
    triggered: bool
    severity: str
    message: str
    recommendation: str
    condition_results: list[dict[str, Any]] = field(default_factory=list)


def _compare(actual: float, condition: RuleCondition) -> bool:
    target = float(condition.value)
    if condition.operator == ">":
        return actual > target
    if condition.operator == ">=":
        return actual >= target
    if condition.operator == "<":
        return actual < target
    if condition.operator == "<=":
        return actual <= target
    if condition.operator == "==":
        return abs(actual - target) <= 1e-9
    if condition.operator == "!=":
        return abs(actual - target) > 1e-9
    low, high = sorted((target, float(condition.second_value)))
    return low <= actual <= high


def evaluate_custom_rule(rule: CustomRule, metrics: dict[str, dict[str, float]], *, product_name: str = "", process_stage: str = "") -> CustomRuleEvaluation:
    rule.validate()
    applicable = rule.enabled
    if rule.product_name and product_name and rule.product_name.casefold() != product_name.casefold():
        applicable = False
    if rule.process_stage and process_stage and rule.process_stage.casefold() != process_stage.casefold():
        applicable = False

    details: list[dict[str, Any]] = []
    outcomes: list[bool] = []
    for condition in rule.conditions:
        actual_raw = metrics.get(condition.metric_group, {}).get(condition.metric_name)
        if actual_raw is None:
            passed = False
            actual = None
        else:
            actual = float(actual_raw)
            passed = _compare(actual, condition)
        outcomes.append(passed)
        details.append({
            "metric_group": condition.metric_group,
            "metric_name": condition.metric_name,
            "operator": condition.operator,
            "expected": condition.value,
            "second_value": condition.second_value,
            "actual": actual,
            "matched": passed,
        })
    triggered = applicable and (all(outcomes) if rule.join_mode == "AND" else any(outcomes))
    return CustomRuleEvaluation(rule.rule_id, rule.name, triggered, rule.severity, rule.message, rule.recommendation, details)


def evaluate_custom_rules(rules: list[CustomRule], metrics: dict[str, dict[str, float]], *, product_name: str = "", process_stage: str = "") -> list[CustomRuleEvaluation]:
    return [evaluate_custom_rule(rule, metrics, product_name=product_name, process_stage=process_stage) for rule in rules]
