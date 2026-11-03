@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title VisionQC Clean Setup and Run

echo ============================================================
echo VisionQC - Clean setup from this project folder
echo ============================================================
echo Current folder: %CD%
echo.

if not exist "requirements.txt" goto missing
if not exist "requirements-dev.txt" goto missing
if not exist "main.py" goto missing
if not exist "visionqc" goto missing

if exist ".venv" (
  echo Removing old local environment...
  rmdir /s /q ".venv"
)

set "PY_CMD="
py -3.11 -c "import sys; print(sys.executable)" >nul 2>&1 && set "PY_CMD=py -3.11"
if not defined PY_CMD python -c "import sys; assert sys.version_info[:2] == (3,11)" >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD goto nopython

echo Creating a new local Python environment...
%PY_CMD% -m venv ".venv" || goto failed

call ".venv\Scripts\activate.bat" || goto failed
python -m pip install --upgrade pip wheel setuptools || goto failed
python -m pip install -r "requirements.txt" || goto failed

echo.
echo Checking VisionQC imports...
python -c "from visionqc.ui.settings_page import SettingsPage; from visionqc.core.database import initialize_database; print('Core import check passed')" || goto failed

echo.
echo Setup completed. Starting VisionQC...
python "main.py"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo VisionQC exited with code %RC%.
  echo Crash log may be in: %%LOCALAPPDATA%%\VisionQC\crash.log
  pause
)
exit /b %RC%

:missing
echo ERROR: This file is not inside the VisionQC project folder.
echo Required files: main.py, requirements.txt, requirements-dev.txt, visionqc folder.
pause
exit /b 1

:nopython
echo ERROR: A working 64-bit Python 3.11 installation was not found.
echo Install Python 3.11 x64, select "Add Python to PATH", then run this file again.
pause
exit /b 1

:failed
echo.
echo SETUP FAILED. The window will remain open so you can read the error.
pause
exit /b 1
