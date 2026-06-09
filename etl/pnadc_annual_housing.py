"""
pnadc_annual_housing.py — Housing tenure from PNADC ANNUAL (Visita 1)
=====================================================================

WHY THIS EXISTS
---------------
PNADC quarterly doesn't carry housing-condition variables. Those live in
PNADC ANNUAL (PNADC-A), released once a year by IBGE in two flavors —
"Trimestre" (quarterly-style annual) and "Visita" (visit-based panel).
Visit 1 carries the household-conditions block (S01001–S01031 series).

This script downloads PNADC-A Visita 1 microdata for a single year,
parses the fixed-width file, computes housing-tenure aggregates for
trabalhadoras(es) domésticas(os), and upserts into the same
`fact_housing` table the dashboard reads. Output rows are tagged
`source_table = 'PNADC-A'` and use period codes like `'2024A'` to
distinguish from quarterly facts.

USAGE
-----
    python etl/pnadc_annual_housing.py              # latest year, default 2024
    python etl/pnadc_annual_housing.py 2023         # specified year
    python etl/pnadc_annual_housing.py 2024 --no-upsert  # dry run

ARCHITECTURE
------------
- We hardcode column specs from the SAS input file (parsed by hand from
  the dictionary). This avoids the dictionary-parsing dance the
  quarterly script does — the annual file structure is stable across
  recent years and the housing-relevant subset is small.
- We download from IBGE FTP. Each annual zip is ~170 MB. We read the
  txt inside without extracting to disk.
- We reuse Supabase dimension lookups by inserting/finding the time_id
  for the annual period code first.
- We reuse `dim_housing` buckets (proprio / alugado / cedido_empregador
  / outro) and `HOUSING_TENURE_MAP` codes 1–7.

After this script runs, run `./etl/refresh.sh` to push the new rows
through to `dashboard/data/dw_housing.json`.
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pnadc_annual_housing")

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "raw" / "pnadc_annual"
RAW_DIR.mkdir(parents=True, exist_ok=True)

FTP_BASE = (
    "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/"
    "Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Anual/"
    "Microdados/Visita/Visita_1"
)
DATA_INDEX = f"{FTP_BASE}/Dados/"

# ---------------------------------------------------------------------------
# Column specs (1-indexed start/end inclusive, parsed by hand from the SAS
# input file at PNADC_2024_visita1_20251119). The PNADC-A layout is stable
# across recent years for the variables we use.
# ---------------------------------------------------------------------------
COLSPECS_1IDX = {
    "Ano":      (1, 4),
    "UF":       (6, 7),
    "V1032":    (58, 72),   # peso COM calibração — 15-char, 9 implicit decimals
    "V2007":    (94, 94),   # sexo
    "V2010":    (106, 106), # cor/raça
    "VD4009":   (540, 541), # posição na ocupação (2 chars in annual!)
    "S01017":   (491, 491), # Este domicílio é: (TENURE — our target)
}

# Reused buckets, mirroring etl/pnadc_microdata.py HOUSING_TENURE_MAP
# (cedido_empregador kept distinct for policy relevance)
HOUSING_TENURE_MAP = {
    "1": "proprio",            # Próprio - já pago
    "2": "proprio",            # Próprio - ainda pagando
    "3": "alugado",            # Alugado
    "4": "cedido_empregador",  # Cedido por empregador (live-in)
    "5": "outro",              # Cedido por familiar
    "6": "outro",              # Cedido de outra forma
    "7": "outro",              # Outra condição
}

RACE_MAP = {
    "1": "branca", "2": "preta", "3": "amarela",
    "4": "parda", "5": "indigena",
}

# Domestic worker codes in PNADC-A VD4009 (2-char form):
# "03" = com carteira, "04" = sem carteira. Same as quarterly.
DOMESTIC_CODES = ["03", "04"]

SOURCE_TABLE_TAG = "PNADC-A"

# ---------------------------------------------------------------------------
# Discovery: find the actual filename for a given year (the IBGE FTP appends
# an "_YYYYMMDD" suffix that varies per release).
# ---------------------------------------------------------------------------

def find_zip_url_for_year(year: int) -> str:
    """Scrape the FTP directory listing and pick the latest zip matching
    PNADC_<year>_visita1_*.zip."""
    log.info("looking up zip url for year %d at %s", year, DATA_INDEX)
    req = urllib.request.Request(DATA_INDEX, headers={"User-Agent": "stdmsp-etl/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("iso-8859-1", errors="replace")
    pattern = re.compile(
        rf"PNADC_{year}_visita1_(\d{{8}})\.zip",
        re.IGNORECASE,
    )
    matches = set(pattern.findall(html))
    if not matches:
        raise SystemExit(f"No PNADC_{year}_visita1_*.zip found at {DATA_INDEX}")
    latest = sorted(matches)[-1]
    url = f"{FTP_BASE}/Dados/PNADC_{year}_visita1_{latest}.zip"
    log.info("  -> %s", url)
    return url


# ---------------------------------------------------------------------------
# Download (cached on disk to avoid re-pulling 170 MB on every run)
# ---------------------------------------------------------------------------

def download_zip(url: str) -> Path:
    fname = url.rsplit("/", 1)[-1]
    out = RAW_DIR / fname
    if out.exists() and out.stat().st_size > 100_000_000:  # >100 MB sanity
        log.info("using cached %s (%.0f MB)", out.name, out.stat().st_size / 1e6)
        return out
    log.info("downloading %s ...", url)
    req = urllib.request.Request(url, headers={"User-Agent": "stdmsp-etl/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(out, "wb") as f:
        chunk_size = 1024 * 1024
        total = 0
        while True:
            chunk = r.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
            if total % (20 * chunk_size) == 0:
                log.info("  ... %d MB", total // (1024 * 1024))
    log.info("  done: %.0f MB", out.stat().st_size / 1e6)
    return out


# ---------------------------------------------------------------------------
# Read the inner txt straight from the zip
# ---------------------------------------------------------------------------

def read_microdata(zip_path: Path) -> pd.DataFrame:
    log.info("parsing %s ...", zip_path.name)
    with zipfile.ZipFile(zip_path) as zf:
        txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not txt_names:
            raise RuntimeError(f"No .txt in {zip_path}")
        with zf.open(txt_names[0]) as fh:
            # pandas wants 0-indexed half-open ranges
            colspecs = [(s - 1, e) for (s, e) in COLSPECS_1IDX.values()]
            df = pd.read_fwf(
                fh,
                colspecs=colspecs,
                names=list(COLSPECS_1IDX.keys()),
                dtype=str,
                keep_default_na=False,
            )
    log.info("  parsed %s rows × %s columns", f"{len(df):,}", len(df.columns))
    return df


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def build_housing_rows(df: pd.DataFrame, period_code: str) -> list[dict]:
    """Compute housing-tenure aggregates for trabalhadoras(es) domésticas(os).

    Emits the same row shape as the quarterly build_housing_rows in
    pnadc_microdata.py, so the upsert logic can reuse the same columns.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1032"], errors="coerce")
    # V1032 has 9 implicit decimals — same convention as V1028
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    # VD4009 in annual is 2 chars; pad/strip just in case
    df["VD4009"] = df["VD4009"].astype(str).str.strip().str.zfill(2)

    dom = df[df["VD4009"].isin(DOMESTIC_CODES) & df["weight"].notna()].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["s01017_raw"] = dom["S01017"].astype(str).str.strip()
    dom["housing_code"] = dom["s01017_raw"].map(HOUSING_TENURE_MAP)
    dom = dom[dom["race_code"].notna() & dom["housing_code"].notna()]

    log.info(
        "  filtered to %s domestic-worker rows with valid tenure & race",
        f"{len(dom):,}",
    )

    rows: list[dict] = []
    HOUSING_BUCKETS = ["proprio", "alugado", "cedido_empregador", "outro"]

    def _row(geo, level, sex, race, housing, w_sum, w_race_total, n):
        if w_sum is None or w_sum == 0:
            return None
        pct = round(100 * w_sum / w_race_total, 2) if w_race_total else None
        # Same divide-by-1000 convention as the rest of the pipeline.
        return {
            "_period_code": period_code,
            "_geo_code": geo,
            "_geo_level": level,
            "_sex": sex,
            "_race": race,
            "_housing": housing,
            "workers_thousands": round(float(w_sum) / 1000.0, 2),
            "pct_within_race": pct,
            "n_unweighted": int(n),
        }

    def emit_for_subset(geo_code: str, geo_level: str, race_label: str, subset: pd.DataFrame):
        total_w = subset["weight"].sum()
        for h in HOUSING_BUCKETS:
            g = subset[subset["housing_code"] == h]
            r = _row(geo_code, geo_level, "T", race_label, h,
                     g["weight"].sum(), total_w, len(g))
            if r:
                rows.append(r)
        r = _row(geo_code, geo_level, "T", race_label, "total",
                 total_w, total_w, len(subset))
        if r:
            rows.append(r)

    # ---- BR-level emissions (existing) ----
    for race, g in dom.groupby("race_code"):
        emit_for_subset("BR", "country", race, g)
    emit_for_subset("BR", "country", "preta_parda", dom[dom["race_code"].isin(["preta", "parda"])])
    emit_for_subset("BR", "country", "nao_negras", dom[dom["race_code"].isin(["branca", "amarela", "indigena"])])
    emit_for_subset("BR", "country", "total", dom)

    # ---- UF-level emissions (Theme 3: live-in geography) ----
    # IBGE 2-char UF codes — 27 federation units.
    UF_CODES = [
        "11", "12", "13", "14", "15", "16", "17",                  # Norte
        "21", "22", "23", "24", "25", "26", "27", "28", "29",      # Nordeste
        "31", "32", "33", "35",                                    # Sudeste
        "41", "42", "43",                                          # Sul
        "50", "51", "52", "53",                                    # Centro-Oeste
    ]
    SMALL_SAMPLE_THRESHOLD = 30  # skip UF × race cells with fewer unweighted obs
    dom["uf_code"] = dom["UF"].astype(str).str.zfill(2)

    for uf in UF_CODES:
        dom_uf = dom[dom["uf_code"] == uf]
        if len(dom_uf) < SMALL_SAMPLE_THRESHOLD:
            log.info("  skip UF %s — only %d unweighted obs", uf, len(dom_uf))
            continue
        # Race aggregates only at UF level — native races have too-small cells
        # in many UFs to be useful. preta_parda, nao_negras, total carry the
        # editorially relevant cuts (live-in by race within state).
        is_negra = dom_uf["race_code"].isin(["preta", "parda"])
        is_nao_negra = dom_uf["race_code"].isin(["branca", "amarela", "indigena"])
        if len(dom_uf[is_negra]) >= SMALL_SAMPLE_THRESHOLD:
            emit_for_subset(uf, "uf", "preta_parda", dom_uf[is_negra])
        if len(dom_uf[is_nao_negra]) >= SMALL_SAMPLE_THRESHOLD:
            emit_for_subset(uf, "uf", "nao_negras", dom_uf[is_nao_negra])
        emit_for_subset(uf, "uf", "total", dom_uf)

    log.info("  produced %d aggregate rows", len(rows))
    return rows


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.warning("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set; running in --no-upsert mode")
        return None
    try:
        from supabase import create_client
    except ImportError:
        log.error("supabase-py not installed. Run: pip install supabase")
        return None
    return create_client(url, key)


