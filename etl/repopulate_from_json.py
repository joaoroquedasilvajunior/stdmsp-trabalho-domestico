"""
repopulate_from_json.py — Reload Supabase from the committed JSON exports
=========================================================================

WHY THIS EXISTS
---------------
On 2026-06-08 we discovered that Supabase project sceneqc had lost all
data during an extended free-tier pause (domestic_work schema dropped,
public emptied). The static-export migration of 2026-05-20 had already
made the dashboard immune to this — `dashboard/data/*.json` is committed
to git and IS the canonical record.

This script rebuilds Supabase from those JSON files. It is the inverse of
`export_static.py`. Run order:

    1. (Wake the Supabase project if paused)
    2. Apply DDL:           psql ... -f schema/002_recovery.sql
                            # or via the Supabase MCP apply_migration tool
    3. Run this script:     python etl/repopulate_from_json.py
    4. Verify counts:       python etl/export_static.py --check

If counts match manifest.json, the rebuild is complete and
`etl/refresh.sh` is operational again.

DESIGN NOTES
------------
- The committed JSON files are JOINED views — they carry codes (sex_code,
  race_code, ...) but not surrogate IDs. We re-derive the dimension rows
  from the codes/labels present in the JSON, insert dims first, then
  resolve codes → IDs when inserting facts.
- dim_age_group sort_order is not in the view, so we hardcode a small
  lookup. Same for the few code→label gaps.
- Idempotent: every insert uses upsert / ON CONFLICT DO NOTHING. Safe
  to re-run.
- No deletions. If the script is run against a populated schema it just
  fills gaps; it never truncates.
"""

from __future__ import annotations

import json
import logging
import os
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("repopulate")

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "dashboard" / "data"
CHUNK = 500  # rows per upsert call

# ------------------------------------------------------------------
# Hardcoded dim_age_group sort_order (the dw_workers view only carries
# the code, not the sort_order or labels)
# ------------------------------------------------------------------
AGE_LOOKUP = OrderedDict([
    # code,     (label_pt,        label_en,         sort_order)
    ("14-17",   ("14 a 17 anos",  "Ages 14–17",     1)),
    ("18-24",   ("18 a 24 anos",  "Ages 18–24",     2)),
    ("25-39",   ("25 a 39 anos",  "Ages 25–39",     3)),
    ("40-59",   ("40 a 59 anos",  "Ages 40–59",     4)),
    ("60+",     ("60 anos ou +",  "Ages 60+",       5)),
    ("total",   ("Total",         "Total",          99)),
])

# ------------------------------------------------------------------
# Connect
# ------------------------------------------------------------------

def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in etl/.env")
    return create_client(url, key)


def load_view(name: str) -> list[dict]:
    p = DATA_DIR / f"{name}.json"
    if not p.exists():
        log.warning("missing %s — skipping", p.name)
        return []
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------
# Derive dimensions from the joined view rows
# ------------------------------------------------------------------

def collect_dim_rows(workers: list[dict], wages: list[dict],
                    hours: list[dict], prev: list[dict]):
    times: dict[str, dict] = {}
    geos:  dict[tuple, dict] = {}
    sexes: dict[str, dict] = {}
    races: dict[str, dict] = {}
    forms: dict[str, dict] = {}
    ages:  dict[str, dict] = {}

    def take_time(r):
        pc = r.get("period_code")
        if not pc or pc in times:
            return
        times[pc] = {
            "period_code": pc,
            "year": r.get("year"),
            "quarter": r.get("quarter"),
        }

    def take_geo(r):
        level = r.get("geo_level")
        code = r.get("geo_code")
        if not level or not code or (level, code) in geos:
            return
        geos[(level, code)] = {
            "level": level,
            "code": code,
            "name_pt": r.get("geo_name_pt", code),
            "name_en": r.get("geo_name_en", code),
        }

    def take_sex(r):
        code = r.get("sex_code")
        if not code or code in sexes:
            return
        sexes[code] = {
            "code": code,
            "label_pt": r.get("sex_pt", code),
            "label_en": r.get("sex_en", code),
        }

    def take_race(r):
        code = r.get("race_code")
        if not code or code in races:
            return
        races[code] = {
            "code": code,
            "label_pt": r.get("race_pt", code),
            "label_en": r.get("race_en", code),
        }

    def take_form(r):
        code = r.get("formality_code")
        if not code or code in forms:
            return
        forms[code] = {
            "code": code,
            "label_pt": r.get("formality_pt", code),
            "label_en": r.get("formality_en", code),
        }

    def take_age(r):
        code = r.get("age_code")
        if not code or code in ages:
            return
        labels = AGE_LOOKUP.get(code, (code, code, 50))
        ages[code] = {
            "code": code,
            "label_pt": labels[0],
            "label_en": labels[1],
            "sort_order": labels[2],
        }

    for r in workers:
        take_time(r); take_geo(r); take_sex(r); take_race(r); take_form(r); take_age(r)
    for r in wages + hours + prev:
        take_time(r); take_geo(r); take_sex(r); take_race(r); take_form(r)

    return (list(times.values()), list(geos.values()),
            list(sexes.values()), list(races.values()),
            list(forms.values()), list(ages.values()))


