from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import json

LIFECYCLE_STATES = ("Draft", "Testing", "Validated", "Production", "Disabled", "Archived")

@dataclass(slots=True)
class DetectorManifest:
    key: str
    name_fa: str
    name_en: str
    category: str
    unit: str
    supports_image: bool = True
    supports_video: bool = True
    requires_history: bool = False
    description_fa: str = ""
    version: str = "1.0.0"
    parameters: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class ScoringRule:
    mode: str = "higher_is_better"  # higher_is_better/lower_is_better/ideal_range
    raw_min: float = 0.0
    raw_max: float = 1.0
    ideal_low: float | None = None
    ideal_high: float | None = None
    tolerance: float = 0.0

@dataclass(slots=True)
class MetricDefinition:
    key: str
    name_fa: str
    detector_key: str
    group_name: str = "سلامت محصول"
    unit: str = "امتیاز"
    weight: float = 10.0
    sampling_seconds: float = 2.0
    aggregation: str = "median"
    window_seconds: int = 30
    persistence_seconds: int = 8
    deadband: float = 3.0
    roi_name: str = "کل تصویر"
    lifecycle: str = "Draft"
    enabled: bool = True
    scoring: ScoringRule = field(default_factory=ScoringRule)
    detector_params: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

@dataclass(slots=True)
class TriggerCondition:
    metric_key: str
    function: str = "last"  # last/avg/min/max/slope/count_below/count_above
    operator: str = "<"
    threshold: float = 70.0
    window_seconds: int = 30

@dataclass(slots=True)
class TriggerDefinition:
    key: str
    name_fa: str
    severity: str = "هشدار سطح متوسط"
    join_mode: str = "AND"
    conditions: list[TriggerCondition] = field(default_factory=list)
    persistence_seconds: int = 10
    recovery_threshold: float | None = None
    lifecycle: str = "Draft"
    enabled: bool = True
    problem_text: str = ""
    recovery_text: str = ""

@dataclass(slots=True)
class ActionStep:
    step_order: int
    action_type: str  # dashboard/headset/snapshot/video/ai/notify/ack
    target: str = "اپراتور"
    message: str = ""
    delay_seconds: int = 0
    repeat_seconds: int = 0
    require_ack: bool = False

@dataclass(slots=True)
class ActionDefinition:
    key: str
    name_fa: str
    trigger_key: str
    steps: list[ActionStep] = field(default_factory=list)
    lifecycle: str = "Draft"
    enabled: bool = True

@dataclass(slots=True)
class InspectionTemplate:
    key: str
    name_fa: str
    version: str = "1.0.0"
    industry: str = "صنایع غذایی"
    process_stage: str = "اختلاط"
    lifecycle: str = "Draft"
    description: str = ""
    metrics: list[MetricDefinition] = field(default_factory=list)
    triggers: list[TriggerDefinition] = field(default_factory=list)
    actions: list[ActionDefinition] = field(default_factory=list)
    product_weight: float = 75.0
    process_weight: float = 25.0
    ai_review_below: float = 80.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "InspectionTemplate":
        metrics=[]
        for m in data.get("metrics", []):
            m=dict(m); m["scoring"] = ScoringRule(**m.get("scoring", {})); metrics.append(MetricDefinition(**m))
        triggers=[]
        for t in data.get("triggers", []):
            t=dict(t); t["conditions"]=[TriggerCondition(**c) for c in t.get("conditions", [])]; triggers.append(TriggerDefinition(**t))
        actions=[]
        for a in data.get("actions", []):
            a=dict(a); a["steps"]=[ActionStep(**s) for s in a.get("steps", [])]; actions.append(ActionDefinition(**a))
        kwargs={k:v for k,v in data.items() if k not in {"metrics","triggers","actions"}}
        return InspectionTemplate(metrics=metrics,triggers=triggers,actions=actions,**kwargs)
