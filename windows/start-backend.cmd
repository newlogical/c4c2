@echo off
rem Run by the "Casa Vestry Backend" scheduled task. Restarts the backend if it ever stops.
setlocal
cd /d "%~dp0..\backend"
if exist "%~dp0path.cmd" call "%~dp0path.cmd"
if not exist "%~dp0..\logs" mkdir "%~dp0..\logs"
set "LOG=%~dp0..\logs\backend.log"
set PYTHONUNBUFFERED=1
:loop
if exist "%LOG%" for %%F in ("%LOG%") do if %%~zF GTR 10485760 move /y "%LOG%" "%LOG%.old" >nul
echo [%date% %time%] starting backend>>"%LOG%"
".venv\Scripts\python.exe" -m uvicorn server:app --host 0.0.0.0 --port 8001 >>"%LOG%" 2>&1
echo [%date% %time%] backend stopped - restarting in 5 seconds>>"%LOG%"
ping -n 6 127.0.0.1 >nul
goto loop
