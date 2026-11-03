from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np

from .models import InspectionTemplate
from .registry import DetectorRegistry, default_detector_registry
from .scoring import score_value
from .validator import validate_template
from visionqc.quality.reporting import build_management_summary
from visionqc.quality.detectors.temporal import TEMPORAL_FUNCTIONS, temporal_consistency
from visionqc.quality.triggers import evaluate_triggers, actions_for_active_triggers
from visionqc.quality.decision import fuse


class ConfigurationRuntime:
    def __init__(self, registry: DetectorRegistry | None = None):
        self.registry = registry or default_detector_registry()

    def _validate(self, template: InspectionTemplate) -> list[str]:
        errors = validate_template(template, self.registry)
        hard = [e for e in errors if 'مجموع وزن' not in e]
        if hard:
            raise ValueError(' | '.join(hard))
        return errors

    def _static_metrics(self, frame: np.ndarray, template: InspectionTemplate, *, mode: str) -> list[dict]:
        metrics: list[dict] = []
        for metric in template.metrics:
            if not metric.enabled:
                continue
            manifest = self.registry.get(metric.detector_key).manifest
            if manifest.requires_history or (mode == 'image' and not manifest.supports_image):
                metrics.append({'key': metric.key, 'name': metric.name_fa, 'group': metric.group_name, 'raw': None, 'score': None, 'weight': metric.weight, 'status': 'NOT_APPLICABLE'})
                continue
            raw = self.registry.execute(metric.detector_key, frame, metric.detector_params)
            score = score_value(raw, metric.scoring)
            metrics.append({'key': metric.key, 'name': metric.name_fa, 'group': metric.group_name, 'raw': raw, 'score': score, 'weight': metric.weight, 'status': 'OK'})
        return metrics

    @staticmethod
    def _groups(metrics: list[dict]) -> dict[str, float]:
        groups: dict[str, float] = {}
        for group in {x['group'] for x in metrics}:
            values = [x for x in metrics if x['group'] == group and x.get('score') is not None and x.get('status') == 'OK']
            if not values:
                continue
            weight = sum(float(x['weight']) for x in values) or len(values)
            groups[group] = sum(float(x['score']) * float(x['weight'] or 1) for x in values) / weight
        return groups

    def _result(self, metrics: list[dict], template: InspectionTemplate, *, mode: str, history=None, samples=1) -> dict:
        groups = self._groups(metrics)
        product_values = [x['score'] for x in metrics if x['group'] == 'سلامت محصول' and x.get('score') is not None]
        process_values = [x['score'] for x in metrics if x['group'] == 'سلامت فرایند' and x.get('score') is not None]
        product = groups.get('سلامت محصول', float(np.mean(product_values)) if product_values else 0.0)
        process = groups.get('سلامت فرایند', float(np.mean(process_values)) if process_values else product)
        assessability = next((x['score'] for x in metrics if x['key'] == 'process.assessability' and x.get('score') is not None), None)
        trigger_results = evaluate_triggers(template, history or {}) if history else []
        critical_override = any(x['active'] and x['severity'] == 'بحرانی' for x in trigger_results)
        final, status = fuse(product, process, product_weight=template.product_weight, process_weight=template.process_weight, assessability=assessability, critical_override=critical_override)
        active_actions = actions_for_active_triggers(template, trigger_results)
        result = {
            'mode': mode,
            'samples': samples,
            'metrics': metrics,
            'groups': groups,
            'product_health': round(float(product), 2),
            'process_health': round(float(process), 2),
            'image_assessability': None if assessability is None else round(float(assessability), 2),
            'final_score': final,
            'status': status,
            'ai_review_required': bool(final < template.ai_review_below),
            'triggers': trigger_results,
            'active_triggers': [x for x in trigger_results if x['active']],
            'actions': active_actions,
        }
        result['management_summary'] = build_management_summary(result)
        return result

    def analyze_frame(self, frame: np.ndarray, template: InspectionTemplate) -> dict:
        errors = self._validate(template)
        metrics = self._static_metrics(frame, template, mode='image')
        result = self._result(metrics, template, mode='image', samples=1)
        result['validation_warnings'] = errors
        return result

    def analyze_video_frames(self, frames: list[np.ndarray], timestamps: list[float], template: InspectionTemplate) -> dict:
        self._validate(template)
        if not frames:
            raise ValueError('No readable frames')
        per_frame = [self._static_metrics(frame, template, mode='video') for frame in frames]
        history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        aggregate: list[dict] = []
        template_by_key = {m.key: m for m in template.metrics}
        keys = {m['key'] for batch in per_frame for m in batch}
        for key in keys:
            values = [next((m for m in batch if m['key'] == key), None) for batch in per_frame]
            values = [m for m in values if m and m.get('score') is not None]
            if values:
                for ts, item in zip(timestamps, [next((m for m in batch if m['key'] == key), None) for batch in per_frame]):
                    if item and item.get('score') is not None:
                        history[key].append((ts, float(item['score'])))
                base = dict(values[0])
                base['raw'] = float(np.median([float(x['raw']) for x in values]))
                base['score'] = float(np.median([float(x['score']) for x in values]))
                aggregate.append(base)

        score_history = {key: [score for _, score in vals] for key, vals in history.items()}
        for metric in template.metrics:
            manifest = self.registry.get(metric.detector_key).manifest
            if not manifest.requires_history:
                continue
            if metric.detector_key == 'process.temporal_consistency':
                raw = temporal_consistency(score_history, metric.detector_params)
            else:
                fn = TEMPORAL_FUNCTIONS.get(metric.detector_key)
                raw = float('nan') if fn is None else fn(frames, metric.detector_params)
            if not np.isfinite(raw):
                aggregate.append({'key': metric.key, 'name': metric.name_fa, 'group': metric.group_name, 'raw': None, 'score': None, 'weight': metric.weight, 'status': 'INSUFFICIENT_HISTORY'})
                continue
            score = score_value(float(raw), metric.scoring)
            aggregate.append({'key': metric.key, 'name': metric.name_fa, 'group': metric.group_name, 'raw': float(raw), 'score': float(score), 'weight': metric.weight, 'status': 'OK'})
            history[metric.key] = [(timestamps[-1], float(score))]

        return self._result(aggregate, template, mode='video', history=history, samples=len(frames))

    def dry_run(self, path: str, template: InspectionTemplate) -> dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        if p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
            frame = cv2.imread(str(p))
            if frame is None:
                raise ValueError('Unreadable image')
            return self.analyze_frame(frame, template)
        cap = cv2.VideoCapture(str(p))
        frames: list[np.ndarray] = []
        timestamps: list[float] = []
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        sample_seconds = 1.0
        step = max(1, int(fps * sample_seconds))
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                frames.append(frame)
                timestamps.append(index / fps)
            index += 1
        cap.release()
        return self.analyze_video_frames(frames, timestamps, template)
