@echo off
title Chrome (Debug Mode) - for Autoway
echo Launching Chrome with remote debugging enabled...
echo.
echo IMPORTANT: Close ALL other Chrome windows first!
echo.
pause

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data"

echo.
echo Chrome launched. Now:
echo   1. Go to https://autoway.hyundai.net/main/ and log in.
echo   2. Open the Depot Agent dashboard.
echo   3. Click "Fetch Unread Emails" in the Inbox Assistant tab.
echo.
pause
