from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from visionqc.application.services.commercial_edition_service import CommercialEditionService
from visionqc.domain.commercial_edition import LicenseState
from visionqc.infrastructure.persistence.sqlite_audit import SqliteAuditTrailRepository
from visionqc.infrastructure.persistence.sqlite_commercial import SqliteCommercialRepository
from visionqc.platform.event_bus import InProcessEventBus


def _service(monkeypatch):
    import visionqc.core.database as db
    temp = tempfile.TemporaryDirectory()
    db_path = Path(temp.name) / "commercial.sqlite3"
    monkeypatch.setattr(db, "database_path", lambda: db_path)
    return temp, CommercialEditionService(SqliteCommercialRepository(), SqliteAuditTrailRepository(), InProcessEventBus())


def test_valid_offline_license_is_imported(monkeypatch):
    temp, service = _service(monkeypatch)
    try:
        payload = service.sign_license_for_testing({
            "customer": "Demo Meat Factory",
            "edition": "Commercial",
            "machine_id": service.machine_id(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "features": ["factory_memory", "automation"],
        })
        path = Path(temp.name) / "license.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert service.import_license(path).state is LicenseState.ACTIVE
        assert service.license_status().customer == "Demo Meat Factory"
    finally:
        temp.cleanup()


def test_tampered_license_is_rejected(monkeypatch):
    temp, service = _service(monkeypatch)
    try:
        payload = service.sign_license_for_testing({"customer": "A", "machine_id": "ANY"})
        payload["customer"] = "Tampered"
        path = Path(temp.name) / "license.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            service.import_license(path)
        except ValueError:
            pass
        else:
            raise AssertionError("tampered license accepted")
    finally:
        temp.cleanup()


def test_machine_mismatch_is_detected(monkeypatch):
    temp, service = _service(monkeypatch)
    try:
        payload = service.sign_license_for_testing({"customer": "A", "machine_id": "OTHER-MACHINE"})
        assert service.validate_payload(payload).state is LicenseState.MACHINE_MISMATCH
    finally:
        temp.cleanup()


def test_offline_update_manifest_verifies_checksum(monkeypatch):
    temp, service = _service(monkeypatch)
    try:
        package = Path(temp.name) / "VisionQC_4.8.0.zip"
        package.write_bytes(b"commercial update package")
        manifest = Path(temp.name) / "update.json"
        manifest.write_text(json.dumps({
            "version": "4.8.0",
            "channel": "stable",
            "package": package.name,
            "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        result = service.assess_update_manifest(manifest)
        assert result.update_available is True
        assert result.checksum_ok is True
    finally:
        temp.cleanup()
