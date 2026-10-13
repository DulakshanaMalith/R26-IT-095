# IPMS integrated launcher (PowerShell alternative to START_ALL.bat)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$services = @(
    @{ Name = "Scheduling API"; Batch = "svc1_scheduling.bat"; Port = 8000 },
    @{ Name = "Quality API"; Batch = "svc2_quality_api.bat"; Port = 9000 },
    @{ Name = "Quality UI"; Batch = "svc3_quality_ui.bat"; Port = 5173 },
    @{ Name = "Risk API"; Batch = "svc4_risk.bat"; Port = 5000 },
    @{ Name = "Risk UI"; Batch = "svc7_risk_ui.bat"; Port = 5175 },
    @{ Name = "Team API"; Batch = "svc5_team_api.bat"; Port = 8003 },
    @{ Name = "Team UI"; Batch = "svc6_team_ui.bat"; Port = 5174 }
)

Write-Host ""
Write-Host "  ================================================================"
Write-Host "   IPMS - Starting PostgreSQL and $($services.Count) app services"
Write-Host "  ================================================================"

Start-Process -FilePath (Join-Path $root "START_POSTGRES.bat")
Start-Sleep -Seconds 12

$number = 0
foreach ($service in $services) {
    $number++
    $batchPath = Join-Path $root $service.Batch
    Write-Host "  [$number/$($services.Count)] $($service.Name) (Port $($service.Port))..."
    Start-Process -FilePath $batchPath
    Start-Sleep -Seconds 3
}

$deadline = (Get-Date).AddSeconds(120)
do {
    $missing = @(
        $services | Where-Object {
            -not (Test-NetConnection 127.0.0.1 -Port $_.Port -InformationLevel Quiet -WarningAction SilentlyContinue)
        }
    )
    if ($missing.Count -eq 0) { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

Write-Host ""
if ($missing.Count -eq 0) {
    Write-Host "  All component ports are accepting connections." -ForegroundColor Green
} else {
    $missingPorts = ($missing | ForEach-Object { $_.Port }) -join ", "
    Write-Warning "Timed out waiting for ports: $missingPorts"
}

Write-Host ""
Write-Host "  Scheduling/Home : http://127.0.0.1:8000/home"
Write-Host "  Quality UI      : http://127.0.0.1:5173"
Write-Host "  Risk UI/Login   : http://127.0.0.1:5175/login"
Write-Host "  Team UI         : http://127.0.0.1:5174"
Write-Host ""
Write-Host "  Risk authentication is isolated to the Risk component."

Start-Process "http://127.0.0.1:8000/home"
Read-Host "  Press Enter to close this launcher window"
