# Turns outside access off: stops the HTTPS gateway and closes ports 80/443. Remove the router port forwards too.
#   powershell -ExecutionPolicy Bypass -File .\windows\remove-remote-access.ps1
$n = "Casa Vestry Gateway"
Unregister-ScheduledTask -TaskName "Smith Apartment Gateway" -Confirm:$false -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "Smith Apartment Gateway (HTTPS)" -ErrorAction SilentlyContinue
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName $n -Confirm:$false
}
Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "Casa Vestry Gateway (HTTPS)" -ErrorAction SilentlyContinue
Write-Host "Outside access is off. Also delete the 80/443 port forwards in UniFi." -ForegroundColor Green
