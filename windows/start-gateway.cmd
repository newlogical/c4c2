@echo off
rem Run by the "Smith Apartment Gateway" scheduled task: HTTPS for outside access (Caddy).
setlocal
cd /d "%~dp0"
if exist "%~dp0remote.cmd" call "%~dp0remote.cmd"
if not exist "%~dp0..\logs" mkdir "%~dp0..\logs"
set "SMITH_LOG_DIR=%~dp0..\logs"
set "XDG_DATA_HOME=%~dp0caddy-data"
set "LOG=%~dp0..\logs\gateway-console.log"
:loop
if exist "%LOG%" for %%F in ("%LOG%") do if %%~zF GTR 10485760 move /y "%LOG%" "%LOG%.old" >nul
echo [%date% %time%] starting gateway>>"%LOG%"
"%~dp0caddy.exe" run --config "%~dp0Caddyfile" --adapter caddyfile >>"%LOG%" 2>&1
echo [%date% %time%] gateway stopped - restarting in 5 seconds>>"%LOG%"
ping -n 6 127.0.0.1 >nul
goto loop
