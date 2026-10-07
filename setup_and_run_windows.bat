@echo off
setlocal
cd /d "%~dp0"
title WasteLens - First Time Setup

echo ===============================================
echo   WasteLens Food Wastage Analytics - Setup
echo ===============================================

echo.
where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found.
    echo Install Python 3.11 or newer from python.org and tick "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating local virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
echo Installing/updating required packages...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Starting WasteLens...
python -m streamlit run app.py
exit /b 0

:error
echo.
echo Setup failed. Check your internet connection and the error shown above.
pause
exit /b 1
