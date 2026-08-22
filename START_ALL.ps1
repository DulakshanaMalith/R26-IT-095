# ============================================================
# IPMS - Start All Services Launcher
# ============================================================

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "  ====================================================="
Write-Host "   IPMS - Integrated Project Management System"
Write-Host "   Starting All 6 Services..."
Write-Host "  ====================================================="
Write-Host ""

# ── SERVICE 1: Scheduling Backend (Port 8000) ─────────────────
Write-Host "  [1/6] Starting Scheduling Backend         (Port 8000)..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& { Set-Location '$root\component_scheduling'; Write-Host 'IPMS [1] Scheduling :8000' -ForegroundColor Cyan; python -m uvicorn main:app --host 127.0.0.1 --port 8000 }"
) -WindowStyle Normal

Write-Host "        Waiting 70 seconds for ML models to load..."
Start-Sleep -Seconds 70

# ── SERVICE 2: Quality Backend (Port 8001) ────────────────────
Write-Host "  [2/6] Starting Quality Assessment Backend  (Port 8001)..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& { Set-Location '$root\component_quality'; Write-Host 'IPMS [2] Quality Backend :8001' -ForegroundColor Green; python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8001 }"
) -WindowStyle Normal

Start-Sleep -Seconds 10

# ── SERVICE 3: Quality Frontend (Port 3000) ───────────────────
Write-Host "  [3/6] Starting Quality Assessment Frontend (Port 3000)..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& { Set-Location '$root\component_quality\frontend'; Write-Host 'IPMS [3] Quality Frontend :3000' -ForegroundColor Green; npm start }"
) -WindowStyle Normal

Start-Sleep -Seconds 5

# ── SERVICE 4: Risk Backend (Port 5000) ──────────────────────
Write-Host "  [4/6] Starting Risk Monitoring Backend     (Port 5000)..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& { Set-Location '$root\component_risk\ipms-risk-app'; Write-Host 'IPMS [4] Risk Monitor :5000' -ForegroundColor Yellow; python -m uvicorn main:app --host 127.0.0.1 --port 5000 }"
) -WindowStyle Normal

Start-Sleep -Seconds 5

# ── SERVICE 5: Team Backend (Port 8003) ──────────────────────
Write-Host "  [5/6] Starting Team Formation Backend      (Port 8003)..."
$teamBackendPath = "$root\component_team\intelligent-team-formation-and-topic-feasiblity-analyzis\backend-fastapi"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& { Set-Location '$teamBackendPath'; Write-Host 'IPMS [5] Team Backend :8003' -ForegroundColor Magenta; python -m uvicorn main:app --host 127.0.0.1 --port 8003 }"
) -WindowStyle Normal

Start-Sleep -Seconds 5

# ── SERVICE 6: Team Frontend (Port 3001) ─────────────────────
Write-Host "  [6/6] Starting Team Formation Frontend     (Port 3001)..."
$teamFrontendPath = "$root\component_team\intelligent-team-formation-and-topic-feasiblity-analyzis\frontend"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "& { Set-Location '$teamFrontendPath'; Write-Host 'IPMS [6] Team Frontend :3001' -ForegroundColor Magenta; npm run dev -- --port 3001 }"
) -WindowStyle Normal

Start-Sleep -Seconds 8

# ── Open Dashboards ───────────────────────────────────────────
Write-Host ""
Write-Host "  Opening dashboards in browser..."
Start-Process "http://127.0.0.1:8000/app"
Start-Sleep -Seconds 1
Start-Process "http://localhost:3000"
Start-Sleep -Seconds 1
Start-Process "http://127.0.0.1:3001"
Start-Sleep -Seconds 1
Start-Process "$root\index.html"

# ── Summary ───────────────────────────────────────────────────
Write-Host ""
Write-Host "  ====================================================="
Write-Host "   ALL SERVICES LAUNCHED SUCCESSFULLY" -ForegroundColor Green
Write-Host "  ====================================================="
Write-Host ""
Write-Host "   Service                   URL"
Write-Host "   -------------------------------------------------------"
Write-Host "   [1] Scheduling Backend    http://127.0.0.1:8000/app"
Write-Host "   [2] Quality Backend       http://127.0.0.1:8001/docs"
Write-Host "   [3] Quality Frontend      http://localhost:3000"
Write-Host "   [4] Risk Monitoring       http://127.0.0.1:5000"
Write-Host "   [5] Team Backend          http://127.0.0.1:8003/docs"
Write-Host "   [6] Team Frontend         http://127.0.0.1:3001"
Write-Host "   Master Dashboard          index.html (opened)"
Write-Host "   -------------------------------------------------------"
Write-Host ""
Read-Host "  Press Enter to close this launcher window"
