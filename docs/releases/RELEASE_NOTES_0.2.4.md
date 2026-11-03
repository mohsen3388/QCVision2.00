# VisionQC 0.2.4 Release Notes

This sprint turns the 2.x prototype into a more installable and operational Windows desktop product baseline.

The first launch now guides the user through factory identity, operator, local storage and camera settings. VisionQC creates a local SQLite database automatically. The new Batch Workspace records batch identity, production stage, notes and a confirmed final QC outcome. History & Replay now provides the first working local batch registry.

The Settings & Diagnostics capability is available from both the sidebar and ALL FEATURES menu. It provides storage configuration, USB-camera testing, system diagnostics and an offline ZIP support bundle.

The Windows build pipeline now runs automated tests before packaging. The standalone application remains targeted at `dist\VisionQC\VisionQC.exe`, and Inno Setup produces `VisionQC_Setup_0.2.4.exe`. Production data is stored in LocalAppData and is not silently deleted during uninstall.

Final Windows executable and hardware validation still require a Windows 10/11 x64 machine.
