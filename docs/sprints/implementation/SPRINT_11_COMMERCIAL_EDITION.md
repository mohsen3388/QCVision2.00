# VisionQC 2.0 — Sprint 11 Commercial Edition

Sprint 11 closes the VisionQC 2.0 roadmap by adding product operations required for a commercial, offline-first factory deployment.

## Delivered

- Offline machine-bound license import and validation
- Tamper detection for license payloads
- Expiry and machine-mismatch states
- Commercial Edition UI
- Offline update-manifest assessment
- SHA-256 package verification
- Structured local crash reports
- Extended support bundles
- Commercial audit events
- Schema migration 5
- Product version 2.0.0

## Security boundary

The included license mechanism is a commercial MVP integrity control. Before broad distribution, replace the embedded verification profile with asymmetric signature verification. Private signing keys must never be shipped with the application.

Update Center only assesses local manifests and packages. It does not silently install software, download executable code, bypass Windows security controls, or restart factory systems.
