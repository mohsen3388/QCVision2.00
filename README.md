# QCVision (VisionQC)

### AI-powered food production monitoring and quality intelligence

**End-to-end burger meat production monitoring · Real-time visual inspection · Voice-guided mixer operators · Role-based quality alerts · Human-supervised decisions**

QCVision (named **VisionQC** in the application source) is an **offline-first Windows desktop platform** designed for food manufacturing, with a particular focus on **burger meat preparation and mixing**. Its operating vision is to connect quality evidence and production context across the workflow—from incoming meat reception and preparation through grinding, ingredient dosing, mixing, process inspection and product discharge—so production teams can identify issues early, communicate clearly and maintain a traceable record.

Unlike a standalone defect detector, QCVision brings together **computer vision, live cameras, process-quality assessment, operator communication, factory knowledge and production analytics**. It is designed to assist people at different responsibility levels: the **mixer/kettle operator**, **quality-control specialist** and **production/project manager**.

> **Status and scope:** Active engineering prototype / pre-production software. The repository includes application code and automated tests for many of the capabilities described below. The full reception-to-discharge operating chain is the intended food-production workflow; actual coverage depends on configured inspection points, cameras, integrations and local factory procedures. Neither end-to-end commissioning nor food-safety certification is claimed.

## What makes QCVision different?

- **Food-production-first workflow:** Organize quality checks around burger meat production and mixing, not merely isolated images.
- **Product and process health:** Separate the visible quality of meat mixture (e.g., color, texture, mixing coverage and visible aeration) from process continuity and behavior; a healthy-looking process does not override poor product-quality evidence.
- **Voice assistance on the production floor:** Send concise, actionable spoken alerts through the Windows audio output/headset; support operator wake-word interaction using **“Vision” / “ویژن”**, with Persian speech recognition when available.
- **Role-aware response:** Present immediate operational warnings to operators, evidence and investigation context to QC staff, and trends, exceptions and KPIs to management. Site-specific routing and escalation rules require configuration and validation.
- **Explainable, auditable decisions:** Link measurements, detector rules, scores, snapshots, events and human acknowledgements.
- **Offline-first architecture:** Run core local vision and quality workflows without requiring cloud AI. Optional Gemini review needs credentials, connectivity and appropriate data-sharing approval.

## Burger meat production: intended end-to-end monitoring workflow

| Stage | Quality and operational monitoring focus |
| --- | --- |
| **1. Raw meat reception** | Lot identity, receipt context, inspection records and available incoming-quality evidence |
| **2. Preparation and grinding** | Production stage/line context, visible condition and configured process checks |
| **3. Ingredients and formulation** | Batch and recipe context, ingredient-related checks where records or sensors are connected |
| **4. Mixing / mixer-kettle operation** | Live camera observation, mixture color and texture indicators, coverage, visible aeration, process events and operator alerts |
| **5. In-process QC** | Snapshot/video evidence, Golden Batch comparison, detector scores, accept/reject review and QC escalation |
| **6. Discharge and handoff** | Final visual/operational evidence, batch disposition, traceable quality records and reporting |

*This table describes the intended production-wide deployment pattern. It is not a claim that every station is already connected to physical factory equipment or that every property can be measured from images. Temperature, composition, pathogen status and other non-visual properties require appropriate calibrated instruments, sampling or laboratory procedures.*

## Role-based communication and alerts

| Role | Main interaction | Example alert or information |
| --- | --- | --- |
| **Mixer / line operator** | Live status, short spoken headset alerts, voice queries and acknowledgements | “Mixing appearance is outside the configured reference. Check the batch and contact QC.” |
| **QC specialist / quality engineer** | Evidence review, inspection scores, batch history, root-cause hypotheses and controlled disposition | “A sustained visual deviation needs review against the approved Golden Batch.” |
| **Production / project manager** | Supervisory dashboards, production trends, OEE, recurring exceptions and escalation summaries | “Repeated mixing deviations have affected multiple runs; review the trend and assigned actions.” |

*Examples illustrate intended role-specific messaging, not exact guaranteed application wording or verified push delivery to every role. Headset output is based on the configured Windows audio device; factory communications and permissions must be tested on site.*

## At a glance

| Area | Current codebase capabilities |
| --- | --- |
| **Visual analysis** | OpenCV/NumPy measurements, ROI selection, rule-based detectors, explainable evidence and visualizations |
| **Cameras and video** | USB/live camera analysis, video temporal trends, RTSP/HTTP source support and multi-camera configuration |
| **Food process inspection** | Configurable detector/score/trigger/action workflows, product-vs-process-health assessment, specialized mixing inspection profiles and Golden Batch reference comparison |
| **Operator assistance** | Spoken quality alerts, serialized headset/audio output, Persian/English recognition fallback and “Vision/ویژن” wake-word interaction |
| **QC operations** | Inspection projects, batch workspace, traceable events, human approvals, reports and inspection history |
| **Quality intelligence** | Factory Memory, root-cause support, knowledge graph, predictive quality workflows and AI Factory Engineer briefings |
| **Analytics** | SPC and process capability indicators, shifts, runs, downtime, OEE and management dashboards |
| **Enterprise integration** | Local API, API-key controls, audit/RBAC mechanisms, connector diagnostics, offline-sync and approval-gated workflows |
| **Deployment** | Windows development/build scripts, diagnostics, backup/restore and offline-oriented distribution infrastructure |

