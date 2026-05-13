@echo off
setlocal
cd /d %~dp0

echo [*] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found! Please install Python from python.org
    pause
    exit /b 1
)

echo [*] Installing dependencies (pyperclip)...
python -m pip install pyperclip --quiet

echo [*] Starting WowMCP Bridge GUI...
start "" python bridge/gui.py

echo [*] Bridge window should open shortly. Keep this window open if you want to see errors, or close it.
pause
