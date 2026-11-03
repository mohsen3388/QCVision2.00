@echo off
setlocal
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  echo Development environment not found. Run SETUP_DEV_ENV.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pytest -q
if errorlevel 1 (
  echo Tests failed. Build stopped.
  pause
  exit /b 1
)
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --clean --noconfirm build_tools\VisionQC.spec
if errorlevel 1 (
  echo PyInstaller build failed.
  pause
  exit /b 1
)
echo Build completed: dist\VisionQC\VisionQC.exe
pause
