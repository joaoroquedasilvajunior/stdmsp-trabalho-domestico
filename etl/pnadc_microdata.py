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


# Variables we extract from the PNADC microdata. The dictionary parser
# discovers byte positions automatically; we just list what to keep.
#
#   V4032  — was a contributor to social security (previdência) in the
#            reference week. Binary 1=Sim, 2=Não. Used for retirement-
#            rights aggregation.
#   V4039  — hours habitually worked per week in main job. Numeric, 0–98.
#            Used for jornada média and % over the 44h legal weekly limit.
NEEDED_VARS = [
    "Ano", "Trimestre", "UF",
    "V1028",   # population weight
    "V2003",   # condição no domicílio (D2 — family / household position)
    "V2007",   # sex
    "V2009",   # idade na data de referência (Theme 2 — age cohorts)
    "V2010",   # cor/raça
    "V4010",   # CBO-Domiciliar 4-digit — MEI proxy CBO bucketing
    "V4012",   # posição raw (before VD4009 derivation) — sanity for autonomous subset
    "V4019",   # CNPJ? 1=Sim 2=Não — MEI proxy variable (asked only to VD4009 ∈ 08,09)
    "V4024",   # serviço doméstico em mais de 1 domicílio — mensalista (2) / diarista (1)
    "V4032",   # previdência contributor (1/2)
    "V4039",   # weekly hours (main job)
    "VD3004",  # nível de instrução mais elevado alcançado (D1 — education)
    "VD4009",  # posição na ocupação
    "VD4019",  # rendimento mensal habitual
    # NOTE: V0212 (housing tenure) is NOT in the PNADC quarterly dictionary —
    # it lives in PNADC ANNUAL. The D3 housing pipeline runs separately via
    # etl/pnadc_annual_housing.py and populates the same fact_housing table.
]


def load_column_specs() -> dict[str, tuple[int, int]]:
    """Return {var: (start, end)} for the variables we need, by parsing the
    SAS INPUT file from IBGE's dictionary zip. Cached to disk after first run.

    The cache is invalidated automatically if NEEDED_VARS has grown since the
    last run — so adding new variables here doesn't require manually deleting
    the cache file.
    """
    cache = RAW_DIR / "column_specs.json"
    import json
    if cache.exists():
        loaded = json.loads(cache.read_text())
        if all(v in loaded for v in NEEDED_VARS):
            log.info("column specs cache hit: %s (%d vars)", cache, len(loaded))
            return {k: tuple(v) for k, v in loaded.items()}
        else:
            missing = [v for v in NEEDED_VARS if v not in loaded]
            log.info("column specs cache missing %s; re-parsing dictionary", missing)

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
    specs = {}
    for v in NEEDED_VARS:
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

# VD3004 (highest education level reached). PNADC native codes 1-7 collapsed into
# 5 buckets aligned with DIEESE reporting conventions. "sem instrução" (code 1)
# is grouped with "fundamental incompleto" (code 2) — matches DIEESE Infográfico.
EDUCATION_MAP = {
    "1": "fund_inc",   # Sem instrução / < 1 ano
    "2": "fund_inc",   # Fundamental incompleto
    "3": "fund_comp",  # Fundamental completo
    "4": "med_inc",    # Médio incompleto
    "5": "med_comp",   # Médio completo
    "6": "sup",        # Superior incompleto
    "7": "sup",        # Superior completo
}

# V2003 (condição no domicílio). PNADC native codes 01-17 collapsed into
# 4 buckets to surface the family-position story cleanly. "chefe de família"
# is the DIEESE-headline number (Infográfico abr/2026: 46% para trabalhadoras
# domésticas vs 58% para mulheres ocupadas em geral).
FAMILY_POSITION_MAP = {
    "01": "chefe",     # Pessoa responsável
    "02": "conjuge",   # Cônjuge / companheiro(a)
    "03": "filha",     # Filha(o)
    "04": "filha",     # Enteada(o)
    "05": "outro",     # Genro / nora
    "06": "outro",     # Pai/mãe / padrasto/madrasta
    "07": "outro",     # Sogro(a)
    "08": "outro",     # Neto(a)
    "09": "outro",     # Bisneto(a)
    "10": "outro",     # Irmão / irmã
    "11": "outro",     # Outro parente
    "12": "outro",     # Agregado(a)
    "13": "outro",     # Convivente
    "14": "outro",     # Pensionista
    "15": "outro",     # Empregado(a) doméstico(a) residente
    "16": "outro",     # Parente do empregado doméstico
    "17": "outro",     # Individual em domicílio coletivo
}

# V0212 (forma de habitação — tenure). PNADC native codes 1-7 collapsed
# into 4 buckets. The "cedido por empregador" case (code 4) is kept distinct
# because it identifies live-in domestic workers (empregadas residentes),
# a historically vulnerable sub-category worth surfacing separately.
HOUSING_TENURE_MAP = {
    "1": "proprio",            # Próprio - já pago
    "2": "proprio",            # Próprio - ainda pagando
    "3": "alugado",            # Alugado
    "4": "cedido_empregador",  # Cedido por empregador (live-in)
    "5": "outro",              # Cedido por familiar
    "6": "outro",              # Cedido de outra forma
    "7": "outro",              # Outra condição
}

# V2009 (idade) bucketed to match the DIEESE Apr/2026 Infográfico table.
# Returns a string code aligned with dim_age_band, or None for invalid ages.
def age_to_band(age: int) -> str | None:
    if age is None or age < 0 or age > 130:
        return None
    if age < 30:
        return "under_29"
    if age < 45:
        return "30_44"
    if age < 60:
        return "45_59"
    return "60_plus"


# V4024 — "Serviço doméstico em mais de 1 domicílio". The standard PNADC
# operational definition of mensalista vs diarista. Used by Mayer's DiD
# hypothesis to test whether the 2017 Labor Reform accelerated the
# mensalista → diarista shift differentially by race.
#   1 = sim (multiple homes) → diarista
#   2 = não (single home)    → mensalista
CONTRACT_MAP = {
    "1": "diarista",
    "2": "mensalista",
}
# PNADC V2007 (sexo) → our dim_sex.code
SEX_MAP = {"1": "M", "2": "F"}
# VD4009 (posição) → our dim_formality.code, restricted to trabalhador doméstico
FORMALITY_MAP = {"03": "com_carteira", "04": "sem_carteira"}

# PNADC UF (numeric IBGE code, 2-digit zero-padded) → sigla. Used for sanity
# logs only; the database stores the numeric codes since dim_geo.code matches
# what fetch_sidra.py inserts (uf rows zfill(2) the SIDRA numeric code).
UF_CODE_TO_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE",
    "27": "AL", "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


def build_fact_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Produce fact_workers payload rows from a parsed quarter's microdata.

    Output: 5 races × 3 formalities (com/sem/total) = 15 rows max per quarter,
    plus a 'total' race aggregate × 3 formalities = 3 rows. All BR-level,
    sex='T', age='total'. Skips rows where race code is 'ignorado' (V2010 = 9).

    Each row carries n_unweighted (unweighted sample count) for CI calculations.
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
    for (race, form), g in dom.groupby(["race_code", "formality_code"]):
        rows.append({
            "_period_code": db_period,
            "_geo_code": "BR", "_geo_level": "country",
            "_sex": "T", "_age": "total",
            "_race": race, "_formality": form,
            "workers_thousands": round(float(g["weight"].sum()) / 1000, 2),
            "n_unweighted": int(len(g)),
        })

    # Race × total (sum across com+sem carteira)
    for race, g in dom.groupby("race_code"):
        rows.append({
            "_period_code": db_period,
            "_geo_code": "BR", "_geo_level": "country",
            "_sex": "T", "_age": "total",
            "_race": race, "_formality": "total",
            "workers_thousands": round(float(g["weight"].sum()) / 1000, 2),
            "n_unweighted": int(len(g)),
        })

    # preta_parda (Black) aggregate × each formality + total
    is_negra_br = dom["race_code"].isin(["preta", "parda"])
    for form in ["com_carteira", "sem_carteira", "total"]:
        mask = is_negra_br if form == "total" else is_negra_br & (dom["formality_code"] == form)
        g = dom[mask]
        rows.append({
            "_period_code": db_period,
            "_geo_code": "BR", "_geo_level": "country",
            "_sex": "T", "_age": "total",
            "_race": "preta_parda", "_formality": form,
            "workers_thousands": round(float(g["weight"].sum()) / 1000, 2),
            "n_unweighted": int(len(g)),
        })

    return rows


