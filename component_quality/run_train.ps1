# Run training script using available Python interpreter
# Usage: .\run_train.ps1 (run from repo root)

Push-Location $PSScriptRoot

# Prefer project venv
$venvPy = Join-Path -Path $PSScriptRoot -ChildPath "venv\Scripts\python.exe"
$systemPy = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source) -as [string]
$candidates = @($venvPy, $systemPy, 'C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe')

$found = $null
foreach ($p in $candidates) {
    if ([string]::IsNullOrEmpty($p)) { continue }
    if (Test-Path $p) { $found = $p; break }
}

if (-not $found) {
    Write-Host "No Python interpreter found. Install Python or activate your venv first." -ForegroundColor Red
    Write-Host "Fallback options: install Python and add to PATH, or provide full path to python.exe." -ForegroundColor Yellow
    Pop-Location
    exit 1
}

Write-Host "Using Python: $found" -ForegroundColor Green
& $found "scripts\train_baseline.py"

Pop-Location
