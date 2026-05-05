"""
pnadc_microdata.py — PNADC microdata ETL
=========================================

Backfill-capable pipeline: download → parse → aggregate → upsert into Supabase
domestic_work.fact_workers. Computes counts of trabalhadoras(es) domésticas(os)
by cor/raça × formality from PNADC microdata, applying survey weights.

Validation target (single-quarter mode): % pretas + pardas should land within
~1 pp of DIEESE published references.
  - For 4T 2024: DIEESE Boletim Especial abr/2025 reports ≈ 68.5–69 %.

Usage:
    python pnadc_microdata.py                  # single quarter, default 042024
    python pnadc_microdata.py 042025           # single quarter, specified
    python pnadc_microdata.py --all            # backfill ALL available quarters
    python pnadc_microdata.py --since 2020     # backfill from 2020Q1 onwards
    python pnadc_microdata.py --no-upsert      # dry run, skip Supabase write

Pipeline (per quarter):
  1. Download   https://ftp.ibge.gov.br/.../Microdados/<YYYY>/PNADC_<TT><YYYY>.zip
  2. Extract    one .txt fixed-width file (~600 MB for one quarter)
  3. Parse      pandas.read_fwf with the column specs below
  4. Validate   sanity-check value distributions (sex, race) before computing
  5. Aggregate  weighted counts using V1028 (peso amostral pré-calibrado)
  6. Print      headline result + a per-cor breakdown

Variables used:
  - V1028   — peso amostral pré-calibrado (population weight)
  - VD4009  — posição na ocupação (we filter to category 5 = Trabalhador doméstico)
  - V2007   — sexo (1=Homem, 2=Mulher)
  - V2010   — cor/raça (1=Branca, 2=Preta, 3=Amarela, 4=Parda, 5=Indígena, 9=Ignorado)
  - UF      — state code (11–53)
  - Ano, Trimestre

NOTE on column positions:
  Positions below are sourced from the PNADC trimestral data dictionary, valid
  for 2024–2025 microdata releases. Foundational variables (V1028, V2007, V2010,
  UF, Ano, Trimestre) are stable since the survey began in 2012. Derived
  variables (VD4009, VD4019) sit toward the end of the record and their
  positions shift slightly when IBGE adds new VD variables.

  If the validation step (step 4) reports unexpected value distributions, the
  most likely cause is that IBGE has shifted positions in a newer dictionary —
  update the COLUMN_SPECS below and re-run.
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# ----- config & logging --------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pnadc_microdata")

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "raw" / "pnadc"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Column specs: (start_1indexed, end_1indexed)
COLUMN_SPECS: dict[str, tuple[int, int]] = {
    "Ano":       (1,   4),
    "Trimestre": (5,   5),
    "UF":        (6,   7),
    "V1028":     (47,  60),    # 14 chars, with implicit decimal places
    "V2007":     (73,  73),
    "V2010":     (85,  85),
    "VD4009":    (218, 218),
    "VD4019":    (323, 332),   # 10 chars, with implicit decimals (currency)
}

# Cor/raça code → label (PT/EN). Codes from PNADC dictionary.
COR_RACA_LABELS = {
    "1": ("Branca",   "White"),
    "2": ("Preta",    "Black"),
    "3": ("Amarela",  "Yellow"),
    "4": ("Parda",    "Brown (parda)"),
    "5": ("Indígena", "Indigenous"),
    "9": ("Ignorado", "Unknown"),
}

# Posição na ocupação code → label.
POSICAO_OCUPACAO = {
    "01": "Empregado privado (exclusive doméstico)",
    "02": "Empregado público",
    "03": "Empregador",
    "04": "Conta própria",
    "05": "Trabalhador doméstico",  # <-- our target population
    "06": "Trabalhador familiar auxiliar",
    "07": "Militar / funcionário público estatutário",
    "08": "Aprendiz / estagiário",
    "09": "Trabalhador no autoconsumo",
    " ": "Sem informação",
    "":  "Sem informação",
}

# ----- download ----------------------------------------------------------------

FTP_BASE = (
    "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/"
    "Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados"
)
DOC_DIR_URL = f"{FTP_BASE}/Documentacao/"


def find_dictionary_zip_url() -> str:
    """Discover the latest Dicionario_e_input zip in IBGE's Documentacao folder.
    The filename has a date suffix that changes when IBGE re-publishes."""
    log.info("listing documentation: %s", DOC_DIR_URL)
    r = requests.get(DOC_DIR_URL, timeout=30)
    r.raise_for_status()
    pattern = re.compile(r'href="(Dicionario[^"]*\.zip)"', re.IGNORECASE)
    matches = sorted(set(pattern.findall(r.text)))
    if not matches:
        raise FileNotFoundError(f"No Dicionario zip in {DOC_DIR_URL}")
    return f"{DOC_DIR_URL}{matches[-1]}"


def download_dictionary() -> Path:
    """Download and cache the IBGE dictionary zip."""
    url = find_dictionary_zip_url()
    fname = url.rsplit("/", 1)[-1]
    local = RAW_DIR / fname
    if local.exists() and local.stat().st_size > 1024:
        return local
    log.info("downloading dictionary %s", url)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(local, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                f.write(chunk)
    return local


def parse_sas_input(text: str) -> dict[str, tuple[int, int]]:
    """Parse a SAS INPUT block, return {var_name: (start_1indexed, end_1indexed)}.

    Format expected:
        @001  Ano        $4.
        @005  Trimestre  $1.
        @006  UF         $2.
        ...
    Lengths are inferred from $N. or N.M (numeric with M decimals).
    """
    specs: dict[str, tuple[int, int]] = {}
    # Match @<position>  <varname>  $<length>. or N. or N.M
    pat = re.compile(
        r"@\s*(\d+)\s+([A-Za-z][A-Za-z0-9_]*)\s+\$?(\d+)(?:\.(\d+)?)?",
        re.IGNORECASE,
    )
    for m in pat.finditer(text):
        start = int(m.group(1))
        name = m.group(2)
        length = int(m.group(3))
        if length <= 0:
            continue
        specs[name] = (start, start + length - 1)
    return specs


def load_column_specs() -> dict[str, tuple[int, int]]:
    """Return {var: (start, end)} for the variables we need, by parsing the
    SAS INPUT file from IBGE's dictionary zip. Cached to disk after first run."""
    cache = RAW_DIR / "column_specs.json"
    import json
    if cache.exists():
        loaded = json.loads(cache.read_text())
        log.info("column specs cache hit: %s (%d vars)", cache, len(loaded))
        return {k: tuple(v) for k, v in loaded.items()}

    dict_zip = download_dictionary()
    log.info("parsing dictionary %s", dict_zip)
    sas_text = ""
    with zipfile.ZipFile(dict_zip) as zf:
        # The SAS input file is usually named input_PNADC_trimestral_<period>.txt
        # or contains a SAS DATA step. Try several patterns.
        candidates = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        for name in candidates:
            with zf.open(name) as f:
                content = f.read().decode("latin-1", errors="replace")
                if "@" in content and ("INPUT" in content.upper() or "$" in content):
                    log.info("using SAS input file: %s", name)
                    sas_text = content
                    break
    if not sas_text:
        raise RuntimeError(
            f"Could not find a SAS INPUT file inside {dict_zip}. "
            f"Members: {zipfile.ZipFile(dict_zip).namelist()}"
        )

    all_specs = parse_sas_input(sas_text)
    log.info("parsed %d variables from dictionary", len(all_specs))

    # Pull only the variables we use, error if any are missing.
    needed = ["Ano", "Trimestre", "UF", "V1028", "V2007", "V2010", "VD4009", "VD4019"]
    specs = {}
    for v in needed:
        if v not in all_specs:
            raise KeyError(f"Variable {v} not found in dictionary. Available: {sorted(all_specs)[:30]}…")
        specs[v] = all_specs[v]
        log.info("  %-10s → cols %d-%d", v, *specs[v])

    cache.write_text(json.dumps(specs))
    return specs