def build_sex_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Produce fact_workers payload rows for sex × formality aggregations.

    Output: 2 sexes × 3 formalities (com_carteira, sem_carteira, total) = 6 rows
    per quarter. race_code = 'total', age_code = 'total' on these rows.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES)].copy()
    dom["sex_code"] = dom["V2007"].map(SEX_MAP)
    dom["formality_code"] = dom["VD4009"].map(FORMALITY_MAP)
    dom = dom[dom["sex_code"].notna() & dom["formality_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    # Sex × formality
    for (sex, form), g in dom.groupby(["sex_code", "formality_code"]):
        rows.append({
            "_period_code": db_period,
            "_geo_code": "BR", "_geo_level": "country",
            "_sex": sex, "_race": "total", "_formality": form, "_age": "total",
            "workers_thousands": round(float(g["weight"].sum()) / 1000, 2),
            "n_unweighted": int(len(g)),
        })

    # Sex × total (sum across formalities)
    for sex, g in dom.groupby("sex_code"):
        rows.append({
            "_period_code": db_period,
            "_geo_code": "BR", "_geo_level": "country",
            "_sex": sex, "_race": "total", "_formality": "total", "_age": "total",
            "workers_thousands": round(float(g["weight"].sum()) / 1000, 2),
            "n_unweighted": int(len(g)),
        })

    return rows


def build_uf_race_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Produce fact_workers payload rows for race × UF aggregations.

    Two cuts emitted:

    (A) formality='total' (legacy, for race composition by UF):
      - 5 race rows × 27 UFs = 135
      - preta_parda × 27 UFs = 27
      - nao_negras × 27 UFs = 27
      - race='total' × 27 UFs = 27

    (B) formality='com_carteira' and 'sem_carteira' (added for Theme 4 —
        compliance geography):
      - preta_parda × com/sem × 27 UFs = 54
      - nao_negras × com/sem × 27 UFs = 54
      - race='total' × com/sem × 27 UFs = 54

    Total: ~378 rows per quarter; ~21k rows across the 56-quarter backfill.

    All rows have sex='T', age='total'. Skips rows with race='ignorado'.

    Caveats for downstream consumers:
      - Small UFs (RR, AP, AC, TO) have noisy estimates for rare race cells.
      - For Theme 4 specifically, downstream code should apply a small-sample
        floor (e.g., n_unweighted >= 30 within race='total' for the UF) before
        showing UF-level formalization rates.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES)].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["formality_code"] = dom["VD4009"].map(FORMALITY_MAP)
    dom["uf_code"] = dom["UF"].astype(str).str.zfill(2)
    dom = dom[dom["race_code"].notna() & dom["uf_code"].isin(UF_CODE_TO_SIGLA)
              & dom["formality_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    def _row(uf, race, formality, group):
        return {
            "_period_code": db_period,
            "_geo_code": uf, "_geo_level": "uf",
            "_sex": "T", "_age": "total",
            "_race": race, "_formality": formality,
            "workers_thousands": round(float(group["weight"].sum()) / 1000, 2),
            "n_unweighted": int(len(group)),
        }

    # --- (A) formality='total' rows (legacy: race composition by UF) ---

    for (uf, race), g in dom.groupby(["uf_code", "race_code"]):
        rows.append(_row(uf, race, "total", g))

    is_negra = dom["race_code"].isin(["preta", "parda"])
    for uf, g in dom[is_negra].groupby("uf_code"):
        rows.append(_row(uf, "preta_parda", "total", g))

    is_nao_negra = dom["race_code"].isin(["branca", "amarela", "indigena"])
    for uf, g in dom[is_nao_negra].groupby("uf_code"):
        rows.append(_row(uf, "nao_negras", "total", g))

    for uf, g in dom.groupby("uf_code"):
        rows.append(_row(uf, "total", "total", g))

    # --- (B) formality='com_carteira' / 'sem_carteira' rows (Theme 4) ---
    # Emit per-formality within aggregate race tracks (preta_parda, nao_negras,
    # total). The 5 native races are NOT emitted at per-formality granularity
    # because their cells become very small in many UFs (e.g., amarela in
    # Roraima); downstream Wilson CIs would be uninformative.

    for (uf, form), g in dom[is_negra].groupby(["uf_code", "formality_code"]):
        rows.append(_row(uf, "preta_parda", form, g))

    for (uf, form), g in dom[is_nao_negra].groupby(["uf_code", "formality_code"]):
        rows.append(_row(uf, "nao_negras", form, g))

    for (uf, form), g in dom.groupby(["uf_code", "formality_code"]):
        rows.append(_row(uf, "total", form, g))

    return rows


def build_hours_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Aggregate weekly hours (V4039) for trabalhadoras(es) domésticas(os).

    Emits weighted mean hours + % over 44h + unweighted sample size for:
      - BR × sex × race × formality (5 races × 2 sex × 2 form = 20)
      - BR × race × total formality at sex='T' (5 races × 3 form = 15)
      - BR × preta_parda × each formality at sex='T' (3)
      - BR × nao_negras × each formality at sex='T' (3)
      - UF × race × formality_total at sex='T' (5 × 27 = 135)
      - UF × preta_parda × formality_total (27)
      - UF × nao_negras × formality_total (27)
      - UF × race='total' × formality_total (27)

    Total: ~260 rows per quarter; ~15k rows over the 56-quarter backfill.

    Drops rows where V4039 is null/zero (i.e., people who didn't work in the
    reference week or whose hours weren't recorded). Skips race='ignorado'.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
    df["hours"] = pd.to_numeric(df["V4039"], errors="coerce")

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES)
             & df["hours"].notna()
             & (df["hours"] > 0)
             & (df["hours"] <= 98)].copy()  # 98 is PNADC's max-hours sentinel
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["sex_code"] = dom["V2007"].map(SEX_MAP)
    dom["formality_code"] = dom["VD4009"].map(FORMALITY_MAP)
    dom["uf_code"] = dom["UF"].astype(str).str.zfill(2)
    dom = dom[dom["race_code"].notna() & dom["sex_code"].notna() & dom["formality_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    def _agg(group):
        w = group["weight"]; h = group["hours"]
        if w.sum() == 0:
            return None
        return {
            "mean_hours_per_week": round(float((h * w).sum() / w.sum()), 2),
            "pct_over_44h": round(100 * float(((h > 44) * w).sum() / w.sum()), 2),
            "n_unweighted": int(len(group)),
        }

    def _row(uf, level, sex, race, form, agg):
        if agg is None:
            return None
        return {
            "_period_code": db_period,
            "_geo_code": uf, "_geo_level": level,
            "_sex": sex, "_race": race, "_formality": form,
            **agg,
        }

    # BR × sex × race × formality (com/sem)
    for (sex, race, form), g in dom.groupby(["sex_code", "race_code", "formality_code"]):
        r = _row("BR", "country", sex, race, form, _agg(g))
        if r: rows.append(r)

    # BR × race × total formality at sex='T'
    for race, g in dom.groupby("race_code"):
        r = _row("BR", "country", "T", race, "total", _agg(g))
        if r: rows.append(r)

    # BR × race × each formality at sex='T'
    for (race, form), g in dom.groupby(["race_code", "formality_code"]):
        r = _row("BR", "country", "T", race, form, _agg(g))
        if r: rows.append(r)

    # BR × preta_parda aggregate at sex='T' × each formality + total
    is_negra = dom["race_code"].isin(["preta", "parda"])
    for form_code in ["com_carteira", "sem_carteira", "total"]:
        mask = is_negra if form_code == "total" else is_negra & (dom["formality_code"] == form_code)
        g = dom[mask]
        if len(g):
            r = _row("BR", "country", "T", "preta_parda", form_code, _agg(g))
            if r: rows.append(r)

    # BR × nao_negras aggregate at sex='T' × each formality + total
    is_nao_negra = dom["race_code"].isin(["branca", "amarela", "indigena"])
    for form_code in ["com_carteira", "sem_carteira", "total"]:
        mask = is_nao_negra if form_code == "total" else is_nao_negra & (dom["formality_code"] == form_code)
        g = dom[mask]
        if len(g):
            r = _row("BR", "country", "T", "nao_negras", form_code, _agg(g))
            if r: rows.append(r)

    # BR × race='total' at sex='T' × total formality (overall mean for BR)
    r = _row("BR", "country", "T", "total", "total", _agg(dom))
    if r: rows.append(r)

    # UF × race × formality='total' at sex='T'
    uf_codes_valid = dom["uf_code"].isin(UF_CODE_TO_SIGLA)
    dom_uf = dom[uf_codes_valid]
    for (uf, race), g in dom_uf.groupby(["uf_code", "race_code"]):
        r = _row(uf, "uf", "T", race, "total", _agg(g))
        if r: rows.append(r)

    # UF × preta_parda × formality='total' at sex='T'
    is_negra_uf = dom_uf["race_code"].isin(["preta", "parda"])
    for uf, g in dom_uf[is_negra_uf].groupby("uf_code"):
        r = _row(uf, "uf", "T", "preta_parda", "total", _agg(g))
        if r: rows.append(r)

    # UF × nao_negras × formality='total' at sex='T'
    is_nao_negra_uf = dom_uf["race_code"].isin(["branca", "amarela", "indigena"])
    for uf, g in dom_uf[is_nao_negra_uf].groupby("uf_code"):
        r = _row(uf, "uf", "T", "nao_negras", "total", _agg(g))
        if r: rows.append(r)

    # UF × race='total' × formality='total' at sex='T'
    for uf, g in dom_uf.groupby("uf_code"):
        r = _row(uf, "uf", "T", "total", "total", _agg(g))
        if r: rows.append(r)

    return rows


def build_prev_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Aggregate previdência contribution (V4032=1) among trabalhadoras
    domésticas. Same structure as build_hours_rows. Drops rows with missing
    V4032 (rare for employed people).

    Substantive expectation: pct_with_prev among 'sem_carteira' should be
    much lower than among 'com_carteira'. The com–sem gap is the headline
    advocacy number (retirement rights).
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
    # V4032: 1=Sim (contributing), 2=Não, blank=not applicable
    df["prev_yes"] = (df["V4032"].astype(str).str.strip() == "1").astype(int)
    df["prev_known"] = df["V4032"].astype(str).str.strip().isin(["1", "2"])

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES) & df["prev_known"]].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["sex_code"] = dom["V2007"].map(SEX_MAP)
    dom["formality_code"] = dom["VD4009"].map(FORMALITY_MAP)
    dom["uf_code"] = dom["UF"].astype(str).str.zfill(2)
    dom = dom[dom["race_code"].notna() & dom["sex_code"].notna() & dom["formality_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    def _agg(group):
        w = group["weight"]; y = group["prev_yes"]
        if w.sum() == 0:
            return None
        return {
            "pct_with_prev": round(100 * float((y * w).sum() / w.sum()), 2),
            "n_with_prev": int(group["prev_yes"].sum()),
            "n_unweighted": int(len(group)),
        }

    def _row(uf, level, sex, race, form, agg):
        if agg is None:
            return None
        return {
            "_period_code": db_period,
            "_geo_code": uf, "_geo_level": level,
            "_sex": sex, "_race": race, "_formality": form,
            **agg,
        }

    # Same level structure as hours
    for (sex, race, form), g in dom.groupby(["sex_code", "race_code", "formality_code"]):
        r = _row("BR", "country", sex, race, form, _agg(g))
        if r: rows.append(r)

    for race, g in dom.groupby("race_code"):
        r = _row("BR", "country", "T", race, "total", _agg(g))
        if r: rows.append(r)

    for (race, form), g in dom.groupby(["race_code", "formality_code"]):
        r = _row("BR", "country", "T", race, form, _agg(g))
        if r: rows.append(r)

    is_negra = dom["race_code"].isin(["preta", "parda"])
    for form_code in ["com_carteira", "sem_carteira", "total"]:
        mask = is_negra if form_code == "total" else is_negra & (dom["formality_code"] == form_code)
        g = dom[mask]
        if len(g):
            r = _row("BR", "country", "T", "preta_parda", form_code, _agg(g))
            if r: rows.append(r)

    is_nao_negra = dom["race_code"].isin(["branca", "amarela", "indigena"])
    for form_code in ["com_carteira", "sem_carteira", "total"]:
        mask = is_nao_negra if form_code == "total" else is_nao_negra & (dom["formality_code"] == form_code)
        g = dom[mask]
        if len(g):
            r = _row("BR", "country", "T", "nao_negras", form_code, _agg(g))
            if r: rows.append(r)

    r = _row("BR", "country", "T", "total", "total", _agg(dom))
    if r: rows.append(r)

    dom_uf = dom[dom["uf_code"].isin(UF_CODE_TO_SIGLA)]
    for (uf, race), g in dom_uf.groupby(["uf_code", "race_code"]):
        r = _row(uf, "uf", "T", race, "total", _agg(g))
        if r: rows.append(r)

    is_negra_uf = dom_uf["race_code"].isin(["preta", "parda"])
    for uf, g in dom_uf[is_negra_uf].groupby("uf_code"):
        r = _row(uf, "uf", "T", "preta_parda", "total", _agg(g))
        if r: rows.append(r)

    is_nao_negra_uf = dom_uf["race_code"].isin(["branca", "amarela", "indigena"])
    for uf, g in dom_uf[is_nao_negra_uf].groupby("uf_code"):
        r = _row(uf, "uf", "T", "nao_negras", "total", _agg(g))
        if r: rows.append(r)

    for uf, g in dom_uf.groupby("uf_code"):
        r = _row(uf, "uf", "T", "total", "total", _agg(g))
        if r: rows.append(r)

    return rows


# =============================================================================
# build_autonomous_rows — Step 2 of MEI proxy pipeline (mei_proxy_path.md)
# =============================================================================
# Conta-própria / empregador × CNPJ cross-tab from PNADC microdata, with
# CBO-Domiciliar bucketing for domestic-adjacent occupations.
#
# This sits OUTSIDE the regular trabalhador-doméstico filter (VD4009 ∈ 03,04)
# because V4019 (CNPJ?) is only asked of VD4009 ∈ {08 empregador, 09 conta-própria}.
# Diaristas legally registered as MEI still appear in VD4009='04' here in the
# IBGE classification — for them V4019 is blank. The MEI proxy must be computed
# off the conta-própria population.
#
# Sample-size note: per probe_mei_vars.py (012026), CBO 5162 (cuidadora) is
# very thin (~4 rows/quarter). Cells with n_unweighted < 30 emit nulls for
# pct_with_prev and mean_wage_brl; the dashboard layer decides whether to
# render or aggregate to annual pools.

CBO_DOMESTIC_ADJACENT = {
    "5121": "domestic_5121",       # empregada doméstica (legally NOT MEI-eligible)
    "5141": "cleaning_5141",       # limpeza/conservação
    "5143": "cleaning_5141",       # collapse 5143 into the 5141 bucket
    "5162": "caregiver_5162",      # cuidadora — cleanest MEI-eligible bucket
}

# VD4009 → autonomy root (the two positions where V4019 is asked)
AUTONOMY_VD4009 = {"08": "empregador", "09": "conta_propria"}


def build_autonomous_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Cross-tab conta-própria/empregador × CNPJ × CBO × race × sex,
    restricted to domestic-adjacent CBO-Domiciliar codes (plus 'other'
    catch-all for sample-size sanity). Output mirrors the row shape of
    other builders so upsert_autonomous_to_supabase() can resolve dim FKs."""
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    # Restrict to the population where V4019 is asked
    auto = df[df["VD4009"].isin(AUTONOMY_VD4009.keys())].copy()
    auto["position_root"] = auto["VD4009"].map(AUTONOMY_VD4009)

    # CNPJ flag — and exclude rows where V4019 is missing/invalid
    auto["V4019_str"] = auto["V4019"].astype(str).str.strip()
    auto = auto[auto["V4019_str"].isin(["1", "2"])]
    auto["has_cnpj"] = auto["V4019_str"] == "1"
    auto["autonomy_code"] = (
        auto["position_root"]
        + auto["has_cnpj"].map({True: "_cnpj", False: "_sem_cnpj"})
    )

    # CBO bucketing — first 4 chars of V4010
    auto["cbo_group"] = (
        auto["V4010"].astype(str).str.strip().str[:4]
        .map(lambda c: CBO_DOMESTIC_ADJACENT.get(c, "other"))
    )

    auto["race_code"] = auto["V2010"].map(RACE_MAP)
    auto["sex_code"]  = auto["V2007"].map(SEX_MAP)
    auto = auto[auto["race_code"].notna() & auto["sex_code"].notna()].copy()
    auto["uf_code"] = auto["UF"].astype(str).str.zfill(2)

    db_period = microdata_period_to_db_code(period)

    def _agg(group: pd.DataFrame) -> dict | None:
        if len(group) == 0:
            return None
        w = group["weight"]
        if w.sum() == 0:
            return None
        prev_known = group["V4032"].astype(str).str.strip().isin(["1", "2"])
        prev_g = group[prev_known]
        # VD4019: rendimento mensal habitual em R$ (whole reais — NOT centavos,
        # despite the "implicit decimals" comment in the IBGE dictionary; the
        # quarterly PNADC microdata pre-divides). Confirmed by triangulation
        # against the existing build_family_rows wage calc (cleaning_5141 cp_cnpj
        # raw came out to R$35.06 with /100, vs ~R$3500 expected — bug fixed).
        vd4019 = pd.to_numeric(group["VD4019"], errors="coerce")
        wage_g = group[vd4019 > 0].copy()
        wage_g["wage_brl"] = pd.to_numeric(wage_g["VD4019"], errors="coerce")
        return {
            "workers_thousands": round(float(w.sum()) / 1000.0, 2),
            "pct_with_prev": (
                round(100.0 * float((
                    (prev_g["V4032"].astype(str).str.strip() == "1").astype(int)
                    * prev_g["weight"]
                ).sum()) / float(prev_g["weight"].sum()), 2)
                if prev_g["weight"].sum() > 0 else None
            ),
            "mean_wage_brl": (
                round(float((wage_g["wage_brl"] * wage_g["weight"]).sum())
                      / float(wage_g["weight"].sum()), 2)
                if len(wage_g) >= 30 and wage_g["weight"].sum() > 0 else None
            ),
            "n_unweighted": int(len(group)),
        }

    rows: list[dict] = []

    def _emit(geo_code, geo_level, sex, race, cbo, aut, agg):
        if agg is None:
            return
        rows.append({
            "_period_code": db_period,
            "_geo_code": geo_code, "_geo_level": geo_level,
            "_sex": sex, "_race": race,
            "cbo_group": cbo, "autonomy_code": aut,
            **agg,
        })

    # ---- BR × race × cbo × autonomy (sex='T') ----
    for (race, cbo, aut), g in auto.groupby(["race_code", "cbo_group", "autonomy_code"]):
        _emit("BR", "country", "T", race, cbo, aut, _agg(g))

    # ---- BR × preta_parda aggregate × cbo × autonomy ----
    is_negra = auto["race_code"].isin(["preta", "parda"])
    for (cbo, aut), g in auto[is_negra].groupby(["cbo_group", "autonomy_code"]):
        _emit("BR", "country", "T", "preta_parda", cbo, aut, _agg(g))

    # ---- BR × nao_negras aggregate × cbo × autonomy ----
    is_nao_negra = auto["race_code"].isin(["branca", "amarela", "indigena"])
    for (cbo, aut), g in auto[is_nao_negra].groupby(["cbo_group", "autonomy_code"]):
        _emit("BR", "country", "T", "nao_negras", cbo, aut, _agg(g))

    # ---- BR × race='total' × cbo × autonomy (the headline cell) ----
    for (cbo, aut), g in auto.groupby(["cbo_group", "autonomy_code"]):
        _emit("BR", "country", "T", "total", cbo, aut, _agg(g))

    # ---- SP × race='total' × cbo × autonomy (only when n_unweighted >= 30) ----
    sp = auto[auto["uf_code"] == "35"]
    for (cbo, aut), g in sp.groupby(["cbo_group", "autonomy_code"]):
        agg = _agg(g)
        if agg and agg["n_unweighted"] >= 30:
            _emit("35", "uf", "T", "total", cbo, aut, agg)

    return rows


def build_education_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Aggregate education levels (VD3004) for trabalhadoras(es) domésticas(os).

    Emits weighted count + % within race for:
      - BR × sex='T' × race × education_bucket (5 races × 5 buckets = 25)
      - BR × sex='T' × preta_parda × education_bucket (5)
      - BR × sex='T' × nao_negras × education_bucket (5)
      - BR × sex='T' × race × education='total' (5 + 2 = 7)
      - BR × sex='T' × race='total' × education_bucket (5)

    Total: ~50 rows per quarter; ~2.8k rows over the 56-quarter backfill.

    Skips rows where VD3004 is null / not in the 1-7 native code set.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES) & df["weight"].notna()].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    # VD3004 is stored as a 1-char string; strip whitespace just in case
    dom["ed_raw"] = dom["VD3004"].astype(str).str.strip()
    dom["education_code"] = dom["ed_raw"].map(EDUCATION_MAP)
    dom = dom[dom["race_code"].notna() & dom["education_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    EDUCATION_BUCKETS = ["fund_inc", "fund_comp", "med_inc", "med_comp", "sup"]

    def _row(geo, level, sex, race, education, w_sum, w_race_total, n):
        if w_sum is None or w_sum == 0:
            return None
        pct = round(100 * w_sum / w_race_total, 2) if w_race_total else None
        # workers_thousands is in *thousands of people*. The raw weight sum
        # is in single people, so divide by 1000. (The unit convention matches
        # the rest of the project — see workers_thousands in dw_workers.)
        return {
            "_period_code": db_period,
            "_geo_code": geo, "_geo_level": level,
            "_sex": sex, "_race": race, "_education": education,
            "workers_thousands": round(float(w_sum) / 1000.0, 2),
            "pct_within_race": pct,
            "n_unweighted": int(n),
        }

    def emit_for_subset(race_label: str, subset: pd.DataFrame):
        """Emit 5 education-bucket rows + 1 total row for a (race-defined) subset."""
        total_w = subset["weight"].sum()
        for ed in EDUCATION_BUCKETS:
            g = subset[subset["education_code"] == ed]
            r = _row("BR", "country", "T", race_label, ed,
                     g["weight"].sum(), total_w, len(g))
            if r: rows.append(r)
        r = _row("BR", "country", "T", race_label, "total",
                 total_w, total_w, len(subset))
        if r: rows.append(r)

    # Per-native-race emissions (branca, preta, amarela, parda, indigena)
    for race, g in dom.groupby("race_code"):
        emit_for_subset(race, g)

    # Aggregate negras (preta + parda)
    is_negra = dom["race_code"].isin(["preta", "parda"])
    emit_for_subset("preta_parda", dom[is_negra])

    # Aggregate nao_negras (branca + amarela + indigena)
    is_nao_negra = dom["race_code"].isin(["branca", "amarela", "indigena"])
    emit_for_subset("nao_negras", dom[is_nao_negra])

    # Race='total' — all domestic workers regardless of race
    emit_for_subset("total", dom)

    return rows


def build_family_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Aggregate household position (V2003) for trabalhadoras(es) domésticas(os),
    with wage cross-tab (VD4019) — the "breadwinner paradox" panel.

    Emits weighted count + % within race + mean wage for:
      - BR × sex='T' × race × family_position (5 races × 4 positions = 20)
      - BR × sex='T' × preta_parda × family_position (4)
      - BR × sex='T' × nao_negras × family_position (4)
      - BR × sex='T' × race × position='total' (5 + 2 = 7)
      - BR × sex='T' × race='total' × family_position (4)

    Total: ~40 rows per quarter; ~2.2k rows over the 56-quarter backfill.

    Two headline cuts:
      - % chefe de família by race (DIEESE 2026 publishes 46% aggregate,
        doesn't disaggregate by race)
      - mean wage of chefes by race (nobody publishes this — the breadwinner
        paradox: workers carrying more household financial responsibility
        also earning less due to the racial gap)

    Wage notes:
      - VD4019 is rendimento mensal habitual em qualquer trabalho (R$ nominal).
      - Computed only over workers with VD4019 > 0 (drops the unemployed +
        non-earners — they shouldn't anchor a "wage of chefes" reading).
      - wage_n_with_income tracks the unweighted sample feeding the wage
        estimate, separately from n_unweighted (the count for the % cell).
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
    df["wage"] = pd.to_numeric(df["VD4019"], errors="coerce")

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES) & df["weight"].notna()].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    # V2003 is stored as a 2-char string; strip whitespace and pad
    dom["v2003_raw"] = dom["V2003"].astype(str).str.strip().str.zfill(2)
    dom["family_code"] = dom["v2003_raw"].map(FAMILY_POSITION_MAP)
    dom = dom[dom["race_code"].notna() & dom["family_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    FAMILY_BUCKETS = ["chefe", "conjuge", "filha", "outro"]

    def _wage_stats(cell: pd.DataFrame):
        """Weighted mean wage over workers with VD4019 > 0. Returns
        (wage_mean_brl, wage_n_with_income) or (None, 0) if the cell is empty."""
        with_inc = cell[cell["wage"].notna() & (cell["wage"] > 0)]
        if len(with_inc) == 0 or with_inc["weight"].sum() == 0:
            return None, 0
        wmean = (with_inc["wage"] * with_inc["weight"]).sum() / with_inc["weight"].sum()
        return round(float(wmean), 2), int(len(with_inc))

    def _row(geo, level, sex, race, family, w_sum, w_race_total, n,
             wage_mean_brl, wage_n_with_income):
        if w_sum is None or w_sum == 0:
            return None
        pct = round(100 * w_sum / w_race_total, 2) if w_race_total else None
        # workers_thousands in *thousands of people* — raw weight sum is in
        # single people, divide by 1000 to match the project convention.
        return {
            "_period_code": db_period,
            "_geo_code": geo, "_geo_level": level,
            "_sex": sex, "_race": race, "_family": family,
            "workers_thousands": round(float(w_sum) / 1000.0, 2),
            "pct_within_race": pct,
            "n_unweighted": int(n),
            "wage_mean_brl": wage_mean_brl,
            "wage_n_with_income": wage_n_with_income,
        }

    def emit_for_subset(race_label: str, subset: pd.DataFrame):
        total_w = subset["weight"].sum()
        # Per-bucket rows
        for fam in FAMILY_BUCKETS:
            g = subset[subset["family_code"] == fam]
            wage_mean, wage_n = _wage_stats(g)
            r = _row("BR", "country", "T", race_label, fam,
                     g["weight"].sum(), total_w, len(g),
                     wage_mean, wage_n)
            if r:
                rows.append(r)
        # Race-total row (across all family positions)
        wage_mean, wage_n = _wage_stats(subset)
        r = _row("BR", "country", "T", race_label, "total",
                 total_w, total_w, len(subset),
                 wage_mean, wage_n)
        if r:
            rows.append(r)

    for race, g in dom.groupby("race_code"):
        emit_for_subset(race, g)

    is_negra = dom["race_code"].isin(["preta", "parda"])
    emit_for_subset("preta_parda", dom[is_negra])

    is_nao_negra = dom["race_code"].isin(["branca", "amarela", "indigena"])
    emit_for_subset("nao_negras", dom[is_nao_negra])

    emit_for_subset("total", dom)

    return rows


def build_contract_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Aggregate contract type (V4024: mensalista/diarista) for
    trabalhadoras(es) domésticas(os) — Mayer DiD hypothesis support.

    Emits per (race × contract_type × formality) cell:
      - BR × sex='T' × race × contract × formality
      - preta_parda × contract × formality
      - nao_negras × contract × formality
      - race='total' × contract × formality

    Three contract values: mensalista, diarista, total
    Three formality values: com_carteira, sem_carteira, total

    Per quarter: ~5 races × 3 contracts × 3 formality + aggregates ≈ 80 rows.
    Full backfill: ~4.5k rows.

    Why include formality cross-tab: lets us test BOTH:
      (a) Did the diarista share rise post-2017 differentially by race?
      (b) Did the % com carteira within mensalistas fall post-2017?
    These two are jointly informative about the Mayer hypothesis: if (a) is
    positive but (b) is null, the racialized informalization works via
    contract-type substitution; if (b) is also negative, employers shifted
    even formal mensalistas toward informal arrangements.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES) & df["weight"].notna()].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["formality_code"] = dom["VD4009"].map(FORMALITY_MAP)
    dom["v4024_raw"] = dom["V4024"].astype(str).str.strip()
    dom["contract_code"] = dom["v4024_raw"].map(CONTRACT_MAP)
    dom = dom[dom["race_code"].notna() & dom["formality_code"].notna() & dom["contract_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    CONTRACT_BUCKETS = ["mensalista", "diarista"]
    FORMALITY_BUCKETS = ["com_carteira", "sem_carteira"]

    def _row(race, contract, formality, w_sum, w_race_total, n):
        if w_sum is None or w_sum == 0:
            return None
        pct = round(100 * w_sum / w_race_total, 2) if w_race_total else None
        return {
            "_period_code": db_period,
            "_geo_code": "BR", "_geo_level": "country",
            "_sex": "T", "_race": race, "_contract": contract, "_formality": formality,
            "workers_thousands": round(float(w_sum) / 1000.0, 2),
            "pct_within_race": pct,
            "n_unweighted": int(n),
        }

    def emit_for_subset(race_label: str, subset: pd.DataFrame):
        total_w = subset["weight"].sum()
        # contract × formality cells
        for ct in CONTRACT_BUCKETS:
            for fm in FORMALITY_BUCKETS:
                g = subset[(subset["contract_code"] == ct) & (subset["formality_code"] == fm)]
                r = _row(race_label, ct, fm, g["weight"].sum(), total_w, len(g))
                if r:
                    rows.append(r)
        # contract × formality='total'
        for ct in CONTRACT_BUCKETS:
            g = subset[subset["contract_code"] == ct]
            r = _row(race_label, ct, "total", g["weight"].sum(), total_w, len(g))
            if r:
                rows.append(r)
        # contract='total' × formality
        for fm in FORMALITY_BUCKETS:
            g = subset[subset["formality_code"] == fm]
            r = _row(race_label, "total", fm, g["weight"].sum(), total_w, len(g))
            if r:
                rows.append(r)
        # contract='total' × formality='total' — race totals
        r = _row(race_label, "total", "total", total_w, total_w, len(subset))
        if r:
            rows.append(r)

    for race, g in dom.groupby("race_code"):
        emit_for_subset(race, g)

    emit_for_subset("preta_parda", dom[dom["race_code"].isin(["preta", "parda"])])
    emit_for_subset("nao_negras", dom[dom["race_code"].isin(["branca", "amarela", "indigena"])])
    emit_for_subset("total", dom)

    return rows


def build_age_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Aggregate age bands (V2009) for trabalhadoras(es) domésticas(os).

    The Theme 2 panel — "Onde estão as jovens?" — uses these rows. Bucket
    breakpoints are DIEESE-aligned so the dashboard can triangulate against
    the Apr/2026 Infográfico table:
      - under_29 (DIEESE reports 12%)
      - 30_44    (DIEESE reports 32%)
      - 45_59    (DIEESE reports 43%)
      - 60_plus  (DIEESE reports 13%)

    Emits weighted count + % within race for:
      - BR × sex='T' × race × age_band (5 races × 4 bands = 20)
      - BR × sex='T' × preta_parda × age_band (4)
      - BR × sex='T' × nao_negras × age_band (4)
      - BR × sex='T' × race × age_band='total' (5 + 2 = 7)
      - BR × sex='T' × race='total' × age_band (4)

    Total: ~40 rows per quarter; ~2.2k rows over the 56-quarter backfill.

    The cohort interpretation is implicit: with 56 quarters of (race, band)
    data, the dashboard can reconstruct birth-cohort trajectories — a
    1995-born worker enters the "under_29" band at all of 2012–2024 and
    crosses into "30_44" in 2025. Pseudo-cohort reading is fine for the
    story; true panel-based cohort tracking is left for a future iteration.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
    df["age_int"] = pd.to_numeric(df["V2009"], errors="coerce")

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES) & df["weight"].notna() & df["age_int"].notna()].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["age_band"] = dom["age_int"].astype(int).apply(age_to_band)
    dom = dom[dom["race_code"].notna() & dom["age_band"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    AGE_BUCKETS = ["under_29", "30_44", "45_59", "60_plus"]

    def _row(geo, level, sex, race, age_band, w_sum, w_race_total, n):
        if w_sum is None or w_sum == 0:
            return None
        pct = round(100 * w_sum / w_race_total, 2) if w_race_total else None
        # workers_thousands in *thousands of people* — raw weight sum is in
        # single people, divide by 1000 to match the project convention.
        return {
            "_period_code": db_period,
            "_geo_code": geo, "_geo_level": level,
            "_sex": sex, "_race": race, "_age_band": age_band,
            "workers_thousands": round(float(w_sum) / 1000.0, 2),
            "pct_within_race": pct,
            "n_unweighted": int(n),
        }

    def emit_for_subset(race_label: str, subset: pd.DataFrame):
        total_w = subset["weight"].sum()
        for band in AGE_BUCKETS:
            g = subset[subset["age_band"] == band]
            r = _row("BR", "country", "T", race_label, band,
                     g["weight"].sum(), total_w, len(g))
            if r:
                rows.append(r)
        r = _row("BR", "country", "T", race_label, "total",
                 total_w, total_w, len(subset))
        if r:
            rows.append(r)

    for race, g in dom.groupby("race_code"):
        emit_for_subset(race, g)

    emit_for_subset("preta_parda", dom[dom["race_code"].isin(["preta", "parda"])])
    emit_for_subset("nao_negras", dom[dom["race_code"].isin(["branca", "amarela", "indigena"])])
    emit_for_subset("total", dom)

    return rows


def build_housing_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Aggregate housing tenure (V0212) for trabalhadoras(es) domésticas(os).

    Emits weighted count + % within race for:
      - BR × sex='T' × race × housing_tenure (5 races × 4 buckets = 20)
      - BR × sex='T' × preta_parda × housing_tenure (4)
      - BR × sex='T' × nao_negras × housing_tenure (4)
      - BR × sex='T' × race × tenure='total' (5 + 2 = 7)
      - BR × sex='T' × race='total' × housing_tenure (4)

    Total: ~40 rows per quarter; ~2.2k rows over the 56-quarter backfill.

    The headline cuts: % próprio (homeownership rate) and % cedido_empregador
    (live-in share). The latter is a structural-vulnerability indicator —
    workers living at the employer's premises have weaker bargaining power
    and historically less LC 150 protection.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES) & df["weight"].notna()].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["v0212_raw"] = dom["V0212"].astype(str).str.strip()
    dom["housing_code"] = dom["v0212_raw"].map(HOUSING_TENURE_MAP)
    dom = dom[dom["race_code"].notna() & dom["housing_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    HOUSING_BUCKETS = ["proprio", "alugado", "cedido_empregador", "outro"]

    def _row(geo, level, sex, race, housing, w_sum, w_race_total, n):
        if w_sum is None or w_sum == 0:
            return None
        pct = round(100 * w_sum / w_race_total, 2) if w_race_total else None
        # workers_thousands in *thousands of people* — raw weight sum is in
        # single people, divide by 1000 to match the project convention.
        return {
            "_period_code": db_period,
            "_geo_code": geo, "_geo_level": level,
            "_sex": sex, "_race": race, "_housing": housing,
            "workers_thousands": round(float(w_sum) / 1000.0, 2),
            "pct_within_race": pct,
            "n_unweighted": int(n),
        }

    def emit_for_subset(race_label: str, subset: pd.DataFrame):
        total_w = subset["weight"].sum()
        for h in HOUSING_BUCKETS:
            g = subset[subset["housing_code"] == h]
            r = _row("BR", "country", "T", race_label, h,
                     g["weight"].sum(), total_w, len(g))
            if r: rows.append(r)
        r = _row("BR", "country", "T", race_label, "total",
                 total_w, total_w, len(subset))
        if r: rows.append(r)

    for race, g in dom.groupby("race_code"):
        emit_for_subset(race, g)

    is_negra = dom["race_code"].isin(["preta", "parda"])
    emit_for_subset("preta_parda", dom[is_negra])

    is_nao_negra = dom["race_code"].isin(["branca", "amarela", "indigena"])
    emit_for_subset("nao_negras", dom[is_nao_negra])

    emit_for_subset("total", dom)

    return rows


# ----- Supabase upsert --------------------------------------------------------

SOURCE_TABLE_TAG = "PNADC-MICRODATA"


def build_wage_rows(df: pd.DataFrame, period: str) -> list[dict]:
    """Produce fact_wages payload rows: weighted-mean nominal wages of
    trabalhadoras(es) domésticas(os) by race × formality.

    Wages are NOMINAL (current reais), not deflated. The dashboard's existing
    "Rendimento médio" chart uses real (deflated) wages from PNADC-6391; this
    new microdata-derived series serves the racial wage GAP, which is a ratio
    and so is invariant to nominal/real choice.

    Two wage measures emitted per cell:
      - mean_wage_brl_real  — monthly mean (R$/month, weighted)
      - mean_hourly_brl     — hourly mean (R$/hour, weighted across workers
                              with both wage>0 AND hours>0; computed as
                              individual wage/(hours×4.33) then weight-averaged)

    The hourly figure supports the per-hour racial gap decomposition: if the
    monthly gap is wider than the hourly gap, the difference is composition
    (Mensalista vs Diarista) rather than per-hour price.

    Output: 5 races + 1 nao_negras + 1 preta_parda, each × 3 formalities
    (com_carteira, sem_carteira, total). ~21 wage rows per quarter.
    """
    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
    df["wage"] = pd.to_numeric(df["VD4019"], errors="coerce")
    df["hours"] = pd.to_numeric(df["V4039"], errors="coerce")

    DOMESTIC_CODES = ["03", "04"]
    dom = df[df["VD4009"].isin(DOMESTIC_CODES)
             & df["wage"].notna()
             & (df["wage"] > 0)].copy()
    dom["race_code"] = dom["V2010"].map(RACE_MAP)
    dom["formality_code"] = dom["VD4009"].map(FORMALITY_MAP)
    dom = dom[dom["race_code"].notna() & dom["formality_code"].notna()]

    db_period = microdata_period_to_db_code(period)
    rows: list[dict] = []

    # Hours-per-month conversion: 4.33 weeks/month (52 weeks / 12 months)
    WEEKS_PER_MONTH = 4.33

    def _wmean(g):
        if g["weight"].sum() == 0: return None
        return float((g["wage"] * g["weight"]).sum() / g["weight"].sum())

    def _wmean_hourly(g):
        """Weighted mean of individual hourly wages. Restricted to workers
        with valid hours > 0 AND <= 98 (PNADC's max-hours sentinel)."""
        with_hours = g[g["hours"].notna() & (g["hours"] > 0) & (g["hours"] <= 98)]
        if with_hours["weight"].sum() == 0:
            return None
        hourly = with_hours["wage"] / (with_hours["hours"] * WEEKS_PER_MONTH)
        return float((hourly * with_hours["weight"]).sum() / with_hours["weight"].sum())

    def _row(race, form, mean_monthly, mean_hourly):
        if mean_monthly is None or pd.isna(mean_monthly): return None
        return {
            "_period_code": db_period,
            "_geo_code": "BR", "_geo_level": "country",
            "_sex": "T", "_race": race, "_formality": form,
            "mean_wage_brl_real": round(mean_monthly, 2),
            "median_wage_brl_real": None,
            "mean_hourly_brl": round(mean_hourly, 2) if mean_hourly is not None and not pd.isna(mean_hourly) else None,
        }

    # Race × formality (5 races × 2 formalities)
    for (race, form), group in dom.groupby(["race_code", "formality_code"]):
        r = _row(race, form, _wmean(group), _wmean_hourly(group))
        if r: rows.append(r)

    # Race × total (sum across com+sem)
    for race, group in dom.groupby("race_code"):
        r = _row(race, "total", _wmean(group), _wmean_hourly(group))
        if r: rows.append(r)

    # preta_parda × each formality
    is_negra = dom["race_code"].isin(["preta", "parda"])
    for form_code in ["com_carteira", "sem_carteira", "total"]:
        if form_code == "total":
            mask = is_negra
        else:
            mask = is_negra & (dom["formality_code"] == form_code)
        group = dom[mask]
        r = _row("preta_parda", form_code, _wmean(group), _wmean_hourly(group)) if len(group) else None
        if r: rows.append(r)

    # nao_negras × each formality (white + Asian + Indigenous; complement set)
    is_nao_negra = dom["race_code"].isin(["branca", "amarela", "indigena"])
    for form_code in ["com_carteira", "sem_carteira", "total"]:
        if form_code == "total":
            mask = is_nao_negra
        else:
            mask = is_nao_negra & (dom["formality_code"] == form_code)
        group = dom[mask]
        r = _row("nao_negras", form_code, _wmean(group), _wmean_hourly(group)) if len(group) else None
        if r: rows.append(r)

    return rows


def upsert_wages_to_supabase(rows: list[dict]) -> int:
    """Push wage rows into domestic_work.fact_wages."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")

    # dim_time entries are already created by upsert_to_supabase; just look them up.
    time_lookup = {r["period_code"]: r["time_id"]
                   for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"]
                  for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"]
                   for r in schema.table("dim_race").select("code,race_id").execute().data}
    formality_lookup = {r["code"]: r["formality_id"]
                        for r in schema.table("dim_formality").select("code,formality_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"]
                  for r in schema.table("dim_sex").select("code,sex_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":      time_lookup[r["_period_code"]],
                "geo_id":       geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":       sex_lookup[r["_sex"]],
                "race_id":      race_lookup[r["_race"]],
                "formality_id": formality_lookup[r["_formality"]],
                "mean_wage_brl_real":   r["mean_wage_brl_real"],
                "median_wage_brl_real": r["median_wage_brl_real"],
                "mean_hourly_brl":      r.get("mean_hourly_brl"),
                "source_table": SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for wage row %s: %s", r, e)

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_wages").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,formality_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_hours_to_supabase(rows: list[dict]) -> int:
    """Push hours rows into domestic_work.fact_hours."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    formality_lookup = {r["code"]: r["formality_id"] for r in schema.table("dim_formality").select("code,formality_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"] for r in schema.table("dim_sex").select("code,sex_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":      time_lookup[r["_period_code"]],
                "geo_id":       geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":       sex_lookup[r["_sex"]],
                "race_id":      race_lookup[r["_race"]],
                "formality_id": formality_lookup[r["_formality"]],
                "mean_hours_per_week": r["mean_hours_per_week"],
                "pct_over_44h":        r["pct_over_44h"],
                "n_unweighted":        r["n_unweighted"],
                "source_table": SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for hours row %s: %s", r, e)

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_hours").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,formality_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_prev_to_supabase(rows: list[dict]) -> int:
    """Push previdência rows into domestic_work.fact_prev."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    formality_lookup = {r["code"]: r["formality_id"] for r in schema.table("dim_formality").select("code,formality_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"] for r in schema.table("dim_sex").select("code,sex_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":      time_lookup[r["_period_code"]],
                "geo_id":       geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":       sex_lookup[r["_sex"]],
                "race_id":      race_lookup[r["_race"]],
                "formality_id": formality_lookup[r["_formality"]],
                "pct_with_prev": r["pct_with_prev"],
                "n_with_prev":   r["n_with_prev"],
                "n_unweighted":  r["n_unweighted"],
                "source_table":  SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for prev row %s: %s", r, e)

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_prev").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,formality_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_autonomous_to_supabase(rows: list[dict]) -> int:
    """Push autonomous-worker rows (conta-própria × CNPJ × CBO × race × sex)
    into domestic_work.fact_autonomous. Schema applied via
    schema/004_fact_autonomous.sql. cbo_group and autonomy_code are stored
    as plain text (CHECK-constrained), not dim FKs."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup  = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    sex_lookup  = {r["code"]: r["sex_id"]  for r in schema.table("dim_sex").select("code,sex_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":           time_lookup[r["_period_code"]],
                "geo_id":            geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":            sex_lookup[r["_sex"]],
                "race_id":           race_lookup[r["_race"]],
                "cbo_group":         r["cbo_group"],
                "autonomy_code":     r["autonomy_code"],
                "workers_thousands": r.get("workers_thousands"),
                "pct_with_prev":     r.get("pct_with_prev"),
                "mean_wage_brl":     r.get("mean_wage_brl"),
                "n_unweighted":      r["n_unweighted"],
                "source_table":      SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for autonomous row %s: %s", r, e)

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_autonomous").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,cbo_group,autonomy_code,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_education_to_supabase(rows: list[dict]) -> int:
    """Push education rows into domestic_work.fact_education."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"] for r in schema.table("dim_sex").select("code,sex_id").execute().data}
    edu_lookup = {r["code"]: r["education_id"] for r in schema.table("dim_education").select("code,education_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":      time_lookup[r["_period_code"]],
                "geo_id":       geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":       sex_lookup[r["_sex"]],
                "race_id":      race_lookup[r["_race"]],
                "education_id": edu_lookup[r["_education"]],
                "workers_thousands": r["workers_thousands"],
                "pct_within_race":   r["pct_within_race"],
                "n_unweighted":      r["n_unweighted"],
                "source_table":      SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for education row %s: %s", r, e)

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_education").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,education_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_family_to_supabase(rows: list[dict]) -> int:
    """Push family-position rows into domestic_work.fact_family."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"] for r in schema.table("dim_sex").select("code,sex_id").execute().data}
    fam_lookup = {r["code"]: r["family_id"] for r in schema.table("dim_family").select("code,family_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":   time_lookup[r["_period_code"]],
                "geo_id":    geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":    sex_lookup[r["_sex"]],
                "race_id":   race_lookup[r["_race"]],
                "family_id": fam_lookup[r["_family"]],
                "workers_thousands":   r["workers_thousands"],
                "pct_within_race":     r["pct_within_race"],
                "wage_mean_brl":       r.get("wage_mean_brl"),
                "wage_n_with_income":  r.get("wage_n_with_income"),
                "n_unweighted":        r["n_unweighted"],
                "source_table":        SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for family row %s: %s", r, e)

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_family").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,family_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_contract_to_supabase(rows: list[dict]) -> int:
    """Push contract-type rows into domestic_work.fact_contract."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"] for r in schema.table("dim_sex").select("code,sex_id").execute().data}
    formality_lookup = {r["code"]: r["formality_id"] for r in schema.table("dim_formality").select("code,formality_id").execute().data}
    contract_lookup = {r["code"]: r["contract_id"] for r in schema.table("dim_contract").select("code,contract_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":     time_lookup[r["_period_code"]],
                "geo_id":      geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":      sex_lookup[r["_sex"]],
                "race_id":     race_lookup[r["_race"]],
                "contract_id": contract_lookup[r["_contract"]],
                "formality_id": formality_lookup[r["_formality"]],
                "workers_thousands": r["workers_thousands"],
                "pct_within_race":   r["pct_within_race"],
                "n_unweighted":      r["n_unweighted"],
                "source_table":      SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for contract row %s: %s", r, e)

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_contract").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,contract_id,formality_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_age_to_supabase(rows: list[dict]) -> int:
    """Push age-band rows into domestic_work.fact_age."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"] for r in schema.table("dim_sex").select("code,sex_id").execute().data}
    age_lookup = {r["code"]: r["age_band_id"] for r in schema.table("dim_age_band").select("code,age_band_id").execute().data}

    payload = []
    for r in rows:
        try:
            payload.append({
                "time_id":     time_lookup[r["_period_code"]],
                "geo_id":      geo_lookup[(r["_geo_level"], r["_geo_code"])],
                "sex_id":      sex_lookup[r["_sex"]],
                "race_id":     race_lookup[r["_race"]],
                "age_band_id": age_lookup[r["_age_band"]],
                "workers_thousands": r["workers_thousands"],
                "pct_within_race":   r["pct_within_race"],
                "n_unweighted":      r["n_unweighted"],
                "source_table":      SOURCE_TABLE_TAG,
            })
        except KeyError as e:
            log.warning("missing dim lookup for age row %s: %s", r, e)

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_age").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,age_band_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_housing_to_supabase(rows: list[dict]) -> int:
    """Push housing-tenure rows into domestic_work.fact_housing."""
    sb = get_supabase_client()
    if sb is None or not rows:
        return 0
    schema = sb.schema("domestic_work")
    time_lookup = {r["period_code"]: r["time_id"] for r in schema.table("dim_time").select("period_code,time_id").execute().data}
    geo_lookup = {(r["level"], r["code"]): r["geo_id"] for r in schema.table("dim_geo").select("level,code,geo_id").execute().data}
    race_lookup = {r["code"]: r["race_id"] for r in schema.table("dim_race").select("code,race_id").execute().data}
    sex_lookup = {r["code"]: r["sex_id"] for r in schema.table("dim_sex").select("code,sex_id").execute().data}
    housing_lookup = {r["code"]: r["housing_id"] for r in schema.table("dim_housing").select("code,housing_id").execute().data}

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
    for i in range(0, len(payload), 250):
        chunk = payload[i:i + 250]
        res = schema.table("fact_housing").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,housing_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


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
                "n_unweighted": r.get("n_unweighted"),
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

    # ---- counts by race (fact_workers) ----
    rows = build_fact_rows(df, period)
    n_dom = sum(r["workers_thousands"] for r in rows
                if r["_race"] != "preta_parda" and r["_formality"] == "total")
    n_negras = sum(r["workers_thousands"] for r in rows
                   if r["_race"] == "preta_parda" and r["_formality"] == "total")
    pct_negras = round(100 * n_negras / n_dom, 1) if n_dom else None

    # ---- counts by sex (fact_workers) ----
    sex_rows = build_sex_rows(df, period)
    rows.extend(sex_rows)   # share the same Supabase upsert (fact_workers)
    n_women = sum(r["workers_thousands"] for r in sex_rows
                  if r["_sex"] == "F" and r["_formality"] == "total")
    n_men = sum(r["workers_thousands"] for r in sex_rows
                if r["_sex"] == "M" and r["_formality"] == "total")
    pct_mulheres = round(100 * n_women / (n_women + n_men), 1) if (n_women + n_men) else None

    # ---- counts by race × UF (fact_workers, geo_level='uf') ----
    uf_rows = build_uf_race_rows(df, period)
    rows.extend(uf_rows)   # share the same Supabase upsert (fact_workers)
    # Diagnostic: % negras among São Paulo domesticas — important for the union
    sp_negras = next((r for r in uf_rows
                      if r["_geo_code"] == "35" and r["_race"] == "preta_parda"), None)
    sp_total = next((r for r in uf_rows
                     if r["_geo_code"] == "35" and r["_race"] == "total"), None)
    pct_negras_sp = (round(100 * sp_negras["workers_thousands"] / sp_total["workers_thousands"], 1)
                     if sp_negras and sp_total and sp_total["workers_thousands"] else None)

    # ---- hours (fact_hours) ----
    hours_rows = build_hours_rows(df, period)

    # ---- previdência (fact_prev) ----
    prev_rows = build_prev_rows(df, period)
    # Diagnostic: top-line previdência rate for the union's framing.
    prev_total = next((r for r in prev_rows
                       if r["_geo_code"] == "BR" and r["_race"] == "total"
                       and r["_sex"] == "T" and r["_formality"] == "total"), None)
    pct_prev_total = prev_total["pct_with_prev"] if prev_total else None
    hours_total = next((r for r in hours_rows
                        if r["_geo_code"] == "BR" and r["_race"] == "total"
                        and r["_sex"] == "T" and r["_formality"] == "total"), None)
    mean_hours = hours_total["mean_hours_per_week"] if hours_total else None

    # ---- autonomous workers (fact_autonomous) — MEI proxy Step 2 ----
    # NOTE: filters df INTERNALLY to VD4009 ∈ {08,09} (autonomous subset);
    # does NOT compete with the trabalhador-doméstico filter used by the
    # other builders. Run unconditionally — the dashboard layer decides
    # whether to render cells based on n_unweighted.
    autonomous_rows = build_autonomous_rows(df, period)
    # Diagnostic: % conta-própria com CNPJ at the BR/total cell, all CBOs
    cp_cnpj = next((r for r in autonomous_rows
                    if r["_geo_code"] == "BR" and r["_race"] == "total"
                    and r["cbo_group"] == "other"
                    and r["autonomy_code"] == "conta_propria_cnpj"), None)
    cp_sem = next((r for r in autonomous_rows
                   if r["_geo_code"] == "BR" and r["_race"] == "total"
                   and r["cbo_group"] == "other"
                   and r["autonomy_code"] == "conta_propria_sem_cnpj"), None)
    pct_cp_cnpj = None
    if cp_cnpj and cp_sem and (cp_cnpj["workers_thousands"] + cp_sem["workers_thousands"]) > 0:
        pct_cp_cnpj = round(100 * cp_cnpj["workers_thousands"]
                            / (cp_cnpj["workers_thousands"] + cp_sem["workers_thousands"]), 1)

    # ---- education (fact_education) ----
    edu_rows = build_education_rows(df, period)
    # Diagnostic: % fund_inc among negras (the DIEESE-comparable cut).
    edu_negra_fund = next((r for r in edu_rows
                           if r["_geo_code"] == "BR" and r["_race"] == "preta_parda"
                           and r["_education"] == "fund_inc"), None)
    pct_fund_inc_negras = edu_negra_fund["pct_within_race"] if edu_negra_fund else None

    # ---- family (fact_family) ----
    fam_rows = build_family_rows(df, period)
    # Diagnostic: % chefe de família for negras AND for the category overall.
    # DIEESE Infográfico abr/2026 publishes 46% (category overall); we compute
    # both negras and total for triangulation.
    fam_total_chefe = next((r for r in fam_rows
                            if r["_geo_code"] == "BR" and r["_race"] == "total"
                            and r["_family"] == "chefe"), None)
    pct_chefe_total = fam_total_chefe["pct_within_race"] if fam_total_chefe else None
    fam_negra_chefe = next((r for r in fam_rows
                            if r["_geo_code"] == "BR" and r["_race"] == "preta_parda"
                            and r["_family"] == "chefe"), None)
    pct_chefe_negras = fam_negra_chefe["pct_within_race"] if fam_negra_chefe else None

    # Theme 1 — Breadwinner paradox diagnostic: wage of chefes by race +
    # racial wage gap among chefes specifically.
    fam_nao_negra_chefe = next((r for r in fam_rows
                                if r["_geo_code"] == "BR" and r["_race"] == "nao_negras"
                                and r["_family"] == "chefe"), None)
    wage_chefe_negras    = fam_negra_chefe.get("wage_mean_brl") if fam_negra_chefe else None
    wage_chefe_nao_negras = fam_nao_negra_chefe.get("wage_mean_brl") if fam_nao_negra_chefe else None
    chefe_wage_gap_pct = None
    if wage_chefe_negras and wage_chefe_nao_negras:
        chefe_wage_gap_pct = round(100 * wage_chefe_negras / wage_chefe_nao_negras, 1)

    # ---- age cohorts (fact_age, Theme 2) ----
    age_rows = build_age_rows(df, period)
    # Diagnostic: % under_29 for the category overall — DIEESE Apr/2026 reports 12%.
    age_total_under29 = next((r for r in age_rows
                              if r["_geo_code"] == "BR" and r["_race"] == "total"
                              and r["_age_band"] == "under_29"), None)
    pct_under29_total = age_total_under29["pct_within_race"] if age_total_under29 else None
    age_negra_under29 = next((r for r in age_rows
                              if r["_geo_code"] == "BR" and r["_race"] == "preta_parda"
                              and r["_age_band"] == "under_29"), None)
    pct_under29_negras = age_negra_under29["pct_within_race"] if age_negra_under29 else None

    # ---- contract type (fact_contract, Mayer DiD hypothesis) ----
    contract_rows = build_contract_rows(df, period)
    # Diagnostic: % diarista for total race and for negras (both)
    ct_total_dia = next((r for r in contract_rows
                         if r["_geo_code"] == "BR" and r["_race"] == "total"
                         and r["_contract"] == "diarista" and r["_formality"] == "total"), None)
    pct_diarista_total = ct_total_dia["pct_within_race"] if ct_total_dia else None
    ct_negra_dia = next((r for r in contract_rows
                         if r["_geo_code"] == "BR" and r["_race"] == "preta_parda"
                         and r["_contract"] == "diarista" and r["_formality"] == "total"), None)
    pct_diarista_negras = ct_negra_dia["pct_within_race"] if ct_negra_dia else None

    # NOTE: housing (D3) is NOT computed here — see etl/pnadc_annual_housing.py.
    # V0212 is in PNADC ANNUAL, not quarterly.

    # ---- wages (fact_wages) ----
    wage_rows = build_wage_rows(df, period)
    wage_negras = next((r for r in wage_rows
                        if r["_race"] == "preta_parda" and r["_formality"] == "total"), None)
    wage_nao_negras = next((r for r in wage_rows
                            if r["_race"] == "nao_negras" and r["_formality"] == "total"), None)
    wage_gap_pct = None
    if wage_negras and wage_nao_negras and wage_nao_negras["mean_wage_brl_real"]:
        wage_gap_pct = round(100 * wage_negras["mean_wage_brl_real"] / wage_nao_negras["mean_wage_brl_real"], 1)

    if upsert:
        inserted_workers = upsert_to_supabase(rows)
        inserted_wages = upsert_wages_to_supabase(wage_rows)
        inserted_hours = upsert_hours_to_supabase(hours_rows)
        inserted_prev = upsert_prev_to_supabase(prev_rows)
        inserted_edu = upsert_education_to_supabase(edu_rows)
        inserted_fam = upsert_family_to_supabase(fam_rows)
        inserted_age = upsert_age_to_supabase(age_rows)
        inserted_ct = upsert_contract_to_supabase(contract_rows)
        inserted_aut = upsert_autonomous_to_supabase(autonomous_rows)
        log.info("[%s] upserted %d work + %d wage + %d hour + %d prev + %d edu + %d fam + %d age + %d ct + %d aut · "
                 "total %.0fk · pretas+pardas %s%% (BR) %s%% (SP) · mulheres %s%% · "
                 "wage gap %s%% · horas méd %s · %% previdência %s%% · "
                 "%% fund_inc (negras) %s%% · %% chefe (total/negras) %s%%/%s%% · "
                 "wage chefes negras R$%s vs n.negras R$%s (gap %s%%) · "
                 "%% under_29 (total/negras) %s%%/%s%% · "
                 "%% diarista (total/negras) %s%%/%s%% · "
                 "%% conta-própria com CNPJ %s%%",
                 period, inserted_workers, inserted_wages, inserted_hours, inserted_prev,
                 inserted_edu, inserted_fam, inserted_age, inserted_ct, inserted_aut,
                 n_dom, pct_negras, pct_negras_sp, pct_mulheres, wage_gap_pct,
                 mean_hours, pct_prev_total, pct_fund_inc_negras,
                 pct_chefe_total, pct_chefe_negras,
                 wage_chefe_negras, wage_chefe_nao_negras, chefe_wage_gap_pct,
                 pct_under29_total, pct_under29_negras,
                 pct_diarista_total, pct_diarista_negras,
                 pct_cp_cnpj)
    else:
        log.info("[%s] (dry run) %d work + %d wage + %d hour + %d prev + %d edu + %d fam + %d age + %d ct + %d aut · "
                 "total %.0fk · pretas+pardas %s%% (BR) %s%% (SP) · mulheres %s%% · "
                 "wage gap %s%% · horas méd %s · %% previdência %s%% · "
                 "%% fund_inc (negras) %s%% · %% chefe (total/negras) %s%%/%s%% · "
                 "wage chefes negras R$%s vs n.negras R$%s (gap %s%%) · "
                 "%% under_29 (total/negras) %s%%/%s%% · "
                 "%% diarista (total/negras) %s%%/%s%% · "
                 "%% conta-própria com CNPJ %s%%",
                 period, len(rows), len(wage_rows), len(hours_rows), len(prev_rows),
                 len(edu_rows), len(fam_rows), len(age_rows), len(contract_rows), len(autonomous_rows),
                 n_dom, pct_negras, pct_negras_sp, pct_mulheres, wage_gap_pct,
                 mean_hours, pct_prev_total, pct_fund_inc_negras,
                 pct_chefe_total, pct_chefe_negras,
                 wage_chefe_negras, wage_chefe_nao_negras, chefe_wage_gap_pct,
                 pct_under29_total, pct_under29_negras,
                 pct_diarista_total, pct_diarista_negras,
                 pct_cp_cnpj)

    return {"period": period, "total_workers_k": n_dom, "pct_negras": pct_negras,
            "pct_negras_sp": pct_negras_sp, "pct_mulheres": pct_mulheres,
            "wage_gap_pct": wage_gap_pct,
            "mean_hours": mean_hours, "pct_prev": pct_prev_total,
            "pct_fund_inc_negras": pct_fund_inc_negras,
            "pct_chefe_total": pct_chefe_total,
            "pct_chefe_negras": pct_chefe_negras,
            "wage_chefe_negras": wage_chefe_negras,
            "wage_chefe_nao_negras": wage_chefe_nao_negras,
            "chefe_wage_gap_pct": chefe_wage_gap_pct,
            "pct_under29_total": pct_under29_total,
            "pct_under29_negras": pct_under29_negras,
            "pct_diarista_total": pct_diarista_total,
            "pct_diarista_negras": pct_diarista_negras}


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
            gap = r.get("wage_gap_pct"); gap_s = f"{gap:.1f}%" if gap is not None else "—"
            mul = r.get("pct_mulheres"); mul_s = f"{mul:.1f}%" if mul is not None else "—"
            sp = r.get("pct_negras_sp"); sp_s = f"{sp:.1f}%" if sp is not None else "—"
            mh = r.get("mean_hours"); mh_s = f"{mh:.1f}h" if mh is not None else "—"
            pv = r.get("pct_prev"); pv_s = f"{pv:.1f}%" if pv is not None else "—"
            print(f"  {r['period']}  total {r['total_workers_k']:>5.0f}k"
                  f"  · pretas+pardas BR {r['pct_negras']}% / SP {sp_s}"
                  f"  · mulheres {mul_s}  · wage gap {gap_s}"
                  f"  · jornada {mh_s}  · prev {pv_s}")
    print("======================================\n")
    n_ok = sum(1 for r in summary if "error" not in r)
    n_fail = len(summary) - n_ok
    log.info("backfill complete: %d ok, %d failed", n_ok, n_fail)


if __name__ == "__main__":
    main()
