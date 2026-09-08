@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先双击“安装依赖.cmd”。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m lulu.backends probe
pause
