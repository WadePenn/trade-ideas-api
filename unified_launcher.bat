@echo off
cd /d "%~dp0"

echo ================================
echo   STARTING IBKR + API + GUI
echo ================================
echo.

:: ---------------------------------
:: 1. Start IBKR TWS or Gateway
:: ---------------------------------
echo Launching IBKR TWS...
start "IBKR TWS" "C:\Jts\tws.exe"
timeout /t 12 >nul

:: ---------------------------------
:: 2. Start FastAPI backend
:: ---------------------------------
echo Launching FastAPI backend...
start "FASTAPI BACKEND" cmd /k "call venv\Scripts\activate && uvicorn main:app --reload"
timeout /t 3 >nul

:: ---------------------------------
:: 3. Start GUI Control Center
:: ---------------------------------
echo Launching GUI Control Center...
start "GUI CONTROL CENTER" cmd /k "call venv\Scripts\activate && python -m gui.main_gui"

echo.
echo All systems launched.
echo.