See [detailed feature status](docs/FEATURES.md), [architecture](docs/ARCHITECTURE.md) and [validation notes](docs/VALIDATION.md).

## How QCVision works

```text
Raw-meat receipt → Preparation / grinding → Mixing → In-process QC → Discharge
       |                    |                  |             |               |
       +--------------------+------------------+-------------+---------------+
                                            |
                         Cameras / video / batch context / connected data
                                            |
                            Local visual measurements + detectors
                                            |
                           Product health + process health + events
                                            |
                            Evidence + rules + quality intelligence
                                            |
                 +--------------------------+--------------------------+
                 |                          |                          |
          Operator / headset            QC specialist         Production manager
          Real-time guidance          Review and approval       Trends and escalation
                 +--------------------------+--------------------------+
                                            |
                              Audit trail + reports + memory
                                            |
                            Optional Gemini-supported review
```

## Core capabilities

### 1. Live food-production and mixing inspection
Analyze images, temporal video and compatible USB/IP camera feeds. Configure inspection regions, detector profiles and Golden Batch references. For mixing scenarios, use visible indicators such as color, surface texture, coverage and aeration patterns as **quality-support evidence**, not direct laboratory measurements.

### 2. Voice-guided operators
Deliver brief spoken warnings through a configured headset/audio output, while healthy/pass outcomes can remain silent. The operator interaction design includes the wake word **Vision / ویژن** and Persian-language questions when Windows speech components support them. Speech recognition and background-noise robustness depend on the deployed device and environment.

### 3. Three-level quality communication
Support different information needs for production operators, QC specialists and managers. Operational messages should be concise and actionable, QC views should provide supporting evidence, and managers should see aggregated patterns and unresolved issues. Approval and escalation remain governed by authorized factory personnel.

### 4. Human-supervised quality intelligence
Combine local detectors and rules with factory history, root-cause hypotheses, knowledge-based briefings and recorded decisions. Optional Google Gemini review may enrich interpretations when configured, but local operation remains the core design.

### 5. Production performance and traceability
Use inspection history, production runs, shifts, downtime, SPC, Cp/Cpk and OEE dashboards to study process stability and recurring deviations. Batch-level traceability depends on reliable data entry, identifiers, integration and site procedures.

## Screenshots and demonstration

Add **real screenshots from a running QCVision build** to `screenshots/` and link them here. Recommended images: production overview, mixing-camera monitoring, operator voice/alert screen, product/process health assessment, QC review workspace and management dashboard. This package does not fabricate screenshots.

## Getting started (development)

**Target:** Windows 10/11 x64; Python **3.11** for the provided development scripts.

```bat
SETUP_DEV_ENV.bat
RUN_VISIONQC.bat
```

Alternatively, configure a Python 3.11 virtual environment, install `requirements-dev.txt` and run:

```bat
python main.py
```

Run automated tests:

```bat
RUN_TESTS.bat
```

Or:

```bash
python -m pytest -q
```

For Windows packaging, inspect `BUILD_RELEASE.bat`, `BUILD_WINDOWS_APP.bat` and `BUILD_WINDOWS_INSTALLER.bat` and verify their prerequisites on the target build machine.

### Optional Gemini integration

Copy `.env.example` to `.env` and configure `GEMINI_API_KEY`. **Never commit** `.env`, secrets, proprietary recipes, raw production records or identifiable factory images. Cloud AI use may send images and contextual data to a provider and requires a plant-approved confidentiality policy.

## Technology and architecture

The application uses **PySide6** for Windows UI, **OpenCV/NumPy** for local visual analysis, **SQLite/SQLAlchemy** for persistence and **ReportLab** for reports, with layered domain, services, infrastructure and integration components. See [architecture](docs/ARCHITECTURE.md).

## Verification and limitations

The supplied source export (`QCVision-main.zip`, provided 2026-11-03) includes automated test coverage; the preceding documentation review reported **122 passing developer tests**. These are not proof of food-safety accuracy, field reliability, cybersecurity certification or successful plant commissioning. See [validation and limitations](docs/VALIDATION.md).

QCVision is **decision-support software, not an autonomous machine controller or a substitute for HACCP procedures, laboratory testing, calibrated sensors or qualified human release decisions**. Visual appearance alone cannot establish microbiological safety, exact composition or temperatures.

## Roadmap and development history

The repository contains documentation from multiple VisionQC development tracks. See [roadmap](docs/ROADMAP.md) and `CHANGELOG.md` for milestones; do not assume that a historical sprint or release note represents an independently validated production installation.

## Maintainer and licensing

**Maintainer:** [Mohsen Khoram Dastjerdi](https://github.com/mohsen3388)

This repository is currently private. No license file was identified in the supplied archive; do not assume public reuse permission.
