@echo off
setlocal
cd /d "%~dp0"

python -m PyInstaller --noconfirm --clean --onefile ^
  --name detector_cli ^
  --hidden-import google.genai ^
  --hidden-import google.genai.types ^
  --hidden-import dotenv ^
  --collect-submodules google.genai ^
  detector_cli.py

if errorlevel 1 exit /b %errorlevel%
echo Built: %CD%\dist\detector_cli.exe
