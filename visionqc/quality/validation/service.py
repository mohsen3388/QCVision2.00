from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

from visionqc.configuration.models import InspectionTemplate
from visionqc.configuration.runtime import ConfigurationRuntime
from .models import (
    QUALITY_CLASSES, CalibrationSample, MetricCalibrationResult,
    SampleEvaluation, ValidationSummary, class_from_score,
)
from .repository import CalibrationRepository


class ValidationService:
    """Runs labelled calibration data through the real VisionQC runtime.

    The service never changes thresholds or publishes templates automatically.
    It produces evidence and a guarded recommendation for a QC specialist.
    """

    def __init__(self, runtime: ConfigurationRuntime | None = None, repository: CalibrationRepository | None = None) -> None:
        self.runtime = runtime or ConfigurationRuntime()
        self.repository = repository or CalibrationRepository()

    @staticmethod
    def _safe_div(a: float, b: float) -> float:
        return 0.0 if not b else float(a) / float(b)

    def _evaluate_samples(self, samples: Iterable[CalibrationSample], template: InspectionTemplate) -> list[SampleEvaluation]:
        output: list[SampleEvaluation] = []
        for sample in samples:
            if sample.id is None:
                raise ValueError("نمونه باید پیش از اعتبارسنجی ذخیره شود.")
            if not Path(sample.source_path).exists():
                raise FileNotFoundError(sample.source_path)
            result = self.runtime.dry_run(sample.source_path, template)
            score = float(result["final_score"])
            predicted = class_from_score(score)
            output.append(SampleEvaluation(
                sample_id=int(sample.id), source_path=sample.source_path,
                expert_label=sample.expert_label, predicted_label=predicted,
                final_score=round(score, 2), product_health=float(result.get("product_health", 0)),
                process_health=float(result.get("process_health", 0)),
                correct=predicted == sample.expert_label, result=result,
            ))
        return output

    @staticmethod
    def _metric_calibration(evaluations: list[SampleEvaluation], template: InspectionTemplate) -> list[MetricCalibrationResult]:
        results: list[MetricCalibrationResult] = []
        metric_names = {m.key: m.name_fa for m in template.metrics}
        for metric_key, metric_name in metric_names.items():
            by_class: dict[str, list[float]] = {label: [] for label in QUALITY_CLASSES}
            for evaluation in evaluations:
                item = next((m for m in evaluation.result.get("metrics", []) if m.get("key") == metric_key and m.get("score") is not None), None)
                if item:
                    by_class[evaluation.expert_label].append(float(item["score"]))
            medians = {label: (round(float(np.median(vals)), 2) if vals else None) for label, vals in by_class.items()}
            available = [(i, medians[label]) for i, label in enumerate(QUALITY_CLASSES) if medians[label] is not None]
            consistency = 0.0
            if len(available) >= 2:
                correct_pairs = sum(1 for (i, a), (j, b) in zip(available, available[1:]) if i < j and float(a) >= float(b))
                consistency = 100.0 * correct_pairs / max(1, len(available) - 1)
            healthy = medians["سالم"]
            medium = medians["هشدار متوسط"]
            high = medians["هشدار سطح بالا"]
            warning_threshold = round((healthy + medium) / 2, 2) if healthy is not None and medium is not None else None
            high_threshold = round((medium + high) / 2, 2) if medium is not None and high is not None else None
            values = [float(v) for v in medians.values() if v is not None]
            separation = round(max(values) - min(values), 2) if len(values) >= 2 else 0.0
            quality = "خوب" if consistency >= 75 and separation >= 20 else "متوسط" if consistency >= 50 and separation >= 10 else "ضعیف"
            results.append(MetricCalibrationResult(metric_key, metric_name, medians, warning_threshold, high_threshold, round(consistency, 2), separation, quality))
        return results

    def validate(self, template: InspectionTemplate, *, minimum_samples: int = 10, minimum_per_class: int = 1,
                 minimum_accuracy: float = 0.70, maximum_false_negative_rate: float = 0.20) -> ValidationSummary:
        samples = self.repository.list_samples(template.key)
        if not samples:
            raise ValueError("برای این Template هیچ نمونه کالیبراسیون ثبت نشده است.")
        evaluations = self._evaluate_samples(samples, template)
        labels = list(QUALITY_CLASSES)
        matrix = {actual: {pred: 0 for pred in labels} for actual in labels}
        for row in evaluations:
            matrix[row.expert_label][row.predicted_label] += 1
        class_counts = Counter(x.expert_label for x in evaluations)
        accuracy = self._safe_div(sum(x.correct for x in evaluations), len(evaluations))

        # Binary safety view: healthy/minor are acceptable; medium/high/critical are defective.
        def defective(label: str) -> bool:
            return label in {"هشدار متوسط", "هشدار سطح بالا", "بحرانی"}
        tp = sum(defective(x.expert_label) and defective(x.predicted_label) for x in evaluations)
        tn = sum(not defective(x.expert_label) and not defective(x.predicted_label) for x in evaluations)
        fp = sum(not defective(x.expert_label) and defective(x.predicted_label) for x in evaluations)
        fn = sum(defective(x.expert_label) and not defective(x.predicted_label) for x in evaluations)
        precision = self._safe_div(tp, tp + fp); recall = self._safe_div(tp, tp + fn)
        specificity = self._safe_div(tn, tn + fp); f1 = self._safe_div(2 * precision * recall, precision + recall)
        fpr = self._safe_div(fp, fp + tn); fnr = self._safe_div(fn, fn + tp)
        per_class_recall = {label: round(self._safe_div(matrix[label][label], sum(matrix[label].values())), 4) for label in labels}

        reasons: list[str] = []
        if len(evaluations) < minimum_samples:
            reasons.append(f"حداقل {minimum_samples} نمونه لازم است؛ اکنون {len(evaluations)} نمونه وجود دارد.")
        missing = [label for label in labels if class_counts.get(label, 0) < minimum_per_class]
        if missing:
            reasons.append("کلاس‌های دارای نمونه ناکافی: " + "، ".join(missing))
        if accuracy < minimum_accuracy:
            reasons.append(f"توافق کلی {accuracy:.1%} کمتر از حد {minimum_accuracy:.0%} است.")
        if fnr > maximum_false_negative_rate:
            reasons.append(f"نرخ از دست‌رفتن عیب {fnr:.1%} بیشتر از حد {maximum_false_negative_rate:.0%} است.")
        metric_results = self._metric_calibration(evaluations, template)
        strong_metrics = sum(x.quality in {"خوب", "متوسط"} for x in metric_results)
        if metric_results and strong_metrics < max(1, len(metric_results) // 2):
            reasons.append("کمتر از نیمی از شاخص‌ها جداسازی قابل قبول بین کلاس‌ها دارند.")
        summary = ValidationSummary(
            run_id=None, template_key=template.key, template_version=template.version,
            sample_count=len(evaluations), class_counts={label: class_counts.get(label, 0) for label in labels},
            accuracy=round(accuracy, 4), precision=round(precision, 4), recall=round(recall, 4),
            specificity=round(specificity, 4), f1=round(f1, 4), false_positive_rate=round(fpr, 4),
            false_negative_rate=round(fnr, 4), expert_agreement=round(accuracy, 4),
            confusion_matrix=matrix, per_class_recall=per_class_recall, metric_results=metric_results,
            sample_results=evaluations, production_ready=not reasons, gate_reasons=reasons,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        summary.run_id = self.repository.save_validation(summary)
        return summary
