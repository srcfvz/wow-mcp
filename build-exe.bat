@echo off
setlocal
cd /d %~dp0

echo [*] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found! Please install Python from python.org to build the EXE.
    pause
    exit /b 1
)

echo [*] Installing build dependencies (pyinstaller, pyperclip)...
python -m pip install pyinstaller pyperclip --quiet

echo [*] Building standalone EXE (this may take a minute)...
:: --onefile: Bundles everything into a single EXE
:: --windowed: Prevents a console window from popping up behind the GUI
:: --name: Name of the output file
:: --add-data: Ensures the mcp-server logic is included
pyinstaller --onefile --windowed --name WowMcpBridge ^
    --add-data "bridge;bridge" ^
    --add-data "mcp-server;mcp-server" ^
    --paths "mcp-server" ^
    bridge/gui.py

if %errorlevel% eq 0 (
    echo [OK] Build successful!
    echo [OK] Your standalone file is in: dist\WowMcpBridge.exe
    echo [*] You can now move WowMcpBridge.exe anywhere and run it without Python.
) else (
    echo [!] Build failed. Check the errors above.
)

pause
