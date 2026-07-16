@echo off
title Remove Depot Monitor Startup Entry
set "VBSFILE=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DepotAgent_Monitor.vbs"

if exist "%VBSFILE%" (
    del "%VBSFILE%"
    echo [OK] Removed: %VBSFILE%
) else (
    echo [INFO] No startup entry found.
)
echo.
echo NOTE: If the monitor is currently running, close it via Task Manager
echo       ^(look for pythonw.exe with autoway_monitor.py in the command line^).
pause
