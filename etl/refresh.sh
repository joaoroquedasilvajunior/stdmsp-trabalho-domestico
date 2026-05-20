#!/usr/bin/env bash
#
# refresh.sh — post-ETL data refresh for the static dashboard
# ============================================================
#
# The dashboard is a STATIC site: it reads dashboard/data/*.json, not a live
# Supabase connection. After the ETL writes new data to Supabase, those JSON
# files must be regenerated and committed — otherwise the dashboard silently
# serves stale data.
#
# This script automates the deterministic post-ETL steps so the export can't
# be forgotten. It does NOT run the ETL itself (that step varies — which
# quarter, which sources — and the PNADC backfill can take hours).
#
# FULL QUARTERLY REFRESH FLOW
# ---------------------------
#   1. Run the ETL (you decide which):
#        python etl/fetch_sidra.py
#        python etl/pnadc_microdata.py 0X2026     # the new quarter
#        python etl/fetch_ilostat.py
#   2. Run THIS script:   ./etl/refresh.sh
#   3. Review, then commit + push (the script prints the exact commands)
#
# USAGE
#   ./etl/refresh.sh            # export + stage, then print commit/push commands
#
set -euo pipefail

# Resolve repo root (this script lives in etl/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Activate the ETL venv if it isn't already active
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -f etl/.venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source etl/.venv/bin/activate
    echo "→ activated etl/.venv"
  else
    echo "WARNING: etl/.venv not found — assuming dependencies are on PATH" >&2
  fi
fi

echo "→ exporting dw_* views to dashboard/data/ ..."
python etl/export_static.py

echo
echo "→ staging dashboard/data/ ..."
git add dashboard/data/

echo
echo "── staged changes ──────────────────────────────────────────"
git status --short dashboard/data/ || true
echo "────────────────────────────────────────────────────────────"
echo
echo "Static export done. To finish the refresh, review the above, then run:"
echo
echo "    git commit -m \"data: refresh static export <YYYYqN>\""
echo "    git push origin main"
echo
echo "Cloudflare Pages auto-deploys on push. The dashboard's \"data updated"
echo "on\" line will reflect the new export timestamp once deployed."
