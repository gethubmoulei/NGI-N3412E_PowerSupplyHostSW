@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   PowerSupply - PyInstaller Build Script
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)

echo [1/3] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

echo [2/3] Installing dependencies...
pip install -r requirements.txt -q

echo [3/3] Building executable...
pyinstaller PowerSupply.spec --noconfirm --clean

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   BUILD SUCCESSFUL
    echo   Output: dist\PowerSupply.exe
    echo ============================================
) else (
    echo.
    echo [ERROR] Build failed. Check the output above for details.
)

pause
