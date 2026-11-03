@echo off
setlocal
cd /d "%~dp0.."
call scripts\RUN_TESTS.bat
if errorlevel 1 exit /b 1
call scripts\PREPARE_OFFLINE_PREREQUISITES.bat
if errorlevel 1 exit /b 1
call scripts\BUILD_WINDOWS_APP.bat
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe scripts\VERIFY_RELEASE_CONTENTS.py
if errorlevel 1 exit /b 1
call scripts\BUILD_WINDOWS_INSTALLER.bat
if errorlevel 1 exit /b 1
echo Release completed. The installer is self-contained for a clean 64-bit Windows computer.
pause
