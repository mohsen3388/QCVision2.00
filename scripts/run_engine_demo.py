from __future__ import annotations

import json
import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from visionqc.analysis.engine import analyze_image


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python run_engine_demo.py IMAGE_PATH")
    result = analyze_image(sys.argv[1], progress=lambda p, m: print(f"{p:3d}% {m}"))
    print(json.dumps(result.to_dict(), indent=2))
