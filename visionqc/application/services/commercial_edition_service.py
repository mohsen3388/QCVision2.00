from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import re
import uuid
import zipfile
from typing import Any

from visionqc.core.diagnostics import create_support_bundle, system_report
from visionqc.core.settings import APP_VERSION, app_data_dir
from visionqc.domain.commercial_edition import CommercialReadiness, LicenseState, LicenseStatus, UpdateAssessment
from visionqc.domain.events import DomainEvent


# MVP offline-license integrity key. Production deployments should replace this
# with asymmetric signature verification and keep the private key outside the app.
_LICENSE_INTEGRITY_KEY = b"VisionQC-Commercial-Edition-v2-public-verification-profile"


class CommercialEditionService:
    def __init__(self, repository, audit_repository, event_bus) -> None:
        self.repository = repository
        self.audit = audit_repository
        self.event_bus = event_bus
        self.repository.initialize()

    def machine_id(self) -> str:
        seed = "|".join([platform.node(), platform.system(), platform.machine(), str(uuid.getnode())])
        return hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:24].upper()

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> bytes:
        body = {k: v for k, v in payload.items() if k != "signature"}
        return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    @classmethod
    def sign_license_for_testing(cls, payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(payload)
        result["signature"] = hmac.new(_LICENSE_INTEGRITY_KEY, cls._canonical(result), hashlib.sha256).hexdigest()
        return result

    def import_license(self, source: Path) -> LicenseStatus:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
        status = self.validate_payload(payload)
        if status.state not in {LicenseState.ACTIVE, LicenseState.EXPIRED}:
            raise ValueError(status.message or "License file is invalid")
        self.repository.save_license(payload)
        self.audit.append("commercial.license_imported", actor="Administrator", entity_type="license", entity_id=status.customer, outcome=status.state.value, details={"edition": status.edition, "expires_at": status.expires_at})
        self.event_bus.publish(DomainEvent("commercial.license_changed", {"state": status.state.value, "customer": status.customer}))
        return status

    def validate_payload(self, payload: dict[str, Any] | None) -> LicenseStatus:
        if not payload:
            return LicenseStatus(LicenseState.UNLICENSED, machine_id=self.machine_id(), message="No commercial license is installed.")
        signature = str(payload.get("signature", ""))
        expected = hmac.new(_LICENSE_INTEGRITY_KEY, self._canonical(payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return LicenseStatus(LicenseState.INVALID, machine_id=self.machine_id(), message="License integrity verification failed.")
        licensed_machine = str(payload.get("machine_id", "")).upper()
        current_machine = self.machine_id()
        if licensed_machine and licensed_machine not in {"ANY", current_machine}:
            return LicenseStatus(LicenseState.MACHINE_MISMATCH, customer=str(payload.get("customer", "")), machine_id=current_machine, message="License belongs to another installation.")
        expires_at = payload.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry < datetime.now(timezone.utc):
                    return LicenseStatus(LicenseState.EXPIRED, customer=str(payload.get("customer", "")), edition=str(payload.get("edition", "Commercial")), expires_at=str(expires_at), features=list(payload.get("features", [])), machine_id=current_machine, message="The installed license has expired.")
            except ValueError:
                return LicenseStatus(LicenseState.INVALID, machine_id=current_machine, message="License expiry date is invalid.")
        return LicenseStatus(LicenseState.ACTIVE, customer=str(payload.get("customer", "")), edition=str(payload.get("edition", "Commercial")), expires_at=str(expires_at) if expires_at else None, features=list(payload.get("features", [])), machine_id=current_machine, message="Commercial license is active.")

    def license_status(self) -> LicenseStatus:
        return self.validate_payload(self.repository.load_license())

    def remove_license(self) -> None:
        self.repository.clear_license()
        self.audit.append("commercial.license_removed", actor="Administrator", entity_type="license", outcome="Success")

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...]:
        parts = re.findall(r"\d+", value)
        return tuple(int(x) for x in parts[:4]) or (0,)

    def assess_update_manifest(self, manifest_path: Path, channel: str = "stable") -> UpdateAssessment:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        available = str(payload.get("version", "")) or None
        manifest_channel = str(payload.get("channel", "stable"))
        package = payload.get("package")
        checksum_ok: bool | None = None
        message = "Manifest loaded."
        if manifest_channel != channel:
            message = f"Manifest channel is {manifest_channel}; selected channel is {channel}."
        update_available = bool(available and self._version_tuple(available) > self._version_tuple(APP_VERSION) and manifest_channel == channel)
        if package:
            package_path = (Path(manifest_path).parent / str(package)).resolve()
            if package_path.exists() and payload.get("sha256"):
                digest = hashlib.sha256(package_path.read_bytes()).hexdigest()
                checksum_ok = hmac.compare_digest(digest.lower(), str(payload["sha256"]).lower())
                if not checksum_ok:
                    update_available = False
                    message = "Update package checksum does not match the manifest."
            elif not package_path.exists():
                message = "Update package referenced by the manifest is unavailable."
            package_text = str(package_path)
        else:
            package_text = None
        result = UpdateAssessment(APP_VERSION, available, channel, update_available, package_text, checksum_ok, message, payload)
        self.repository.record_update(APP_VERSION, available, channel, "Available" if update_available else "NoUpdate", {"message": message, "checksum_ok": checksum_ok})
        self.audit.append("commercial.update_checked", actor="VisionQC", entity_type="update_manifest", entity_id=str(manifest_path), outcome="Available" if update_available else "NoUpdate", details={"available_version": available, "channel": channel, "checksum_ok": checksum_ok})
        return result

    def create_diagnostics_bundle(self, destination: Path) -> Path:
        bundle = create_support_bundle(destination)
        crash_dir = app_data_dir() / "crashes"
        if crash_dir.exists():
            with zipfile.ZipFile(bundle, "a", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(crash_dir.glob("*.json"))[-20:]:
                    archive.write(path, f"crashes/{path.name}")
        self.audit.append("commercial.support_bundle_created", actor="Administrator", entity_type="support_bundle", entity_id=bundle.name, outcome="Success")
        return bundle

    def record_crash(self, exc_type: type[BaseException], exc: BaseException, traceback_text: str) -> Path:
        folder = app_data_dir() / "crashes"; folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = folder / f"crash_{stamp}_{os.getpid()}.json"
        payload = {"occurred_at": datetime.now(timezone.utc).isoformat(), "type": exc_type.__name__, "message": str(exc), "traceback": traceback_text, "system": system_report()}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            self.audit.append("commercial.crash_recorded", actor="VisionQC", entity_type="crash_report", entity_id=path.name, outcome="Failure", details={"exception": exc_type.__name__})
        except Exception:
            pass
        return path

    def readiness(self) -> CommercialReadiness:
        license_status = self.license_status()
        crash_dir = app_data_dir() / "crashes"
        crash_count = len(list(crash_dir.glob("*.json"))) if crash_dir.exists() else 0
        no_update = UpdateAssessment(APP_VERSION, None, "stable", False, message="No offline update manifest assessed in this session.")
        checks = [
            {"name": "License integrity", "ok": license_status.state not in {LicenseState.INVALID, LicenseState.MACHINE_MISMATCH}, "details": license_status.message},
            {"name": "Commercial activation", "ok": license_status.usable, "details": license_status.state.value},
            {"name": "Diagnostics directory", "ok": os.access(app_data_dir(), os.W_OK), "details": str(app_data_dir())},
            {"name": "Crash reporting", "ok": True, "details": f"{crash_count} local crash report(s) retained"},
        ]
        return CommercialReadiness.now(license_status=license_status, update_assessment=no_update, support_bundle_ready=True, crash_reports=crash_count, checks=checks)
