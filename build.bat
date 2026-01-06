@echo off
REM ============================================================
REM Action Library - Build Script
REM ============================================================
REM
REM This script builds a portable one-folder distribution using PyInstaller.
REM
REM Prerequisites:
REM   - Python 3.10+
REM   - PyInstaller: pip install pyinstaller
REM   - All project dependencies installed
REM
REM Output:
REM   dist/ActionLibrary/
REM       ActionLibrary.exe
REM       _internal/
REM       storage/    (empty folder for library data)
REM
REM ============================================================

echo.
echo ============================================
echo    Action Library - Build Script
echo ============================================
echo.

REM Navigate to script directory
cd /d "%~dp0"

REM Check if PyInstaller is installed
where pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyInstaller is not installed.
    echo Please install it with: pip install pyinstaller
    pause
    exit /b 1
)

REM Clean previous builds
echo [1/4] Cleaning previous builds...
if exist "build" (
    rmdir /s /q "build"
    echo       Removed: build/
)
if exist "dist" (
    rmdir /s /q "dist"
    echo       Removed: dist/
)

REM Run PyInstaller
echo.
echo [2/4] Running PyInstaller...
echo       This may take a few minutes...
echo.
pyinstaller build_spec.spec --noconfirm

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

REM Create storage folder
echo.
echo [3/4] Creating storage folder...
if not exist "dist\ActionLibrary\storage" (
    mkdir "dist\ActionLibrary\storage"
    echo       Created: dist/ActionLibrary/storage/
)

REM Create a README for the portable installation
echo.
echo [4/4] Creating portable installation info...
(
echo Action Library - Portable Installation
echo ======================================
echo.
echo This is a portable installation. All your data will be stored in the
echo 'storage' folder next to the executable.
echo.
echo Structure:
echo   ActionLibrary.exe  - Main application
echo   _internal/         - Application dependencies
echo   storage/           - Your animation library data
echo.
echo First Launch:
echo   On first launch, a setup wizard will guide you through configuring
echo   your library storage location.
echo.
echo Moving Your Library:
echo   To move your library to another computer, simply copy this entire
echo   folder to the new location.
echo.
) > "dist\ActionLibrary\README.txt"
echo       Created: dist/ActionLibrary/README.txt

REM Done
echo.
echo ============================================
echo    Build Complete!
echo ============================================
echo.
echo Output: dist\ActionLibrary\
echo.
echo You can now:
echo   1. Run: dist\ActionLibrary\ActionLibrary.exe
echo   2. Copy the entire 'ActionLibrary' folder for distribution
echo.
pause
