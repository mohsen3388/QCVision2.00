# Sprint 10 Acceptance — VisionQC 1.0.0

## Goal
Deliver secure, offline-first multi-site data exchange without requiring a continuously available server.

## Accepted capabilities
- Secure Synchronization page is available from the sidebar and ☰ ALL FEATURES.
- Outbound `.vqcsync` packages use ZIP containers with canonical JSON payloads, SHA-256 integrity hashes and HMAC-SHA256 signatures.
- A 256-bit shared key can be generated locally; only its fingerprint is displayed in package metadata.
- Pending changes can be queued and marked Exported after package creation.
- Incoming packages are validated before any database write.
- Idempotent receipts prevent the same remote queue item from being applied twice.
- Optional safe snapshot import uses allow-listed tables and `INSERT OR IGNORE` semantics.
- Package history records inbound/outbound direction, source site, item count, status, path and timestamp.
- Existing full offline installer and embedded Python/runtime requirements remain intact.

## Security boundary
This sprint provides signed store-and-forward exchange, not automatic Internet transport or a hosted central dashboard. Shared keys must be exchanged through a trusted channel.