def ensure_annual_time_id(sb, year: int, period_code: str) -> int:
    """Insert (or find) the dim_time row for an annual period.
    Returns the time_id for upserts."""
    schema = sb.schema("domestic_work")
    existing = schema.table("dim_time").select("time_id,period_code") \
        .eq("period_code", period_code).execute()
    if existing.data:
        return existing.data[0]["time_id"]
    res = schema.table("dim_time").insert({
        "year": year,
        "quarter": None,
        "period_code": period_code,
    }).execute()
    return res.data[0]["time_id"]


def upsert_to_supabase(rows: list[dict], year: int, period_code: str) -> int:
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    ensure_annual_time_id(sb, year, period_code)

    time_lookup = {
        r["period_code"]: r["time_id"]
        for r in schema.table("dim_time").select("period_code,time_id").execute().data
    }
    geo_lookup = {
        (r["level"], r["code"]): r["geo_id"]
        for r in schema.table("dim_geo").select("level,code,geo_id").execute().data
    }
    race_lookup = {r["code"]: r["race_id"]
                   for r in schema.table("dim_race").select("code,race_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"]
                  for r in schema.table("dim_sex").select("code,sex_id").execute().data}
    housing_lookup = {r["code"]: r["housing_id"]
                      for r in schema.table("dim_housing").select("code,housing_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":    time_lookup[r["_period_code"]],
                "geo_id":     geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":     sex_lookup[r["_sex"]],
                "race_id":    race_lookup[r["_race"]],
                "housing_id": housing_lookup[r["_housing"]],
                "workers_thousands": r["workers_thousands"],
                "pct_within_race":   r["pct_within_race"],
                "n_unweighted":      r["n_unweighted"],
                "source_table":      SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for housing row %s: %s", r, e)

    inserted = 0
    CHUNK = 250
    for i in range(0, len(payload), CHUNK):
        chunk = payload[i:i + CHUNK]
        res = schema.table("fact_housing").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,housing_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PNADC Annual Visita 1 — housing tenure ETL")
    parser.add_argument("year", type=int, nargs="?", default=2024,
                        help="Base year (default 2024 — latest available as of mid-2026)")
    parser.add_argument("--no-upsert", action="store_true",
                        help="Dry run; print results without writing to Supabase")
    args = parser.parse_args()

    url = find_zip_url_for_year(args.year)
    zip_path = download_zip(url)
    df = read_microdata(zip_path)

    period_code = f"{args.year}A"
    rows = build_housing_rows(df, period_code)

    # Diagnostic: % próprio and % live-in for the category overall
    total_proprio = next((r for r in rows
                          if r["_race"] == "total" and r["_housing"] == "proprio"), None)
    pct_proprio = total_proprio["pct_within_race"] if total_proprio else None
    total_livein = next((r for r in rows
                         if r["_race"] == "total" and r["_housing"] == "cedido_empregador"), None)
    pct_livein = total_livein["pct_within_race"] if total_livein else None

    if args.no_upsert:
        log.info("[%s] (dry run) %d rows · %% próprio %s%% · %% live-in %s%%",
                 period_code, len(rows), pct_proprio, pct_livein)
        return

    inserted = upsert_to_supabase(rows, args.year, period_code)
    log.info("[%s] upserted %d housing rows · %% próprio %s%% · %% live-in %s%%",
             period_code, inserted, pct_proprio, pct_livein)
    log.info("next: ./etl/refresh.sh && git add dashboard/data/ && commit")


if __name__ == "__main__":
    main()
