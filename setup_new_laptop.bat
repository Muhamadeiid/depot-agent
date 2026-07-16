@echo off
title Setup — Cairo Metro Depot Agent
color 0A
echo ============================================
echo  Cairo Metro Line 1 — Depot Agent Setup
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from python.org and check "Add to PATH".
    pause & exit /b 1
)
echo [OK] Python found.

echo Installing packages...
pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] pip failed. & pause & exit /b 1 )

echo Installing Playwright browser...
playwright install chromium

echo.
echo ============================================
echo  Setup Complete!
echo ============================================
echo.
echo Next: Double-click run_gui.bat to start the dashboard.
echo Then go to Settings and enter your Anthropic API key.
echo.
pause
