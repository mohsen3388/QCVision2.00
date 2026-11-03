@echo off
setlocal
cd /d "%~dp0.."
set "PREREQ_DIR=%CD%\prerequisites"
if not exist "%PREREQ_DIR%" mkdir "%PREREQ_DIR%"
set "VCREDIST=%PREREQ_DIR%\VC_redist.x64.exe"
if exist "%VCREDIST%" (
  echo Microsoft Visual C++ runtime already prepared.
  exit /b 0
)
echo Downloading the official Microsoft Visual C++ 2015-2022 x64 runtime for inclusion in the offline installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%VCREDIST%'"
if errorlevel 1 (
  echo Failed to download prerequisite. Check the build computer internet connection.
  exit /b 1
)
for %%F in ("%VCREDIST%") do if %%~zF LSS 1000000 (
  echo Downloaded prerequisite looks invalid.
  del /q "%VCREDIST%"
  exit /b 1
)
echo Offline prerequisite prepared: %VCREDIST%
