# Release Notes — VisionQC 2.0 Sprint 9

## Enterprise Integration Hub

VisionQC now exposes an offline-first connector framework and secured local REST interface. Factory IT teams can assess MQTT, OPC-UA, webhook and file-exchange readiness without receiving false positive connection claims.

## Security

API secrets are displayed only at issuance. Only SHA-256 hashes are persisted. Keys can be disabled, and permissions are enforced through role-based access control.

## Deployment

The REST service is stopped by default and binds to `127.0.0.1`. Network exposure must be explicitly designed and protected by factory IT before use outside the local workstation.
