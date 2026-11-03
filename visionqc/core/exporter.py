from __future__ import annotations

import json
from pathlib import Path

from visionqc.models.results import AnalysisResult


def export_json(result: AnalysisResult, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, ensure_ascii=False, indent=2)
    return path
