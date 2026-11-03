import cv2
import numpy as np

from visionqc.ai.prompt_builder import build_inspection_prompt
from visionqc.analysis.live_stream import build_temporal_contact_sheet


def _jpeg(value: int) -> bytes:
    image = np.full((120, 160, 3), value, dtype=np.uint8)
    ok, encoded = cv2.imencode('.jpg', image)
    assert ok
    return encoded.tobytes()


def test_temporal_prompt_instructs_gemini_to_follow_process_trend():
    prompt = build_inspection_prompt({'temporal_contact_sheet': True}, {})
    assert 'chronological contact sheet' in prompt
    assert 'stable, improving, deteriorating, or rapidly deteriorating' in prompt
    assert 'rolling_metrics' in prompt


def test_build_temporal_contact_sheet_uses_multiple_chronological_frames():
    payload = build_temporal_contact_sheet([_jpeg(40), _jpeg(100), _jpeg(180)], _jpeg(220))
    decoded = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape[1] == 1440
    assert decoded.shape[0] >= 640
