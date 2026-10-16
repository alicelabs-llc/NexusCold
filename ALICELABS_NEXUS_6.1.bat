@echo off
cd /d "%~dp0"
python ALICELABS_EXTRACTOR_GUI.py
if errorlevel 1 pause
