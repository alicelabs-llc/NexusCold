@echo off
setlocal
cd /d "%~dp0"
title TechDigital Prospect by AliceLabs LLC Builder
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :failed
python -m PyInstaller --noconfirm --onefile --windowed --name "TechDigital_Prospect_v6.4" --collect-all customtkinter --hidden-import pandas --hidden-import aiohttp "ALICELABS_EXTRACTOR_GUI.py"
if errorlevel 1 goto :failed
echo Build complete: dist\TechDigital_Prospect_v6.4.exe
pause
exit /b 0
:failed
echo Build failed. Read the error above.
pause
exit /b 1
