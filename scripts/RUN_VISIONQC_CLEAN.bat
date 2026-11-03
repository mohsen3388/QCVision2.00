@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo VisionQC has not been set up yet.
  echo Run CLEAN_SETUP_AND_RUN.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "main.py"
if errorlevel 1 (
  echo.
  echo VisionQC stopped with an error.
  echo See: %%LOCALAPPDATA%%\VisionQC\crash.log
  pause
)
