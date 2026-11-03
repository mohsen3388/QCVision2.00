from __future__ import annotations

from dataclasses import asdict
import operator
import numpy as np

from visionqc.configuration.models import InspectionTemplate, TriggerCondition

OPS = {'<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge, '==': operator.eq, '!=': operator.ne}


def _window(values: list[tuple[float, float]], seconds: int) -> list[tuple[float, float]]:
    if not values:
        return []
    end = values[-1][0]
    return [(t, v) for t, v in values if t >= end - max(1, seconds)]


def condition_value(c: TriggerCondition, history: dict[str, list[tuple[float, float]]]) -> float:
    data = _window(history.get(c.metric_key, []), c.window_seconds)
    vals = np.asarray([v for _, v in data if np.isfinite(v)], dtype=float)
    if vals.size == 0:
        return float('nan')
    fn = c.function
    if fn == 'last': return float(vals[-1])
    if fn == 'avg': return float(np.mean(vals))
    if fn == 'median': return float(np.median(vals))
    if fn == 'min': return float(np.min(vals))
    if fn == 'max': return float(np.max(vals))
    if fn == 'count_below': return float(np.sum(vals < c.threshold))
    if fn == 'count_above': return float(np.sum(vals > c.threshold))
    if fn == 'slope':
        if vals.size < 2: return 0.0
        ts = np.asarray([t for t, v in data if np.isfinite(v)], dtype=float)
        ts -= ts[0]
        return float(np.polyfit(ts, vals, 1)[0]) if ts[-1] > 0 else 0.0
    raise ValueError(f'Unsupported trigger function: {fn}')


def evaluate_triggers(template: InspectionTemplate, history: dict[str, list[tuple[float, float]]]) -> list[dict]:
    results = []
    for tr in template.triggers:
        if not tr.enabled:
            continue
        evidence = []
        states = []
        sufficient = True
        for c in tr.conditions:
            value = condition_value(c, history)
            ok = bool(np.isfinite(value) and OPS.get(c.operator, operator.lt)(value, c.threshold))
            samples = len(_window(history.get(c.metric_key, []), c.window_seconds))
            if samples == 0:
                sufficient = False
            evidence.append({'condition': asdict(c), 'value': None if not np.isfinite(value) else round(float(value), 3), 'matched': ok, 'samples': samples})
            states.append(ok)
        active = sufficient and (all(states) if tr.join_mode.upper() == 'AND' else any(states))
        results.append({'key': tr.key, 'name': tr.name_fa, 'severity': tr.severity, 'active': active, 'problem_text': tr.problem_text, 'evidence': evidence})
    return results


def actions_for_active_triggers(template: InspectionTemplate, trigger_results: list[dict]) -> list[dict]:
    active = {x['key'] for x in trigger_results if x['active']}
    return [asdict(a) for a in template.actions if a.enabled and a.trigger_key in active]
