@echo off
echo ==========================================
echo      WowMCP Windows Build Script
echo ==========================================

echo [1/3] Checking dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo [2/3] Cleaning previous builds...
rmdir /s /q build
rmdir /s /q dist

echo [3/3] Building Executable...
pyinstaller wow_mcp.spec

echo.
if exist "dist\WowMCP.exe" (
    echo [SUCCESS] Build complete!
    echo Binary location: dist\WowMCP.exe
) else (
    echo [ERROR] Build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo [4/4] Building Inno Setup installer (optional)...
where ISCC >nul 2>nul
if %ERRORLEVEL%==0 (
    ISCC wow_mcp_installer.iss
    if exist "dist\WowMCP-Setup.exe" (
        echo [SUCCESS] Installer created: dist\WowMCP-Setup.exe
    ) else (
        echo [WARN] Inno Setup ran but installer not found in dist\
    )
) else (
    echo [INFO] Inno Setup Compiler (ISCC) not found. Skipping installer build.
    echo        Install Inno Setup and ensure ISCC is in PATH to build setup.exe.
)

pause
