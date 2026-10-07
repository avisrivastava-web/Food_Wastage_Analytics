@echo off
setlocal
cd /d "%~dp0"
title WasteLens Food Wastage Analytics

if not exist ".venv\Scripts\python.exe" (
    echo First-time setup has not been completed.
    echo Opening setup now...
    call setup_and_run_windows.bat
    exit /b %errorlevel%
)

call ".venv\Scripts\activate.bat"
python -m streamlit run app.py
if errorlevel 1 (
    echo.
    echo The app could not start. Run setup_and_run_windows.bat again to repair dependencies.
    pause
)
