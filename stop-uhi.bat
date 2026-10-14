@echo off
setlocal
cd /d "%~dp0"

set "SUCCESS_MESSAGE_SECONDS=3"

docker compose stop prediction frontend || goto :fail

echo UHI Viewer is stopped.
timeout /t %SUCCESS_MESSAGE_SECONDS% >nul
exit /b 0

:fail
echo.
echo Stop failed.
pause
exit /b 1
