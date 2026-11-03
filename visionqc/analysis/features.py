from __future__ import annotations

import cv2
import numpy as np


def _round(value: float) -> float:
    if not np.isfinite(value):
        return 0.0
    return round(float(value), 3)


def _safe_skew(values: np.ndarray) -> float:
    x = values.astype(np.float64).ravel()
    std = x.std()
    if std < 1e-9:
        return 0.0
    return float(np.mean(((x - x.mean()) / std) ** 3))


def _safe_kurtosis(values: np.ndarray) -> float:
    x = values.astype(np.float64).ravel()
    std = x.std()
    if std < 1e-9:
        return 0.0
    return float(np.mean(((x - x.mean()) / std) ** 4) - 3.0)


def _entropy_from_hist(hist: np.ndarray) -> float:
    p = hist.astype(np.float64).ravel()
    p = p / max(float(p.sum()), 1.0)
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p)))


def image_quality_metrics(image: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray_f = gray.astype(np.float32)
    mean = float(np.mean(gray))
    std = float(np.std(gray))
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = float(lap.var())
    p1, p5, p25, p50, p75, p95, p99 = np.percentile(gray, [1, 5, 25, 50, 75, 95, 99])
    clipped_dark = float(np.mean(gray <= 5) * 100)
    clipped_light = float(np.mean(gray >= 250) * 100)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    entropy = _entropy_from_hist(hist)
    gaussian = cv2.GaussianBlur(gray, (5, 5), 0)
    residual = gray_f - gaussian.astype(np.float32)
    noise_proxy = float(np.mean(np.abs(residual)))
    noise_std = float(np.std(residual))
    snr_proxy = float(20 * np.log10(max(mean, 1.0) / max(noise_std, 1e-3)))
    exposure_quality = max(0.0, 100.0 - clipped_dark - clipped_light)
    focus_score = min(100.0, (lap_var / 400.0) * 100.0)
    dynamic_range = float(p99 - p1)
    rms_contrast = float(np.sqrt(np.mean((gray_f - mean) ** 2)))
    return {
        "brightness": _round(mean), "contrast_std": _round(std),
        "rms_contrast": _round(rms_contrast), "sharpness_laplacian": _round(lap_var),
        "focus_score": _round(focus_score), "dynamic_range_p1_p99": _round(dynamic_range),
        "dark_clipping_percent": _round(clipped_dark), "light_clipping_percent": _round(clipped_light),
        "exposure_quality": _round(exposure_quality), "entropy": _round(entropy),
        "noise_mean_absolute": _round(noise_proxy), "noise_std": _round(noise_std),
        "snr_proxy_db": _round(snr_proxy), "gray_skewness": _round(_safe_skew(gray)),
        "gray_excess_kurtosis": _round(_safe_kurtosis(gray)),
        "gray_p01": _round(p1), "gray_p05": _round(p5), "gray_p25": _round(p25),
        "gray_median": _round(p50), "gray_p75": _round(p75), "gray_p95": _round(p95),
        "gray_p99": _round(p99),
    }


def color_metrics(image: np.ndarray) -> dict[str, float]:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    data: dict[str, float] = {}
    for prefix, arr, names in (
        ("rgb", rgb, ("r", "g", "b")), ("hsv", hsv, ("h", "s", "v")),
        ("lab", lab, ("l", "a", "b")), ("ycrcb", ycrcb, ("y", "cr", "cb")),
    ):
        for index, name in enumerate(names):
            channel = arr[:, :, index]
            data[f"{prefix}_{name}_mean"] = _round(np.mean(channel))
            data[f"{prefix}_{name}_std"] = _round(np.std(channel))
            data[f"{prefix}_{name}_p05"] = _round(np.percentile(channel, 5))
            data[f"{prefix}_{name}_p95"] = _round(np.percentile(channel, 95))
    lab_std = np.mean([data["lab_l_std"], data["lab_a_std"], data["lab_b_std"]])
    data["color_uniformity"] = _round(max(0.0, 100.0 - lab_std))
    saturation = hsv[:, :, 1]
    hue = hsv[:, :, 0].astype(np.float32)
    data["low_saturation_percent"] = _round(np.mean(saturation < 25) * 100)
    data["high_saturation_percent"] = _round(np.mean(saturation > 180) * 100)
    # Hasler-Süsstrunk colorfulness proxy.
    r, g, b = [rgb[:, :, i].astype(np.float32) for i in range(3)]
    rg = r - g
    yb = 0.5 * (r + g) - b
    colorfulness = np.sqrt(np.std(rg) ** 2 + np.std(yb) ** 2) + 0.3 * np.sqrt(np.mean(rg) ** 2 + np.mean(yb) ** 2)
    data["colorfulness_proxy"] = _round(colorfulness)
    a_centered = lab[:, :, 1].astype(np.float32) - 128
    b_centered = lab[:, :, 2].astype(np.float32) - 128
    chroma = np.sqrt(a_centered ** 2 + b_centered ** 2)
    data["lab_chroma_mean"] = _round(np.mean(chroma))
    data["lab_chroma_std"] = _round(np.std(chroma))
    # Circular concentration of hue (1 = concentrated, 0 = dispersed).
    angles = hue * (2 * np.pi / 180.0)
    weights = saturation.astype(np.float32) / 255.0
    denom = max(float(weights.sum()), 1e-6)
    resultant = np.sqrt((np.sum(np.cos(angles) * weights) / denom) ** 2 + (np.sum(np.sin(angles) * weights) / denom) ** 2)
    data["hue_concentration"] = _round(resultant * 100)
    return data


def _glcm_metrics(gray: np.ndarray, levels: int = 16) -> dict[str, float]:
    small = cv2.resize(gray, (192, 192), interpolation=cv2.INTER_AREA)
    q = np.clip((small.astype(np.int32) * levels) // 256, 0, levels - 1)
    glcm = np.zeros((levels, levels), dtype=np.float64)
    for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
        if dx >= 0:
            a = q[max(0, -dy): q.shape[0]-max(0, dy), 0:q.shape[1]-dx]
            b = q[max(0, dy): q.shape[0]-max(0, -dy), dx:q.shape[1]]
        else:
            a = q[max(0, -dy): q.shape[0]-max(0, dy), -dx:q.shape[1]]
            b = q[max(0, dy): q.shape[0]-max(0, -dy), 0:q.shape[1]+dx]
        np.add.at(glcm, (a.ravel(), b.ravel()), 1)
    glcm += glcm.T
    glcm /= max(glcm.sum(), 1.0)
    i, j = np.indices(glcm.shape)
    contrast = np.sum(glcm * (i - j) ** 2)
    dissimilarity = np.sum(glcm * np.abs(i - j))
    homogeneity = np.sum(glcm / (1.0 + (i - j) ** 2))
    asm = np.sum(glcm ** 2)
    energy = np.sqrt(asm)
    mi, mj = np.sum(i * glcm), np.sum(j * glcm)
    si = np.sqrt(np.sum(((i - mi) ** 2) * glcm))
    sj = np.sqrt(np.sum(((j - mj) ** 2) * glcm))
    correlation = np.sum((i - mi) * (j - mj) * glcm) / max(si * sj, 1e-9)
    return {"glcm_contrast": _round(contrast), "glcm_dissimilarity": _round(dissimilarity),
            "glcm_homogeneity": _round(homogeneity), "glcm_asm": _round(asm),
            "glcm_energy": _round(energy), "glcm_correlation": _round(correlation)}


def _lbp_metrics(gray: np.ndarray) -> dict[str, float]:
    small = cv2.resize(gray, (256, 256), interpolation=cv2.INTER_AREA)
    c = small[1:-1, 1:-1]
    neighbors = [small[:-2, :-2], small[:-2, 1:-1], small[:-2, 2:], small[1:-1, 2:],
                 small[2:, 2:], small[2:, 1:-1], small[2:, :-2], small[1:-1, :-2]]
    lbp = np.zeros_like(c, dtype=np.uint8)
    for bit, n in enumerate(neighbors):
        lbp |= ((n >= c).astype(np.uint8) << bit)
    hist = np.bincount(lbp.ravel(), minlength=256).astype(np.float64)
    p = hist / max(hist.sum(), 1.0)
    return {"lbp_entropy": _round(_entropy_from_hist(hist)),
            "lbp_uniformity": _round(np.sum(p ** 2) * 100),
            "lbp_dominant_pattern_percent": _round(np.max(p) * 100)}


def texture_metrics(image: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (256, 256), interpolation=cv2.INTER_AREA)
    gx = cv2.Sobel(small, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(small, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    edges = cv2.Canny(small, 50, 150)
    local_mean = cv2.blur(small.astype(np.float32), (9, 9))
    local_sq_mean = cv2.blur((small.astype(np.float32) ** 2), (9, 9))
    local_variance = np.maximum(0.0, local_sq_mean - local_mean ** 2)
    local_std = np.sqrt(local_variance)
    roughness = float(np.mean(magnitude))
    edge_density = float(np.mean(edges > 0) * 100)
    local_variation = float(np.mean(local_std))
    uniformity = max(0.0, 100.0 - min(100.0, local_variation * 3.0))
    data = {
        "edge_density": _round(edge_density), "gradient_mean": _round(roughness),
        "gradient_p90": _round(np.percentile(magnitude, 90)), "gradient_p99": _round(np.percentile(magnitude, 99)),
        "local_variation": _round(local_variation), "local_variation_std": _round(np.std(local_std)),
        "texture_uniformity": _round(uniformity),
    }
    data.update(_glcm_metrics(gray))
    data.update(_lbp_metrics(gray))
    return data


def surface_metrics(image: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blurred = cv2.GaussianBlur(gray, (7, 7), 1.5)
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.3, minDist=12,
                               param1=90, param2=24, minRadius=3,
                               maxRadius=max(8, min(image.shape[:2]) // 12))
    circle_count = 0 if circles is None else int(circles.shape[1])
    area = max(image.shape[0] * image.shape[1], 1)
    bubble_candidate_density = min(100.0, circle_count * 2500.0 / area * 100.0)
    saturation, value = hsv[:, :, 1], hsv[:, :, 2]
    oily_mask = ((saturation < 55) & (value > 165)).astype(np.uint8)
    specular_mask = (value > 245).astype(np.uint8)
    contours, _ = cv2.findContours(oily_mask * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    areas = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) >= 9]
    circularities = []
    for c in contours:
        a = cv2.contourArea(c)
        p = cv2.arcLength(c, True)
        if a >= 9 and p > 0:
            circularities.append(4 * np.pi * a / (p * p))
    return {
        "bubble_candidate_count": float(circle_count),
        "bubble_candidate_density": _round(bubble_candidate_density),
        "oily_region_candidate_percent": _round(np.mean(oily_mask) * 100),
        "specular_reflection_percent": _round(np.mean(specular_mask) * 100),
        "bright_low_saturation_region_count": float(len(areas)),
        "largest_bright_region_percent": _round((max(areas) if areas else 0.0) / area * 100),
        "mean_candidate_circularity": _round(np.mean(circularities) if circularities else 0.0),
        "surface_dark_region_percent": _round(np.mean(value < 55) * 100),
    }


def distributions(image: np.ndarray) -> dict[str, list[float]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    result: dict[str, list[float]] = {}
    for name, channel, bins, limit in [
        ("Gray", gray, 64, (0, 256)), ("Red", rgb[:, :, 0], 64, (0, 256)),
        ("Green", rgb[:, :, 1], 64, (0, 256)), ("Blue", rgb[:, :, 2], 64, (0, 256)),
        ("Hue", hsv[:, :, 0], 45, (0, 180)), ("Saturation", hsv[:, :, 1], 64, (0, 256)),
    ]:
        hist, _ = np.histogram(channel, bins=bins, range=limit)
        hist = hist.astype(np.float64)
        hist /= max(hist.max(), 1.0)
        result[name] = [round(float(v), 5) for v in hist]
    return result
