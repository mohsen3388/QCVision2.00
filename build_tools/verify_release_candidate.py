from __future__ import annotations

import json
from pathlib import Path

from visionqc.bootstrap import bootstrap_application


def main() -> int:
    context = bootstrap_application()
    service = context.container.resolve("release_readiness_service")
    report = service.assess()
    output = Path.cwd() / "VisionQC_Release_Readiness.json"
    service.export_report(output, report)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    print(f"Report: {output}")
    return 0 if report.level.value != "Blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
