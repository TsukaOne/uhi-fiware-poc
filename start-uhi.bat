@echo off
setlocal
cd /d "%~dp0"

set "SITE_URL=http://127.0.0.1:3000"
set "PREDICTION_HEALTH_URL=http://127.0.0.1:8002/health"
set "DOCKER_DESKTOP_EXE=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set "POLL_INTERVAL_SECONDS=2"
set "MAX_POLL_ATTEMPTS=90"
set "SUCCESS_MESSAGE_SECONDS=5"

docker info >nul 2>&1 || call :start_docker_desktop || goto :fail

echo Building and starting the containers...
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build prediction frontend || goto :fail

echo Waiting for the prediction service...
call :wait_until "curl -sf %PREDICTION_HEALTH_URL%" || goto :prediction_not_ready

echo UHI Viewer is running at %SITE_URL%
start "" "%SITE_URL%"
timeout /t %SUCCESS_MESSAGE_SECONDS% >nul
exit /b 0

:start_docker_desktop
echo Starting Docker Desktop...
start "" "%DOCKER_DESKTOP_EXE%"
call :wait_until "docker info" && exit /b 0
echo Docker Desktop did not start in time.
exit /b 1

:prediction_not_ready
echo The prediction service is not answering. See its logs with:
echo     docker logs uhi-prediction
goto :fail

:wait_until
for /l %%i in (1,1,%MAX_POLL_ATTEMPTS%) do (
    %~1 >nul 2>&1 && exit /b 0
    timeout /t %POLL_INTERVAL_SECONDS% /nobreak >nul
)
exit /b 1

:fail
echo.
echo Launch failed.
pause
exit /b 1
