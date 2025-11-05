@echo off
REM Setup script for processor-engine development environment (Windows)

setlocal enabledelayedexpansion

echo.
echo 🔧 Setting up processor-engine environment...
echo.

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ Python version: %PYTHON_VERSION%

REM Create virtual environment if it doesn't exist
if not exist "venv\" (
    echo 📦 Creating virtual environment...
    python -m venv venv
) else (
    echo ✓ Virtual environment already exists
)

REM Activate virtual environment
echo ✓ Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo 📦 Upgrading pip...
python -m pip install --upgrade pip setuptools wheel

REM Install dependencies
echo 📦 Installing dependencies and development tools...
pip install -e ".[dev]"

echo.
echo ✅ Setup complete!
echo.
echo 📝 Next steps:
echo    1. Activate the virtual environment:
echo       PowerShell: .\venv\Scripts\Activate.ps1
echo       CMD: .\venv\Scripts\activate.bat
echo.
echo    2. Run the processor:
echo       python scripts/run.py C:\path\to\timetable.png
echo.

pause
