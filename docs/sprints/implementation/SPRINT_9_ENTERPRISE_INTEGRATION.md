# VisionQC 2.0 — Sprint 9: Enterprise Integration

Sprint 9 turns VisionQC from a standalone workstation application into an offline-first enterprise integration platform.

## Delivered

- Connector registry and common connector contract
- Secured local REST API (`/health`, `/connectors`, `/factory-memory`)
- API key issue, authentication, disable and usage audit
- Role-based access control for Operator, QC, Supervisor, Maintenance, Administrator and Auditor
- MQTT readiness adapter with honest dependency and endpoint health reporting
- OPC-UA readiness adapter with optional driver detection
- Outbound webhook adapter
- Writable secure file-exchange connector
- Integration Hub UI
- Audit Trail integration
- Schema migration version 3

## Safety and operating boundaries

VisionQC does not write to PLCs or alter recipe/machine parameters in this sprint. MQTT and OPC-UA are read/integration readiness adapters until commissioned against a factory test environment. The REST API binds to localhost by default.

## REST API

- `GET /health` — anonymous operational health
- `GET /connectors` — API key required
- `GET /factory-memory` — API key required

Use header: `X-API-Key: <secret>`.
