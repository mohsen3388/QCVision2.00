from pathlib import Path
import cv2
import numpy as np
from visionqc.analysis.engine import analyze_image


def test_analysis_engine_returns_deep_result(tmp_path: Path):
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:] = (105, 125, 165)
    cv2.circle(image, (240, 220), 45, (150, 170, 200), 4)
    cv2.line(image, (40, 400), (590, 80), (80, 100, 130), 8)
    path = tmp_path / "sample.png"
    assert cv2.imwrite(str(path), image)
    result = analyze_image(str(path), (20, 20, 580, 420))
    assert result.engine_version == "0.4.1"
    assert len(result.metrics["Image Quality"]) >= 20
    assert len(result.metrics["Color"]) >= 40
    assert "glcm_contrast" in result.metrics["Texture"]
    assert "lbp_entropy" in result.metrics["Texture"]
    assert len(result.distributions) >= 6
    assert len(result.visualization_png) >= 4
    assert 0 <= result.visual_health_score <= 100
    assert 0 <= result.analysis_confidence <= 100
    assert "visualization_png" not in result.to_dict()
