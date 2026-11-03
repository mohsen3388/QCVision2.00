from __future__ import annotations
from .models import InspectionTemplate,LIFECYCLE_STATES
from .registry import DetectorRegistry

def validate_template(t:InspectionTemplate, registry:DetectorRegistry)->list[str]:
    errors=[]
    if not t.key.strip(): errors.append("کلید Template خالی است.")
    if t.lifecycle not in LIFECYCLE_STATES: errors.append("وضعیت چرخه عمر نامعتبر است.")
    keys=set()
    for m in t.metrics:
        if m.key in keys: errors.append(f"کلید شاخص تکراری: {m.key}")
        keys.add(m.key)
        try: registry.get(m.detector_key)
        except KeyError: errors.append(f"Detector شاخص {m.name_fa} موجود نیست: {m.detector_key}")
        if m.weight < 0: errors.append(f"وزن منفی: {m.name_fa}")
        if m.lifecycle == "Production" and t.lifecycle not in {"Validated","Production"}: errors.append(f"شاخص Production در Template تأییدنشده: {m.name_fa}")
    for group in {m.group_name for m in t.metrics}:
        total=sum(m.weight for m in t.metrics if m.group_name==group and m.enabled)
        if total and abs(total-100)>0.01: errors.append(f"مجموع وزن گروه «{group}» برابر {total:.1f} است؛ باید 100 باشد.")
    trigger_keys={x.key for x in t.triggers}
    for tr in t.triggers:
        for c in tr.conditions:
            if c.metric_key not in keys: errors.append(f"Trigger {tr.name_fa} به شاخص ناموجود {c.metric_key} وصل است.")
    for a in t.actions:
        if a.trigger_key not in trigger_keys: errors.append(f"Action {a.name_fa} به Trigger ناموجود وصل است.")
    return errors
