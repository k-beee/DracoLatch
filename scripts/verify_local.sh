#!/bin/bash
set -e

echo "=== DracoLatch Local Verification Suite ==="
echo ""

echo "[1/4] Running unit and adversarial tests..."
python3 -m pytest -q -p no:cacheprovider tests/test_draco_latch.py
echo "✓ All Python unit & adversarial tests passed."
echo ""

echo "[2/4] Linting DracoLatch contract with genvm-linter..."
PYTHONIOENCODING=utf-8 python3 -m genvm_linter.cli check contracts/draco_latch.py
echo "✓ DracoLatch contract lint & validation passed."
echo ""

echo "[3/4] Linting DracoSourceProbe contract with genvm-linter..."
PYTHONIOENCODING=utf-8 python3 -m genvm_linter.cli check contracts/draco_source_probe.py
echo "✓ DracoSourceProbe contract lint & validation passed."
echo ""

if [ -d "frontend" ]; then
  echo "[4/4] Verifying frontend build..."
  cd frontend
  npm run build
  cd ..
  echo "✓ Frontend typecheck & Vite production build passed."
fi

echo ""
echo "=== DracoLatch: All Verification Checks Passed Successfully ==="
