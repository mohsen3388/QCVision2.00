from __future__ import annotations

from dataclasses import dataclass, asdict
from math import exp
from statistics import mean, pstdev
from typing import Iterable

from visionqc.models.results import AnalysisResult

# Metrics selected because they are visually meaningful, reasonably stable and available
# for image, video and camera analysis through the shared engine.
DEFAULT_METRICS = (
    ("Image Quality", "brightness"),
    ("Image Quality", "contrast_std"),
    ("Image Quality", "focus_score"),
    ("Image Quality", "exposure_quality"),
    ("Color", "color_uniformity"),
    ("Color", "lab_chroma_mean"),
    ("Color", "hue_concentration"),
    ("Texture", "texture_uniformity"),
    ("Texture", "glcm_homogeneity"),
    ("Texture", "glcm_contrast"),
    ("Texture", "lbp_entropy"),
    ("Surface", "bubble_candidate_density"),
    ("Surface", "oily_region_candidate_percent"),
    ("Surface", "specular_reflection_percent"),
)

# Minimum denominator prevents tiny-valued metrics from producing absurd percentage errors.
SCALES = {
    "brightness": 30.0,
    "contrast_std": 12.0,
    "focus_score": 20.0,
    "exposure_quality": 15.0,
    "color_uniformity": 12.0,
    "lab_chroma_mean": 8.0,
    "hue_concentration": 0.12,
    "texture_uniformity": 12.0,
    "glcm_homogeneity": 0.08,
    "glcm_contrast": 12.0,
    "lbp_entropy": 0.6,
    "bubble_candidate_density": 5.0,
    "oily_region_candidate_percent": 3.0,
    "specular_reflection_percent": 2.0,
}

WEIGHTS = {
    "brightness": 0.7,
    "contrast_std": 0.7,
    "focus_score": 0.5,
    "exposure_quality": 0.6,
    "color_uniformity": 1.3,
    "lab_chroma_mean": 1.1,
    "hue_concentration": 1.0,
    "texture_uniformity": 1.5,
    "glcm_homogeneity": 1.2,
    "glcm_contrast": 1.1,
    "lbp_entropy": 0.8,
    "bubble_candidate_density": 1.3,
    "oily_region_candidate_percent": 1.2,
    "specular_reflection_percent": 0.7,
}

@dataclass(slots=True)
class MetricReference:
    group: str
    metric: str
    mean: float
    std: float
    tolerance: float
    weight: float

@dataclass(slots=True)
class MetricDeviation:
    group: str
    metric: str
    current: float
    reference_mean: float
    reference_std: float
    absolute_difference: float
    normalized_deviation: float
    similarity: float
    status: str
    weight: float

@dataclass(slots=True)
class GoldenComparison:
    profile_id: int
    profile_name: str
    similarity_score: float
    confidence: float
    status: str
    deviations: list[MetricDeviation]
    strongest_deviations: list[MetricDeviation]
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


def flatten_selected(result: AnalysisResult) -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], float] = {}
    for group, metric in DEFAULT_METRICS:
        if group in result.metrics and metric in result.metrics[group]:
            values[(group, metric)] = float(result.metrics[group][metric])
    return values


def build_reference(results: Iterable[AnalysisResult], tolerance_multiplier: float = 2.5) -> list[MetricReference]:
    rows = [flatten_selected(r) for r in results]
    if not rows:
        raise ValueError("At least one approved analysis result is required.")
    references: list[MetricReference] = []
    for group, metric in DEFAULT_METRICS:
        vals = [row[(group, metric)] for row in rows if (group, metric) in row]
        if not vals:
            continue
        mu = mean(vals)
        sigma = pstdev(vals) if len(vals) > 1 else 0.0
        base = SCALES.get(metric, max(abs(mu) * 0.12, 1.0))
        tolerance = max(base, tolerance_multiplier * sigma)
        references.append(MetricReference(group, metric, mu, sigma, tolerance, WEIGHTS.get(metric, 1.0)))
    if len(references) < 6:
        raise ValueError("The approved samples do not contain enough compatible metrics.")
    return references


def compare_to_reference(result: AnalysisResult, profile_id: int, profile_name: str,
                         references: Iterable[MetricReference]) -> GoldenComparison:
    current = flatten_selected(result)
    deviations: list[MetricDeviation] = []
    weighted_similarity = 0.0
    total_weight = 0.0
    for ref in references:
        key = (ref.group, ref.metric)
        if key not in current:
            continue
        value = current[key]
        diff = abs(value - ref.mean)
        # 100 at the reference mean. At tolerance it is about 36.8.
        normalized = diff / max(ref.tolerance, 1e-9)
        similarity = 100.0 * exp(-(normalized ** 2))
        status = "Within Range" if normalized <= 1.0 else ("Attention" if normalized <= 1.6 else "Out of Range")
        item = MetricDeviation(ref.group, ref.metric, value, ref.mean, ref.std, diff,
                               normalized, similarity, status, ref.weight)
        deviations.append(item)
        weighted_similarity += similarity * ref.weight
        total_weight += ref.weight
    if not deviations:
        raise ValueError("No compatible metrics were found for comparison.")
    score = weighted_similarity / total_weight
    coverage = min(1.0, len(deviations) / max(1, len(list(references))))
    confidence = min(99.0, 0.7 * result.analysis_confidence + 30.0 * coverage)
    out_count = sum(d.status == "Out of Range" for d in deviations)
    attention_count = sum(d.status == "Attention" for d in deviations)
    if score >= 82 and out_count == 0:
        status = "Match"
        recommendation = "Visual signature is close to the approved reference. Continue normal QC verification."
    elif score >= 62 and out_count <= 2:
        status = "Review"
        recommendation = "Review the strongest deviations and confirm process conditions before final QC approval."
    else:
        status = "Mismatch"
        recommendation = "Pause or escalate according to the factory procedure; the visual signature differs materially from the approved reference."
    strongest = sorted(deviations, key=lambda d: d.normalized_deviation, reverse=True)[:5]
    return GoldenComparison(profile_id, profile_name, round(score, 2), round(confidence, 2), status,
                            deviations, strongest, recommendation)
