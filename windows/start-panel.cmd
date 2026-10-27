@echo off
rem Run by the "Smith Apartment Panel" scheduled task. Serves frontend\build on port 3000.
setlocal
cd /d "%~dp0..\frontend"
if exist "%~dp0path.cmd" call "%~dp0path.cmd"
if not exist "%~dp0..\logs" mkdir "%~dp0..\logs"
set "LOG=%~dp0..\logs\panel.log"
:loop
if exist "%LOG%" for %%F in ("%LOG%") do if %%~zF GTR 10485760 move /y "%LOG%" "%LOG%.old" >nul
echo [%date% %time%] starting panel>>"%LOG%"
call "%SERVE%" -s build -l 3000 --no-clipboard >>"%LOG%" 2>&1
echo [%date% %time%] panel stopped - restarting in 5 seconds>>"%LOG%"
ping -n 6 127.0.0.1 >nul
goto loop
