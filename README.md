# QCVision (VisionQC)

### AI-powered food production monitoring and quality intelligence

**Burger meat production monitoring · Live visual inspection · Voice-guided mixer operators · Role-aware quality alerts · Human-supervised decisions**

QCVision (named **VisionQC** in the application source) is an offline-first Windows desktop quality-intelligence platform designed for food-manufacturing workflows, especially **burger meat preparation and mixing**. Its intended operating workflow connects observations and quality records from incoming raw meat through preparation, grinding, ingredient dosing, mixing, in-process inspection, and discharge.

Rather than functioning only as a defect detector, QCVision combines **computer vision, compatible cameras, production context, operator headset communication, QC review, factory knowledge, and analytics**. Operator, quality engineer, and production manager interfaces are designed for different decisions and levels of detail.

> **Current status:** Engineering prototype / pre-production. Capabilities represented in source code and tests are not evidence of commissioning every station or proving food-safety compliance at a factory. Physical integration, calibration, validation, role-specific routing, and site acceptance remain deployment-dependent.

## End-to-end burger meat production workflow

| Production stage | Intended monitoring and quality context |
| --- | --- |
| Raw meat reception | Batch/lot information, receipt inspection and incoming-quality evidence |
| Preparation and grinding | Line status, visible product condition and configured checks |
| Ingredient addition | Recipe/batch context and connected instrument or operator inputs where available |
| Mixer / kettle operation | Live video, visual mixture indicators, process continuity and operator alerts |
| In-process quality control | Image evidence, reference comparisons, rules, QC investigation and approvals |
| Discharge / handoff | Final evidence, batch disposition, traceability and reporting |

Visual inspection **cannot** directly establish microbial safety, precise composition, or internal temperature. Those require calibrated instruments, sampling, or laboratory tests.

## Features at a glance

| Capability | What is represented in the codebase |
| --- | --- |
| Image inspection | OpenCV/NumPy visual measurement, region-of-interest selection, rule-based interpretation and evidence |
| Video and cameras | Live USB cameras, RTSP/HTTP sources, multi-camera configuration and video temporal analysis |
| Mixing quality intelligence | Product-health versus process-health assessment, detector/score/trigger workflows, visual references and Golden Batch comparisons |
| Operator communication | Spoken headset alerts, voice interaction and “Vision / ویژن” wake-word workflows; deployment depends on hardware/Windows speech support |
| QC specialist workflow | Batch inspection, review and approval gates, events, history, traceable decisions and reports |
| Management oversight | Production trends, SPC, Cp/Cpk, downtime, OEE and dashboards |
| Factory intelligence | Factory Memory, knowledge graph, root-cause hypotheses, predictive quality and AI Factory Engineer briefings |
| Optional cloud AI | Google Gemini image/video review with an approved connection, credentials and data-sharing policy |
| Integration | Local REST/API-key interfaces, audit/RBAC workflows, offline synchronization and configurable connector checks |
| Windows delivery | Development scripts, Windows build/installer configurations and release validation utilities |

## Three levels of alerts and interaction

- **Mixer / line operator:** short actionable alerts, audible headset guidance, operator questions and acknowledgements.
- **QC specialist / quality engineer:** supporting snapshots, measurements, root-cause evidence and review/approval controls.
- **Production / project manager:** consolidated exceptions, performance trends and escalation information.

Specific delivery/escalation policies must be configured and validated for the actual site. QCVision assists authorized personnel; it is **not** an autonomous production-stop or product-release controller.

## How the platform works

```text
Raw meat → Preparation → Grinding → Dosing → Mixing → QC → Discharge
    |           |            |        |        |       |        |
    +-----------+------------+--------+--------+-------+--------+
                                |
                 Cameras / batch context / sensors*
                                |
                    Local computer-vision rules
                                |
                   Product + process assessment
                                |
                     Evidence and quality events
                                |
             +------------------+------------------+
             |                  |                  |
      Operator / headset   QC engineer       Production manager
      Immediate guidance   Review & approval  Trends & escalation
             +------------------+------------------+
                                |
                   Reports / audit / Factory Memory
                                |
                    Optional Gemini AI review

* Sensor integration depends on available connectors and site commissioning.
```

## Getting started (Windows development)

The source is oriented toward **Windows 10/11 x64 and Python 3.11**. Run the included scripts **from the repository root**:

```bat
scripts\SETUP_DEV_ENV.bat
scripts\RUN_VISIONQC.bat
```

Alternatively, set up a compatible Python environment, install `requirements-dev.txt`, then run:

```bat
python main.py
```

Run developer tests:

```bat
scripts\RUN_TESTS.bat
```

Or:

```bash
python -m pytest -q
```

Build and packaging entry points are located in `scripts/` (`BUILD_RELEASE.bat`, `BUILD_WINDOWS_APP.bat`, and `BUILD_WINDOWS_INSTALLER.bat`). They resolve the repository root before running. The PyInstaller spec is in `build_tools/VisionQC.spec`.

### Optional Gemini review

Copy `.env.example` to `.env` and provide your own `GEMINI_API_KEY`. Do not commit `.env`, API keys, proprietary recipes, production images, or identifiable factory data. Cloud review may transmit selected content to the provider and should require factory authorization.

## Architecture and documentation

The application uses **PySide6**, **OpenCV / NumPy**, **SQLite / SQLAlchemy**, and **ReportLab**, alongside local analysis and integration modules. Historical sprint, acceptance, and release reports are preserved but moved out of the repository root.

- [Documentation index](docs/README.md)
- [Architecture notes](docs/architecture/ARCHITECTURE_SPRINT_1.md)
- [Release notes](docs/releases/)
- [Sprint acceptance evidence](docs/sprints/acceptance/)
- [Development history](docs/releases/CHANGELOG.md)

## Validation and limitations

The repository contains automated tests and engineering evidence, but source-level testing alone does **not** establish production accuracy, cybersecurity certification, HACCP compliance, or commissioning under real factory lighting, noise, and operating conditions. The platform does not replace calibrated instrumentation, laboratory tests, or a food business's authorized release procedures.

## Maintainer and license

Maintainer: [Mohsen Khoram Dastjerdi](https://github.com/mohsen3388). No license was found in this source archive; reuse rights should not be assumed.

For the complete root-level script inventory and usage, see [scripts/README.md](scripts/README.md).
