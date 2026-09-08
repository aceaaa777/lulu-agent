@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto nopy
py -3.12 bootstrap.py
if errorlevel 1 goto fail
echo 安装完成。请打开 Ollama，再双击“启动 Lulu Agent.cmd”。
pause
exit /b 0
:nopy
echo 请先从 https://www.python.org/downloads/windows/ 安装 Python 3.12，并保留 Python Launcher。
pause
exit /b 1
:fail
echo 安装未完成，请保留上方错误信息。
pause
exit /b 1
