# QCVision scripts

Run these from the repository root using `scripts\NAME.bat` on Windows. Each BAT script automatically changes its current directory to the project root, so you may also double-click it from File Explorer.

| Script | Purpose |
|---|---|
| `SETUP_DEV_ENV.bat` | Set up developer virtual environment |
| `CLEAN_SETUP_AND_RUN.bat` | Rebuild environment and run UI |
| `RUN_VISIONQC.bat` / `RUN_VISIONQC_CLEAN.bat` | Start app |
| `RUN_TESTS.bat` | Run tests |
| `BUILD_WINDOWS_APP.bat` | Build Windows application |
| `BUILD_WINDOWS_INSTALLER.bat` | Build Inno Setup installer |
| `BUILD_RELEASE.bat` | Full release pipeline |
| `PREPARE_OFFLINE_PREREQUISITES.bat` | Download Windows runtime prerequisite for offline package |
| `VERIFY_WINDOWS_BUILD.bat` | Inspect Windows bundle |
| `VERIFY_RELEASE_CONTENTS.py` | Verify release artifacts |
| `run_engine_demo.py` | Sample image CLI, e.g. `python scripts/run_engine_demo.py path-to-image` |

Development prerequisites and packaging tools are not required merely to upload this project to GitHub.
