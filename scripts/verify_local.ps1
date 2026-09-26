# DracoLatch Cross-Platform Local Verification Script (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=== DracoLatch Local Verification Suite (PowerShell) ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Running unit and adversarial tests..." -ForegroundColor Yellow
python -m pytest -q -p no:cacheprovider tests/test_draco_latch.py
Write-Host "✓ All Python unit & adversarial tests passed." -ForegroundColor Green
Write-Host ""

Write-Host "[2/4] Linting DracoLatch contract with genvm-linter..." -ForegroundColor Yellow
$env:PYTHONIOENCODING = "utf-8"
python -m genvm_linter.cli check contracts/draco_latch.py
Write-Host "✓ DracoLatch contract lint & validation passed." -ForegroundColor Green
Write-Host ""

Write-Host "[3/4] Linting DracoSourceProbe contract with genvm-linter..." -ForegroundColor Yellow
python -m genvm_linter.cli check contracts/draco_source_probe.py
Write-Host "✓ DracoSourceProbe contract lint & validation passed." -ForegroundColor Green
Write-Host ""

if (Test-Path "frontend") {
    Write-Host "[4/4] Verifying frontend build..." -ForegroundColor Yellow
    Push-Location frontend
    npm run build
    Pop-Location
    Write-Host "✓ Frontend typecheck & Vite production build passed." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== DracoLatch: All Verification Checks Passed Successfully ===" -ForegroundColor Cyan
