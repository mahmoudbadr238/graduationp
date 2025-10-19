@echo off
:: Run Sentinel as Administrator
:: This script will request UAC elevation automatically

echo Sentinel - Security Suite
echo Requesting Administrator privileges...
echo.

:: Check if already running as admin
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Already running as Administrator!
    goto :run
) else (
    echo Elevating to Administrator...
)

:: Request elevation
powershell -Command "Start-Process python -ArgumentList 'main.py' -Verb RunAs -WorkingDirectory '%cd%'"
exit

:run
python main.py
