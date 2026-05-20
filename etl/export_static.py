"""
export_static.py — Export dw_* views to static JSON for the dashboard
======================================================================

WHY THIS EXISTS
---------------
The dashboard reads read-only aggregate data that only changes when the
ETL runs (quarterly). Serving it from a live Supabase connection makes the
public site fragile: free-tier Supabase projects pause after inactivity,
and a paused project means a dead dashboard.

This script exports every `dw_*` view to `dashboard/data/*.json`. The
dashboard then reads those static files (same Cloudflare deploy as
index.html), making the public site fully static and immune to Supabase
availability. Supabase remains the ETL target and source of truth — it
just stops being a *runtime* dependency for the public site.

WHEN TO RUN
-----------
After every ETL refresh (quarterly), then commit the updated JSON:

    python etl/export_static.py
    git add dashboard/data/
    git commit -m "data: refresh static export YYYYqN"
    git push

USAGE
-----
    python etl/export_static.py            # export all views
    python etl/export_static.py --check    # report row counts without writing
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("export_static")

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "dashboard" / "data"

# The dashboard's seven data sources. All are views in the public schema.
VIEWS = [
    "dw_workers",
    "dw_wages",
    "dw_hours",
    "dw_prev",
    "dw_intl",
    "dw_sources",
    "dw_static_facts",
]

PAGE = 1000   # Supabase REST default max-rows cap


def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in etl/.env")
    return create_client(url, key)


def fetch_all(client, view: str) -> list[dict]:
    """Page through a view past the 1,000-row REST cap."""
    rows: list[dict] = []
    start = 0
    while True:
        resp = client.from_(view).select("*").range(start, start + PAGE - 1).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        start += PAGE
    return rows


def main():
    parser = argparse.ArgumentParser(description="Export dw_* views to static JSON")
    parser.add_argument("--check", action="store_true",
                        help="Report row counts without writing files")
    args = parser.parse_args()

    client = get_client()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "views": {},
    }
    total_bytes = 0

    for view in VIEWS:
        rows = fetch_all(client, view)
        manifest["views"][view] = len(rows)
        if args.check:
            log.info("  %-18s %6d rows  (check only, not written)", view, len(rows))
            continue
        out_path = OUT_DIR / f"{view}.json"
        # Compact JSON (no whitespace) — Cloudflare gzips on the wire anyway.
        payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=False)
        out_path.write_text(payload, encoding="utf-8")
        size_kb = out_path.stat().st_size / 1024
        total_bytes += out_path.stat().st_size
        log.info("  %-18s %6d rows  ->  %s (%.0f KB)", view, len(rows), out_path.name, size_kb)

    if args.check:
        log.info("check complete — no files written")
        return

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("wrote manifest.json — generated_at = %s", manifest["generated_at"])
    log.info("total payload: %.1f MB across %d views", total_bytes / 1024 / 1024, len(VIEWS))
    log.info("next: git add dashboard/data/ && git commit && git push")


if __name__ == "__main__":
    main()
