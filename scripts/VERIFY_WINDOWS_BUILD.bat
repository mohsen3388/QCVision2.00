@echo off
setlocal
cd /d "%~dp0.."
if not exist dist\VisionQC\VisionQC.exe (
  echo ERROR: dist\VisionQC\VisionQC.exe was not found.
  echo Run BUILD_WINDOWS_APP.bat first.
  pause
  exit /b 1
)
if not exist dist\VisionQC\_internal (
  echo WARNING: PyInstaller internal dependency folder not found.
)
echo Windows application bundle exists.
echo Launching a manual smoke test...
start "" dist\VisionQC\VisionQC.exe
pause
