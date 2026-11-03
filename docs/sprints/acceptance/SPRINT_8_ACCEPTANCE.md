# VisionQC Sprint 8 Acceptance

Version: 0.8.0

## Goal
Deliver a deployment-ready, offline Windows distribution that can be installed on a clean 64-bit Windows 10/11 computer without Python, PySide6, OpenCV, NumPy, SQLAlchemy, ReportLab, Git, an IDE, or other specialist software already installed.

## Implemented
- Standalone PyInstaller application remains the application payload.
- Full offline Inno Setup installer includes the complete `dist/VisionQC` directory.
- Microsoft Visual C++ 2015-2022 x64 redistributable is downloaded on the build computer and embedded into the installer.
- Installer checks 64-bit Windows and installs the Microsoft runtime silently when required.
- Installer uses administrative privileges for reliable machine-wide installation.
- New `PREPARE_OFFLINE_PREREQUISITES.bat` build step.
- New release-content verifier.
- New Deployment tab in Settings & Diagnostics.
- Runtime inventory, writable-directory checks, disk-space check and standalone-build status.
- Exportable deployment readiness JSON report.
- Version and installer metadata updated to 0.8.0.

## Target computer requirements
- 64-bit Windows 10 (1809+) or Windows 11.
- No Python or developer software required.
- No internet connection required during installation or normal use.
- Camera drivers remain the responsibility of Windows or the camera manufacturer.

## Release output
`installer/VisionQC_Setup_0.8.0_Offline.exe`
