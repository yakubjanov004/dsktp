# Port 3200 va 8001 ni to'xtatish uchun PowerShell script
# Ishlatish: .\kill_ports.ps1

Write-Host "Port 3200 ni to'xtatish..." -ForegroundColor Yellow
$port3200 = Get-NetTCPConnection -LocalPort 3200 -ErrorAction SilentlyContinue
if ($port3200) {
    $port3200 | ForEach-Object {
        $pid = $_.OwningProcess
        Write-Host "Killing process $pid on port 3200..." -ForegroundColor Red
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Port 3200 to'xtatildi!" -ForegroundColor Green
} else {
    Write-Host "Port 3200 bo'sh" -ForegroundColor Green
}

Write-Host "`nPort 8001 ni to'xtatish..." -ForegroundColor Yellow
$port8001 = Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue
if ($port8001) {
    $port8001 | ForEach-Object {
        $pid = $_.OwningProcess
        Write-Host "Killing process $pid on port 8001..." -ForegroundColor Red
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Port 8001 to'xtatildi!" -ForegroundColor Green
} else {
    Write-Host "Port 8001 bo'sh" -ForegroundColor Green
}

Write-Host "`nBarcha portlar tozalandi!" -ForegroundColor Cyan

