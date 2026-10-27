# Turns auto-start off and stops the background backend + panel. Run in an Administrator PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\windows\remove-autostart.ps1
foreach ($n in "Casa Vestry Backend", "Casa Vestry Panel", "Smith Apartment Backend", "Smith Apartment Panel") {
  if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $n -Confirm:$false
    Write-Host "Removed: $n" -ForegroundColor Green
  }
}
foreach ($p in 8001, 3000) {
  Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Write-Host "Auto-start is off. You can run the backend and panel by hand again."
