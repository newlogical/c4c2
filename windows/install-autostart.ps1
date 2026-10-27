# Starts the Casa Vestry backend + panel at power-on (before anyone signs in) and keeps them running.
# Run in an Administrator PowerShell from the project folder:
#   powershell -ExecutionPolicy Bypass -File .\windows\install-autostart.ps1
# Safe to re-run: after a git pull / yarn build, re-run it to restart both with the new code.
$ErrorActionPreference = "Stop"
$win = $PSScriptRoot
$root = Split-Path -Parent $win
$tasks = @(
  @{ Name = "Casa Vestry Backend"; Cmd = "start-backend.cmd"; Port = 8001; Url = "http://localhost:8001/api/" },
  @{ Name = "Casa Vestry Panel";   Cmd = "start-panel.cmd";   Port = 3000; Url = "http://localhost:3000/" }
)

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "Please run this in PowerShell opened with 'Run as administrator'." -ForegroundColor Red; exit 1 }

Write-Host "Checking the setup..." -ForegroundColor Cyan
if (-not (Test-Path "$root\backend\.venv\Scripts\python.exe")) { Write-Host "Backend not set up: run step 3 of WINDOWS_SETUP.md first (backend\.venv missing)." -ForegroundColor Red; exit 1 }
if (-not (Test-Path "$root\backend\.env")) { Write-Host "backend\.env is missing (step 3 of WINDOWS_SETUP.md)." -ForegroundColor Red; exit 1 }
if (-not (Test-Path "$root\frontend\build\index.html")) { Write-Host "Panel not built yet: cd frontend, then run 'yarn build'." -ForegroundColor Red; exit 1 }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Write-Host "Node.js not found on PATH." -ForegroundColor Red; exit 1 }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Host "Note: ffmpeg not found on PATH - the camera's live feed won't work until it is." -ForegroundColor Yellow }

$serve = Get-Command serve.cmd -ErrorAction SilentlyContinue
if (-not $serve) {
  Write-Host "Installing the 'serve' web server (one time)..." -ForegroundColor Cyan
  npm install -g serve | Out-Host
  $serve = Get-Command serve.cmd -ErrorAction SilentlyContinue
  if (-not $serve) { Write-Host "Couldn't install 'serve'. Try: npm install -g serve" -ForegroundColor Red; exit 1 }
}

# The tasks run as SYSTEM, so save today's PATH (python, node, ffmpeg) for them.
Set-Content -Path "$win\path.cmd" -Encoding ASCII -Value @(
  "@set `"PATH=$env:Path`"",
  "@set `"SERVE=$($serve.Source)`""
)

Write-Host "Stopping anything already using ports 8001 / 3000 (close old backend/panel windows)..." -ForegroundColor Cyan
foreach ($old in "Smith Apartment Backend", "Smith Apartment Panel") {  # tasks from before the rename
  if (Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $old -Confirm:$false
  }
}
foreach ($t in $tasks) {
  if (Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue) { Stop-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue }
}
foreach ($t in $tasks) {
  Get-NetTCPConnection -LocalPort $t.Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 2

foreach ($t in $tasks) {
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"`"$win\$($t.Cmd)`"`"" -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -AtStartup
  $trigger.Delay = "PT20S"  # give MongoDB and the network a moment after power-on
  $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
  Start-ScheduledTask -TaskName $t.Name
  Write-Host "Registered + started: $($t.Name)" -ForegroundColor Green
}

Write-Host "Waiting for both to answer (up to 60 s)..." -ForegroundColor Cyan
foreach ($t in $tasks) {
  $ok = $false
  for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
    try { Invoke-WebRequest -Uri $t.Url -UseBasicParsing -TimeoutSec 3 | Out-Null; $ok = $true } catch { Start-Sleep -Seconds 2 }
  }
  if ($ok) { Write-Host "  OK  $($t.Name)  ($($t.Url))" -ForegroundColor Green }
  else { Write-Host "  NOT ANSWERING  $($t.Name) - see $root\logs\" -ForegroundColor Red }
}
Write-Host ""
Write-Host "Done. Both now start by themselves at every power-on, even before anyone signs in." -ForegroundColor Green
Write-Host "Logs: $root\logs\backend.log and panel.log"
