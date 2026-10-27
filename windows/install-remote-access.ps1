# Sets up outside access: downloads Caddy (HTTPS gateway), saves your domain, opens ports 80/443 in the
# Windows firewall, and starts it at every power-on. Run in an Administrator PowerShell from the project folder:
#   powershell -ExecutionPolicy Bypass -File .\windows\install-remote-access.ps1 -Domain home.example.com -Email you@example.com
# Safe to re-run (e.g. to change the domain).
param(
  [Parameter(Mandatory = $true)][string]$Domain,
  [Parameter(Mandatory = $true)][string]$Email
)
$ErrorActionPreference = "Stop"
$win = $PSScriptRoot
$root = Split-Path -Parent $win
$task = "Smith Apartment Gateway"

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "Please run this in PowerShell opened with 'Run as administrator'." -ForegroundColor Red; exit 1 }
$Domain = $Domain.Trim().ToLower() -replace '^https?://', '' -replace '/.*$', ''
if ($Domain -notmatch '^[a-z0-9.-]+\.[a-z]{2,}$') { Write-Host "That doesn't look like a domain (e.g. home.smithapartment.com)." -ForegroundColor Red; exit 1 }

if (-not (Get-ScheduledTask -TaskName "Smith Apartment Backend" -ErrorAction SilentlyContinue)) {
  Write-Host "Run .\windows\install-autostart.ps1 first so the backend and panel are running." -ForegroundColor Red; exit 1
}

if (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue) { Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue }
Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

if (-not (Test-Path "$win\caddy.exe")) {
  Write-Host "Downloading Caddy (HTTPS gateway)..." -ForegroundColor Cyan
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri "https://caddyserver.com/api/download?os=windows&arch=amd64" -OutFile "$win\caddy.exe" -UseBasicParsing
}
& "$win\caddy.exe" version | Out-Host

Set-Content -Path "$win\remote.cmd" -Encoding ASCII -Value @(
  "@set `"SMITH_DOMAIN=$Domain`"",
  "@set `"SMITH_ACME_EMAIL=$Email`""
)

$env:SMITH_DOMAIN = $Domain; $env:SMITH_ACME_EMAIL = $Email; $env:SMITH_LOG_DIR = "$root\logs"
& "$win\caddy.exe" validate --config "$win\Caddyfile" --adapter caddyfile | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "Caddyfile check failed (see above)." -ForegroundColor Red; exit 1 }

Write-Host "Opening ports 80 and 443 in Windows Firewall..." -ForegroundColor Cyan
Remove-NetFirewallRule -DisplayName "Smith Apartment Gateway (HTTPS)" -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Smith Apartment Gateway (HTTPS)" -Direction Inbound -Protocol TCP -LocalPort 80,443 -Action Allow -Profile Any | Out-Null

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"`"$win\start-gateway.cmd`"`"" -WorkingDirectory $win
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT30S"
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $task
Write-Host "Registered + started: $task" -ForegroundColor Green

Write-Host "Waiting for the security certificate (up to 90 s; needs the port forwards + DNS already set)..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
  try { Invoke-WebRequest -Uri "https://$Domain/api/bootstrap" -UseBasicParsing -TimeoutSec 3 | Out-Null; $ok = $true } catch { Start-Sleep -Seconds 3 }
}
if ($ok) { Write-Host "  OK  https://$Domain is live" -ForegroundColor Green }
else { Write-Host "  Not answering yet. Check DNS + port forwards, then see $root\logs\gateway-console.log" -ForegroundColor Yellow }
Write-Host ""
Write-Host "Next: in Settings -> Outside access, add a login for you and one for the client." -ForegroundColor Green
