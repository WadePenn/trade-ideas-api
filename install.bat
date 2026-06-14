@echo off
title Trade Ideas Panel - One-Click Installer
color 0B
echo.
echo  +------------------------------------------+
echo  ^|  Trade Ideas Panel  -  One-Click Setup   ^|
echo  ^|  github.com/WadePenn/trade-ideas-api     ^|
echo  +------------------------------------------+
echo.
echo  Downloading installer from GitHub...
echo.
powershell -ExecutionPolicy Bypass -Command "$t=\"$env:TEMP\ti_$PID.ps1\"; try { Invoke-WebRequest 'https://raw.githubusercontent.com/WadePenn/trade-ideas-api/master/install.ps1' -OutFile $t -UseBasicParsing; & powershell -ExecutionPolicy Bypass -File $t; Remove-Item $t -Force -ErrorAction SilentlyContinue } catch { Write-Host 'ERROR: Could not reach GitHub. Check internet connection.' -ForegroundColor Red; Remove-Item $t -Force -ErrorAction SilentlyContinue; exit 1 }"
if %errorlevel% neq 0 (
    echo.
    echo  Installation failed. Check your internet connection and try again.
    pause
    exit /b 1
)
