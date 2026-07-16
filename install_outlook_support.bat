@echo off
title Install Outlook Support
color 0A
echo ============================================
echo   Installing Outlook Desktop Support
echo ============================================
echo.
pip install pywin32
if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed.
    echo Make sure Python is installed and in PATH.
    pause
    exit /b 1
)
echo.
echo ============================================
echo   [OK] pywin32 installed successfully!
echo ============================================
echo.
echo Now the Inbox Assistant can read your Outlook emails.
echo Just make sure Outlook Desktop is OPEN when you use it.
echo.
pause
