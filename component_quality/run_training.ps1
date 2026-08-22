# Enhanced ML Pipeline Training Script
# Installs dependencies and runs the training pipeline

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "ASAP 2.0 Enhanced ML Training Pipeline" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# Activate virtual environment if it exists
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "`n[INFO] Activating virtual environment..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1
} else {
    Write-Host "`n[WARNING] Virtual environment not found. Using system Python." -ForegroundColor Yellow
}

# Install/upgrade dependencies
Write-Host "`n[INFO] Installing/upgrading dependencies..." -ForegroundColor Yellow
pip install --upgrade pip --quiet
pip install xgboost>=2.0.0 --quiet
pip install sentence-transformers>=2.2.0 --quiet

# Run training script
Write-Host "`n[INFO] Starting training pipeline..." -ForegroundColor Yellow
python scripts/train_baseline.py

Write-Host "`n[INFO] Training complete!" -ForegroundColor Green
