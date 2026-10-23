#!/usr/bin/env bash
# Generate the cohort, train the models, and write the evaluation report.
# Run this once before `docker compose up` or before starting the API directly.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Generating the synthetic cohort"
python data/generator/generate_cohort.py --quiet

echo "==> Training forecasters and the excursion classifier"
python -m ml.train

echo "==> Writing the evaluation report"
python scripts/write_evaluation_report.py

echo
echo "Done. Next:"
echo "  docker compose up --build        # full stack on :3000 and :8000"
echo "  uvicorn backend.app.main:app     # API only, SQLite fallback"