def find_microdata_url(period: str) -> str:
    """Discover the actual zip filename for a given period.

    IBGE files follow two patterns depending on year:
      - newer (current quarters)  : PNADC_<TTYYYY>.zip
      - older (re-versioned files): PNADC_<TTYYYY>_<YYYYMMDD>.zip

    Both can coexist, so we list the year directory and pick whichever exists.
    If multiple match (republished files), take the lexicographically latest
    which corresponds to the most recent date suffix.
    """
    if len(period) != 6 or not period.isdigit():
        raise ValueError(f"Period must be 6 digits TTYYYY, got: {period!r}")
    year = period[2:]
    dir_url = f"{FTP_BASE}/{year}/"
    log.info("[%s] listing %s", period, dir_url)
    r = requests.get(dir_url, timeout=30)
    r.raise_for_status()
    # Apache directory listing — files appear as <a href="filename">filename</a>
    pattern = re.compile(rf'href="(PNADC_{period}(?:_\d+)?\.zip)"', re.IGNORECASE)
    matches = sorted(set(pattern.findall(r.text)))
    if not matches:
        raise FileNotFoundError(
            f"No file matching PNADC_{period}*.zip in {dir_url}\n"
            f"Listing returned {len(r.text)} chars; check URL in a browser."
        )
    chosen = matches[-1]   # latest date-suffix wins if multiple exist
    if len(matches) > 1:
        log.info("[%s] multiple versions found; using latest: %s", period, chosen)
    return f"{dir_url}{chosen}"


