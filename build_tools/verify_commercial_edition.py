from __future__ import annotations

import json
from visionqc.bootstrap import bootstrap_application


def main() -> int:
    context = bootstrap_application()
    service = context.container.resolve("commercial_edition_service")
    report = service.readiness()
    print(json.dumps({
        "version": report.update_assessment.current_version,
        "license_state": report.license_status.state.value,
        "machine_id": report.license_status.machine_id,
        "crash_reports": report.crash_reports,
        "checks": report.checks,
    }, indent=2))
    return 0 if all(item["ok"] for item in report.checks if item["name"] != "Commercial activation") else 1


if __name__ == "__main__":
    raise SystemExit(main())
