@echo off
title Trade Ideas ? Starting...
color 0A
echo.
echo  ========================================
echo    Trade Ideas API  ^|  Starting Up...
echo  ========================================
echo.
start /d "C:\Users\Valued Customer\fastapi_api" "Trade Ideas Server" cmd /k "py -3.11 -m uvicorn main:app --reload"
echo  [1/3] Server starting...
timeout /t 4 /nobreak >nul
start /d "C:\Users\Valued Customer\fastapi_api" "Trade Ideas Panel" cmd /k "py -3.11 run_panel.py"
echo  [2/3] Panel launching...
timeout /t 2 /nobreak >nul
start "" "http://localhost:8000/docs"
echo  [3/3] Browser opening...
echo.
echo  All systems running!  Close this window at any time.
pause >nul
