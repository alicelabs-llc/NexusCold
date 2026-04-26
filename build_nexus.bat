@echo off
title AliceLabs Nexus WORLD EDITION Builder
echo ===================================================
echo   AliceLabs B2B Nexus WORLD EDITION v6.0
echo   Builder — Generates standalone .exe
echo ===================================================
echo.
echo [1/3] Installing/Updating requirements...
pip install --quiet customtkinter openpyxl requests beautifulsoup4 pyinstaller aiohttp pandas 2>nul
echo.
echo [2/3] Building World Edition Executable...
echo   This may take 1-3 minutes...
pyinstaller --noconfirm --onefile --windowed --name "AliceLabs_Nexus_WORLD_v6.0" --add-data "C:\Users\Usuario\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\customtkinter;customtkinter/" --add-data "enrich_cache.json;." --hidden-import pandas --hidden-import aiohttp --hidden-import asyncio "ALICELABS_EXTRACTOR_GUI.py"
echo.
echo [3/3] Copying to desktop...
copy /Y "dist\AliceLabs_Nexus_WORLD_v6.0.exe" "..\AliceLabs_Nexus_WORLD_v6.0.exe" 2>nul
echo.
echo ===================================================
echo   ✅ BUILD COMPLETE!
echo   📁 dist\AliceLabs_Nexus_WORLD_v6.0.exe
echo   📁 ..\AliceLabs_Nexus_WORLD_v6.0.exe (desktop)
echo ===================================================
pause
