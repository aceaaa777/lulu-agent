@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install pytest==9.1.1
if errorlevel 1 goto end
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto end
".venv\Scripts\python.exe" tests\live_smoke.py
:end
pause
