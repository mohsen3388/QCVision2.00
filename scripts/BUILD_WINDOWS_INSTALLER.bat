@echo off
setlocal
cd /d "%~dp0.."
if not exist dist\VisionQC\VisionQC.exe (
  echo Application build not found. Running BUILD_WINDOWS_APP.bat...
  call scripts\BUILD_WINDOWS_APP.bat
  if errorlevel 1 exit /b 1
)
set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (
  echo Inno Setup 6 was not found.
  echo Install it, then run this file again.
  pause
  exit /b 1
)
if not exist installer mkdir installer
"%ISCC%" build_tools\VisionQC_Setup.iss
if errorlevel 1 (
  echo Installer build failed.
  pause
  exit /b 1
)
echo Installer completed: installer\VisionQC_Setup_1.0.0_Offline.exe
pause