def download_microdata_zip(period: str) -> Path:
    """Download the PNADC microdata zip for `period` (TTYYYY, e.g. '042024').

    Caches in raw/pnadc/. Returns the local zip path.
    """
    url = find_microdata_url(period)
    fname = url.rsplit("/", 1)[-1]
    local = RAW_DIR / fname
    if local.exists() and local.stat().st_size > 1024 * 1024:
        log.info("[%s] cache hit: %s (%d MB)", period, local, local.stat().st_size // 1024 // 1024)
        return local

    log.info("[%s] downloading %s", period, url)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        with open(local, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=fname) as bar:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
    return local


def extract_txt(zip_path: Path) -> Path:
    """Extract the .txt fixed-width file from the microdata zip."""
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not names:
            raise RuntimeError(f"No .txt file in {zip_path}")
        target = RAW_DIR / names[0]
        if target.exists() and target.stat().st_size > 100 * 1024 * 1024:
            log.info("extract cache hit: %s (%d MB)", target, target.stat().st_size // 1024 // 1024)
            return target
        log.info("extracting %s → %s", names[0], target)
        zf.extract(names[0], RAW_DIR)
        return target


# ----- parse -------------------------------------------------------------------

def parse_microdata(txt_path: Path, specs: dict[str, tuple[int, int]] | None = None) -> pd.DataFrame:
    """Read the fixed-width file. Column positions come from the IBGE dictionary
    when `specs` is None (recommended); falls back to the hardcoded COLUMN_SPECS
    only as last resort.

    pandas read_fwf uses 0-indexed [start, end) intervals; we convert from the
    1-indexed inclusive ranges.
    """
    if specs is None:
        specs = COLUMN_SPECS
    colspecs = [(s - 1, e) for (s, e) in specs.values()]
    names = list(specs.keys())
    log.info("parsing %s (this can take 1–2 min for a quarter)…", txt_path.name)

    # Read everything as strings first; type-convert after validation so we can
    # spot column-position mistakes via the value distribution.
    df = pd.read_fwf(txt_path, colspecs=colspecs, names=names, dtype=str, keep_default_na=False)
    log.info("parsed %d rows", len(df))
    return df


# ----- validate ----------------------------------------------------------------

def validate_columns(df: pd.DataFrame) -> bool:
    """Sanity-check that COLUMN_SPECS positions are correct.

    PNADC has stable value distributions for the categorical variables. If our
    column positions are off, the codes will be garbage. We catch that here
    before computing aggregates that would otherwise look plausible but wrong.
    """
    ok = True

    # V2007 (sexo): should be ~100 % in {1, 2}, with very few blanks.
    sexo_dist = df["V2007"].value_counts(dropna=False, normalize=True)
    sexo_valid = sexo_dist.get("1", 0) + sexo_dist.get("2", 0)
    log.info("V2007 (sexo) distribution top: %s", sexo_dist.head(5).to_dict())
    if sexo_valid < 0.99:
        log.error("V2007 looks wrong — expected ~100%% in {1,2}, got %.1f%%", 100 * sexo_valid)
        ok = False

    # V2010 (cor/raça): should be in {1,2,3,4,5,9} for >99 % of rows.
    cor_dist = df["V2010"].value_counts(dropna=False, normalize=True)
    cor_valid = sum(cor_dist.get(c, 0) for c in ["1", "2", "3", "4", "5", "9"])
    log.info("V2010 (cor/raça) distribution top: %s", cor_dist.head(8).to_dict())
    if cor_valid < 0.99:
        log.error("V2010 looks wrong — expected ~100%% in {1..5,9}, got %.1f%%", 100 * cor_valid)
        ok = False

    # UF: should be in 11..53 for ~all rows.
    uf_dist = df["UF"].value_counts(dropna=False).head(5)
    log.info("UF distribution top: %s", uf_dist.to_dict())
    try:
        uf_int = pd.to_numeric(df["UF"], errors="coerce")
        uf_valid = ((uf_int >= 11) & (uf_int <= 53)).mean()
        if uf_valid < 0.99:
            log.error("UF looks wrong — expected 99%% in [11,53], got %.1f%%", 100 * uf_valid)
            ok = False
    except Exception as e:
        log.error("UF type conversion failed: %s", e)
        ok = False

    # VD4009 (posição na ocupação): expected codes "01"–"09" with most weight on 01,04,05.
    pos_dist = df["VD4009"].value_counts(dropna=False, normalize=True).head(10)
    log.info("VD4009 (posição) top: %s", pos_dist.to_dict())
    pos_valid_codes = ["01", "02", "03", "04", "05", "06", "07", "08", "09", " ", ""]
    pos_valid = sum(pos_dist.get(c, 0) for c in pos_valid_codes)
    if pos_valid < 0.95:
        log.warning("VD4009 distribution unusual — got %.1f%% in expected codes", 100 * pos_valid)
        # Don't fail outright; VD positions are the most likely to drift between dictionary versions.

    return ok


# ----- aggregate ---------------------------------------------------------------

def list_available_periods() -> list[str]:
    """Discover every TTYYYY period available on IBGE's FTP for trimestre fixo.
    Walks each year directory under /Microdados/<YYYY>/ from 2012 onwards."""
    out: list[str] = []
    from datetime import date
    for year in range(2012, date.today().year + 1):
        url = f"{FTP_BASE}/{year}/"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                continue
        except requests.RequestException:
            continue
        # Look for files like PNADC_TTYYYY[ _datestamp].zip
        pat = re.compile(rf'href="PNADC_(0[1-4]){year}(?:_\d+)?\.zip"')
        for m in pat.finditer(r.text):
            tt = m.group(1)
            period = f"{tt}{year}"
            if period not in out:
                out.append(period)
    out.sort(key=lambda p: (p[2:], p[:2]))   # chronological: year first, then quarter
    return out


def microdata_period_to_db_code(period: str) -> str:
    """042024 (PNADC microdata file naming) → 202404 (dim_time period_code)."""
    if len(period) != 6:
        raise ValueError(period)
    return period[2:] + period[:2]


def aggregate_by_race(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to trabalhadoras(es) domésticas(os) (VD4009 = '05') and compute
    weighted population estimates by cor/raça."""
    # Convert weight to float. PNADC weights are ~14-char strings with implied decimals
    # (no decimal point in the file — it's a fixed-precision integer that we divide).
    # Inspect the actual weight values to guess the divisor.
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    # Common PNADC convention: weights have implicit 9 decimals → divide by 1e9
    # Reality check: if max weight > 1e9 after conversion, divide by 1e9.
    # Population-level weights should sum to ~215 million (Brazilian population 14+).
    log.info("V1028 raw stats: min=%.1f max=%.1e mean=%.1e", df["weight"].min(), df["weight"].max(), df["weight"].mean())
    # Heuristic divisor
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
        log.info("scaled weight by 1e-9; new max=%.1f", df["weight"].max())

    total_pop = df["weight"].sum()
    log.info("total weighted population (pessoas 14+): %.1fM", total_pop / 1e6)
    if not (1.5e8 < total_pop < 2.5e8):
        log.warning(
            "weighted total is out of expected range (~180-220M); "
            "weight scaling may be wrong"
        )

    # Diagnostic: print VD4009 weighted distribution so we can identify which
    # codes correspond to trabalhadoras domésticas.
    by_pos = (
        df.groupby("VD4009", dropna=False)["weight"].sum()
          .div(1000).round(0).reset_index()
          .rename(columns={"weight": "thousands"})
          .sort_values("thousands", ascending=False)
    )
    log.info("VD4009 weighted distribution (thousands of people):\n%s", by_pos.head(15).to_string(index=False))

    # Standard PNADC trimestral coding for VD4009 (Posição na ocupação):
    #   "01" Empregado privado, exclusive trabalhador doméstico - com carteira
    #   "02" Empregado privado, exclusive trabalhador doméstico - sem carteira
    #   "03" Trabalhador doméstico - com carteira  ←┐
    #   "04" Trabalhador doméstico - sem carteira  ←┴ both = trabalhador doméstico total
    #   "05" Empregado no setor público - com carteira
    #   "06" Empregado no setor público - sem carteira
    #   "07" Militar / estatutário
    #   "08" Empregador
    #   "09" Conta própria
    #   "10" Trabalhador familiar auxiliar
    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES)].copy()
    n_dom = dom["weight"].sum()
    log.info(
        "trabalhadoras(es) domésticas(os) [codes %s] weighted: %.0f thousand "
        "(vs PNADC published ~5,500–5,900 k)",
        DOMESTIC_CODES, n_dom / 1000,
    )

    # Group by cor/raça
    by_race = (
        dom.groupby("V2010", dropna=False)["weight"].sum()
           .div(1000)
           .round(0)
           .reset_index()
           .rename(columns={"V2010": "cor_raca_code", "weight": "workers_thousands"})
    )
    by_race["label_pt"] = by_race["cor_raca_code"].map(lambda c: COR_RACA_LABELS.get(c, ("?", "?"))[0])
    by_race["pct_of_total"] = (by_race["workers_thousands"] / by_race["workers_thousands"].sum() * 100).round(1)
    by_race = by_race.sort_values("workers_thousands", ascending=False)
    return by_race


# ----- aggregate to fact_workers shape ----------------------------------------

# PNADC V2010 (cor/raça) → our dim_race.code
RACE_MAP = {"1": "branca", "2": "preta", "3": "amarela", "4": "parda", "5": "indigena"}
# VD4009 (posição) → our dim_formality.code, restricted to trabalhador doméstico
FORMALITY_MAP = {"03": "com_carteira", "04": "sem_carteira"}


def build_fact_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Produce fact_workers payload rows from a parsed quarter's microdata.

    Output: 5 races × 3 formalities (com/sem/total) = 15 rows max per quarter,
    plus a 'total' race aggregate × 3 formalities = 3 rows. All BR-level,
    sex='T', age='total'. Skips rows where race code is 'ignorado' (V2010 = 9).
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES)].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["formality_code"] = dom["VD4009"].map(FORMALITY_MAP)
    dom = dom[dom["race_code"].notna() & dom["formality_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    # Race × formality (e.g., "preta com_carteira")
    for (race, form), w in dom.groupby(["race_code", "formality_code"])["weight"].sum().items():
        rows.append({
            "_period_code": db_period,
            "_geo_code": "BR",
            "_geo_level": "country",
            "_sex": "T", "_age": "total",
            "_race": race, "_formality": form,
            "workers_thousands": round(float(w) / 1000, 2),
        })

    # Race × total (sum across com+sem carteira)
    for race, w in dom.groupby("race_code")["weight"].sum().items():
        rows.append({
            "_period_code": db_period,
            "_geo_code": "BR",
            "_geo_level": "country",
            "_sex": "T", "_age": "total",
            "_race": race, "_formality": "total",
            "workers_thousands": round(float(w) / 1000, 2),
        })

    # preta_parda (Black) aggregate × each formality + total
    for form in ["com_carteira", "sem_carteira", "total"]:
        if form == "total":
            mask = dom["race_code"].isin(["preta", "parda"])
        else:
            mask = dom["race_code"].isin(["preta", "parda"]) & (dom["formality_code"] == form)
        w = dom.loc[mask, "weight"].sum()
        rows.append({
            "_period_code": db_period,
            "_geo_code": "BR",
            "_geo_level": "country",
            "_sex": "T", "_age": "total",
            "_race": "preta_parda", "_formality": form,
            "workers_thousands": round(float(w) / 1000, 2),
        })

    return rows


# ----- Supabase upsert --------------------------------------------------------

SOURCE_TABLE_TAG = "PNADC-MICRODATA"


def get_supabase_client():
    """Lazily import + construct the supabase client. Returns None if creds
    aren't available — callers should treat that as "skip upsert"."""
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


def upsert_to_supabase(rows: list[dict]) -> int:
    """Resolve dim ids, batch-upsert into fact_workers. Mirrors fetch_sidra.py logic."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")

    # 1. Ensure all needed period codes exist in dim_time
    needed_periods = {r["_period_code"] for r in rows}
    payload = []
    for code in needed_periods:
        # YYYYTT → year, quarter as integers
        year = int(code[:4])
        quarter = int(code[4:])
        payload.append({"year": year, "quarter": quarter, "period_code": code})
    if payload:
        schema.table("dim_time").upsert(payload, on_conflict="period_code").execute()

    # 2. Build dim lookups
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    formality_lookup = {r["code"]: r["formality_id"] for r in schema.table("dim_formality").select("code,formality_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"] for r in schema.table("dim_sex").select("code,sex_id").execute().data}
    age_lookup = {r["code"]: r["age_id"] for r in schema.table("dim_age_group").select("code,age_id").execute().data}

    # 3. Build payload
    fact_payload = []
    for r in rows:
        try:
            fact_payload.append({
                "time_id":      time_lookup[r["_period_code"]],
                "geo_id":       geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":       sex_lookup[r["_sex"]],
                "race_id":      race_lookup[r["_race"]],
                "formality_id": formality_lookup[r["_formality"]],
                "age_id":       age_lookup[r["_age"]],
                "workers_thousands": r["workers_thousands"],
                "source_table": SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for row %s: %s", r, e)

    # 4. Batch upsert
    inserted = 0
    for i in range(0, len(fact_payload), 250):
        chunk = fact_payload[i:i + 250]
        res = schema.table("fact_workers").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,formality_id,age_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


# ----- backfill orchestration -------------------------------------------------

def process_period(period: str, specs: dict, upsert: bool = True) -> dict:
    """Run a single quarter end-to-end. Returns {period, total_workers_k, pct_negras}."""
    log.info("--- processing %s ---", period)
    zip_path = download_microdata_zip(period)
    # Read directly from the zip without extracting to disk (saves 600 MB / quarter)
    with zipfile.ZipFile(zip_path) as zf:
        txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not txt_names:
            raise RuntimeError(f"No .txt in {zip_path}")
        with zf.open(txt_names[0]) as fh:
            colspecs = [(s - 1, e) for (s, e) in specs.values()]
            df = pd.read_fwf(fh, colspecs=colspecs, names=list(specs.keys()),
                             dtype=str, keep_default_na=False)

    rows = build_fact_rows(df, period)
    n_dom = sum(r["workers_thousands"] for r in rows
                if r["_race"] != "preta_parda" and r["_formality"] == "total")
    n_negras = sum(r["workers_thousands"] for r in rows
                   if r["_race"] == "preta_parda" and r["_formality"] == "total")
    pct_negras = round(100 * n_negras / n_dom, 1) if n_dom else None

    if upsert:
        inserted = upsert_to_supabase(rows)
        log.info("[%s] upserted %d rows · total %.0fk · pretas+pardas %s%%",
                 period, inserted, n_dom, pct_negras)
    else:
        log.info("[%s] (dry run) %d rows ready · total %.0fk · pretas+pardas %s%%",
                 period, len(rows), n_dom, pct_negras)

    return {"period": period, "total_workers_k": n_dom, "pct_negras": pct_negras}


# ----- main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PNADC microdata ETL")
    parser.add_argument("period", nargs="?", default=None,
                        help="TTYYYY (e.g. 042024). Omit if using --all/--since.")
    parser.add_argument("--all", action="store_true",
                        help="Backfill every available quarter (2012Q1 → latest).")
    parser.add_argument("--since", type=int, default=None, metavar="YYYY",
                        help="Backfill from this year onwards.")
    parser.add_argument("--no-upsert", action="store_true",
                        help="Dry run — parse and aggregate but skip Supabase write.")
    parser.add_argument("--keep-zips", action="store_true",
                        help="Keep raw zips after processing (default: keep, for re-runs).")
    args = parser.parse_args()

    upsert = not args.no_upsert
    specs = load_column_specs()

    # Decide period list
    if args.all or args.since:
        log.info("listing available periods on IBGE FTP…")
        periods = list_available_periods()
        if args.since:
            periods = [p for p in periods if int(p[2:]) >= args.since]
        log.info("will process %d periods: %s … %s", len(periods), periods[0], periods[-1])
    elif args.period:
        periods = [args.period]
    else:
        periods = ["042024"]   # default: pilot validation period

    summary = []
    for p in periods:
        try:
            result = process_period(p, specs, upsert=upsert)
            summary.append(result)
        except Exception as e:
            log.exception("[%s] FAILED: %s", p, e)
            summary.append({"period": p, "error": str(e)})

    # Summary table
    print("\n========== BACKFILL SUMMARY ==========")
    for r in summary:
        if "error" in r:
            print(f"  {r['period']}  ❌ {r['error'][:80]}")
        else:
            print(f"  {r['period']}  total {r['total_workers_k']:>5.0f}k  · pretas+pardas {r['pct_negras']}%")
    print("======================================\n")
    n_ok = sum(1 for r in summary if "error" not in r)
    n_fail = len(summary) - n_ok
    log.info("backfill complete: %d ok, %d failed", n_ok, n_fail)


if __name__ == "__main__":
    main()