# ------------------------------------------------------------------
# Insert dims, return code→id lookups
# ------------------------------------------------------------------

def upsert_dim(sb, table: str, rows: list[dict], conflict: str) -> int:
    if not rows:
        return 0
    schema = sb.schema("domestic_work")
    inserted = 0
    for i in range(0, len(rows), CHUNK):
        res = schema.table(table).upsert(rows[i:i+CHUNK], on_conflict=conflict).execute()
        inserted += len(res.data or [])
    return inserted


def lookup(sb, table: str, key_col: str, val_col: str = "code", id_col: str = None) -> dict:
    """Build a (code|key) → id map."""
    schema = sb.schema("domestic_work")
    id_col = id_col or table.replace("dim_", "") + "_id"
    rows = schema.table(table).select(f"{val_col},{id_col}").execute().data or []
    return {r[val_col]: r[id_col] for r in rows}


def lookup_geo(sb) -> dict:
    schema = sb.schema("domestic_work")
    rows = schema.table("dim_geo").select("level,code,geo_id").execute().data or []
    return {(r["level"], r["code"]): r["geo_id"] for r in rows}


# ------------------------------------------------------------------
# Insert facts
# ------------------------------------------------------------------

def resolve_workers(rows: list[dict], maps) -> list[dict]:
    t, g, s, ra, fo, ag = maps
    out = []
    for r in rows:
        try:
            out.append({
                "time_id":      t[r["period_code"]],
                "geo_id":       g[(r["geo_level"], r["geo_code"])],
                "sex_id":       s[r["sex_code"]],
                "race_id":      ra[r["race_code"]],
                "formality_id": fo[r["formality_code"]],
                "age_id":       ag[r["age_code"]],
                "workers_thousands": r.get("workers_thousands"),
                "n_unweighted":      r.get("n_unweighted"),
                "source_table":      r.get("source_table", "UNKNOWN"),
            })
        except KeyError as e:
            log.warning("skip workers row, missing %s", e)
    return out


def resolve_wages(rows, t, g, s, ra, fo):
    out = []
    for r in rows:
        try:
            out.append({
                "time_id":      t[r["period_code"]],
                "geo_id":       g[(r["geo_level"], r["geo_code"])],
                "sex_id":       s[r["sex_code"]],
                "race_id":      ra[r["race_code"]],
                "formality_id": fo[r["formality_code"]],
                "mean_wage_brl_real":   r.get("mean_wage_brl_real"),
                "median_wage_brl_real": r.get("median_wage_brl_real"),
                "n_unweighted":         r.get("n_unweighted"),
                "source_table":         r.get("source_table", "UNKNOWN"),
            })
        except KeyError as e:
            log.warning("skip wages row, missing %s", e)
    return out


def resolve_hours(rows, t, g, s, ra, fo):
    out = []
    for r in rows:
        try:
            out.append({
                "time_id":      t[r["period_code"]],
                "geo_id":       g[(r["geo_level"], r["geo_code"])],
                "sex_id":       s[r["sex_code"]],
                "race_id":      ra[r["race_code"]],
                "formality_id": fo[r["formality_code"]],
                "mean_hours_per_week": r.get("mean_hours_per_week"),
                "pct_over_44h":        r.get("pct_over_44h"),
                "n_unweighted":        r.get("n_unweighted"),
                "source_table":        r.get("source_table", "UNKNOWN"),
            })
        except KeyError as e:
            log.warning("skip hours row, missing %s", e)
    return out


def resolve_prev(rows, t, g, s, ra, fo):
    out = []
    for r in rows:
        try:
            out.append({
                "time_id":      t[r["period_code"]],
                "geo_id":       g[(r["geo_level"], r["geo_code"])],
                "sex_id":       s[r["sex_code"]],
                "race_id":      ra[r["race_code"]],
                "formality_id": fo[r["formality_code"]],
                "pct_with_prev": r.get("pct_with_prev"),
                "n_with_prev":   r.get("n_with_prev"),
                "n_unweighted":  r.get("n_unweighted"),
                "source_table":  r.get("source_table", "UNKNOWN"),
            })
        except KeyError as e:
            log.warning("skip prev row, missing %s", e)
    return out


