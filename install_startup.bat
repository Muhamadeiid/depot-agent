@echo off
setlocal EnableDelayedExpansion
title Install Depot Monitor on Startup

set "PROJDIR=%~dp0"
set "PROJDIR=!PROJDIR:~0,-1!"
set "STARTUPDIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBSFILE=%STARTUPDIR%\DepotAgent_Monitor.vbs"

echo Locating pythonw.exe...
set "PYW="
for %%p in (
  "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
  "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
  "%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
  "C:\Python313\pythonw.exe"
  "C:\Python312\pythonw.exe"
  "C:\Python311\pythonw.exe"
) do if exist %%p if "!PYW!"=="" set "PYW=%%~p"

if "!PYW!"=="" (
  where pythonw.exe >nul 2>&1
  if !errorlevel!==0 for /f "delims=" %%p in ('where pythonw.exe') do if "!PYW!"=="" set "PYW=%%p"
)

if "!PYW!"=="" (
  echo [ERROR] pythonw.exe not found. Install Python first.
  pause & exit /b 1
)

echo Found: !PYW!
echo Writing launcher to !VBSFILE!

if not exist "!STARTUPDIR!" mkdir "!STARTUPDIR!"

(
  echo Set WshShell = CreateObject^("WScript.Shell"^)
  echo WshShell.CurrentDirectory = "!PROJDIR!"
  echo WshShell.Run Chr^(34^) ^& "!PYW!" ^& Chr^(34^) ^& " " ^& Chr^(34^) ^& "!PROJDIR!\autoway_monitor.py" ^& Chr^(34^), 0, False
) > "!VBSFILE!"

echo.
echo [OK] Startup entry installed.
echo   Runs silently on next login: !PYW! autoway_monitor.py
echo   To remove: run uninstall_startup.bat
echo.
pause