def resolve_intl(rows: list[dict], t: dict) -> list[dict]:
    out = []
    for r in rows:
        try:
            out.append({
                "time_id":      t[r["period_code"]],
                "country_iso3": r.get("country_iso3"),
                "country_pt":   r.get("country_pt"),
                "country_en":   r.get("country_en"),
                "domestic_workers_thousands": r.get("domestic_workers_thousands"),
                "pct_of_employed_women":      r.get("pct_of_employed_women"),
                "pct_informal":               r.get("pct_informal"),
                "source":                     r.get("source", "ILOSTAT"),
            })
        except KeyError as e:
            log.warning("skip intl row, missing %s", e)
    return out


def upsert_chunked(sb, table: str, rows: list[dict], conflict: str) -> int:
    if not rows:
        return 0
    schema = sb.schema("domestic_work")
    inserted = 0
    for i in range(0, len(rows), CHUNK):
        res = schema.table(table).upsert(rows[i:i+CHUNK], on_conflict=conflict).execute()
        inserted += len(res.data or [])
    return inserted


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    sb = get_client()

    log.info("loading committed JSON exports from %s", DATA_DIR)
    workers = load_view("dw_workers")
    wages   = load_view("dw_wages")
    hours   = load_view("dw_hours")
    prev    = load_view("dw_prev")
    intl    = load_view("dw_intl")
    sources = load_view("dw_sources")
    static  = load_view("dw_static_facts")
    log.info("  loaded: %d workers, %d wages, %d hours, %d prev, %d intl, %d sources, %d static",
             len(workers), len(wages), len(hours), len(prev), len(intl), len(sources), len(static))

    # -------- dimensions
    log.info("deriving dimension rows from view JSON...")
    dim_times, dim_geos, dim_sexes, dim_races, dim_forms, dim_ages = \
        collect_dim_rows(workers, wages, hours, prev)
    log.info("  derived: %d times, %d geos, %d sexes, %d races, %d formality, %d ages",
             len(dim_times), len(dim_geos), len(dim_sexes), len(dim_races),
             len(dim_forms), len(dim_ages))

    log.info("upserting dimensions...")
    upsert_dim(sb, "dim_time",      dim_times, "period_code")
    upsert_dim(sb, "dim_geo",       dim_geos,  "level,code")
    upsert_dim(sb, "dim_sex",       dim_sexes, "code")
    upsert_dim(sb, "dim_race",      dim_races, "code")
    upsert_dim(sb, "dim_formality", dim_forms, "code")
    upsert_dim(sb, "dim_age_group", dim_ages,  "code")

    # -------- lookups
    log.info("building code→id lookups...")
    t  = lookup(sb, "dim_time", "period_code", "period_code", "time_id")
    g  = lookup_geo(sb)
    s  = lookup(sb, "dim_sex", "code")
    ra = lookup(sb, "dim_race", "code")
    fo = lookup(sb, "dim_formality", "code")
    ag = lookup(sb, "dim_age_group", "code")

    # -------- facts
    log.info("upserting facts...")
    fw = resolve_workers(workers, (t, g, s, ra, fo, ag))
    n = upsert_chunked(sb, "fact_workers", fw,
                       "time_id,geo_id,sex_id,race_id,formality_id,age_id,source_table")
    log.info("  fact_workers: %d/%d rows", n, len(fw))

    fwg = resolve_wages(wages, t, g, s, ra, fo)
    n = upsert_chunked(sb, "fact_wages", fwg,
                       "time_id,geo_id,sex_id,race_id,formality_id,source_table")
    log.info("  fact_wages:   %d/%d rows", n, len(fwg))

    fh = resolve_hours(hours, t, g, s, ra, fo)
    n = upsert_chunked(sb, "fact_hours", fh,
                       "time_id,geo_id,sex_id,race_id,formality_id,source_table")
    log.info("  fact_hours:   %d/%d rows", n, len(fh))

    fp = resolve_prev(prev, t, g, s, ra, fo)
    n = upsert_chunked(sb, "fact_prev", fp,
                       "time_id,geo_id,sex_id,race_id,formality_id,source_table")
    log.info("  fact_prev:    %d/%d rows", n, len(fp))

    fi = resolve_intl(intl, t)
    n = upsert_chunked(sb, "fact_intl", fi, "time_id,country_iso3,source")
    log.info("  fact_intl:    %d/%d rows", n, len(fi))

    # -------- data_source
    if sources:
        n = upsert_dim(sb, "data_source", sources, "short_code")
        log.info("  data_source:  %d rows", n)

    # -------- static_fact
    if static:
        # Strip out anything not in the table columns
        cleaned = [{k: v for k, v in r.items()
                    if k in {"fact_code", "value_num", "value_unit",
                             "label_pt", "label_en", "source_short",
                             "source_url", "source_date", "note_pt", "note_en"}}
                   for r in static]
        n = upsert_dim(sb, "static_fact", cleaned, "fact_code")
        log.info("  static_fact:  %d rows", n)

    log.info("rebuild complete — verify with: python etl/export_static.py --check")


if __name__ == "__main__":
    main()
