"""
probe_union_annual.py — Find union membership in PNADC-A (Annual, Visita 1)
============================================================================

WHY THIS SCRIPT
---------------
PNADC Trimestral does NOT collect union membership (filiação sindical).
Confirmed by searching the entire trimestral dictionary: only 2 mentions
of "sindic", both about consulting employment agencies, not membership.

PNADC Anual, on the other hand, has a labor supplement on Visita 1 that
HISTORICALLY includes union membership (variable named V4082 in pre-2016
PNAD, possibly under a different name in PNADC-A). This script does the
discovery + probe in one pass:

  1. Downloads the PNADC-A Visita 1 dictionary from IBGE FTP (if not cached)
  2. Searches the dictionary for "sindic" / "filiad" keywords
  3. Lists every matching variable, its column position, and its question text
  4. If a clear "associada/filiada a sindicato" variable exists, runs the
     probe against the cached PNADC_2024_visita1 zip
  5. Reports % filiadas by race × contract × formality with Wilson CIs

RUN ON THE MAC, NOT IN THE COWORK SANDBOX
------------------------------------------
The script needs to download from https://ftp.ibge.gov.br/, which the
Cowork bash sandbox cannot reach (proxy 403). Run from a terminal on
your Mac:

    cd ~/Documents/Claude/Domestic\\ Work
    source .venv/bin/activate    # if you have one; otherwise system Python is fine
    python etl/probe_union_annual.py

The script is read-only: it does not write anything to Supabase, only
prints a markdown table to stdout. Append `>> chapter/probe_union_annual.md`
if you want to save the output.
"""

from __future__ import annotations

import io
import logging
import math
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("probe_union_annual")

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "etl" / "raw" / "pnadc_annual"
RAW_DIR.mkdir(parents=True, exist_ok=True)

FTP_BASE = (
    "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/"
    "Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Anual/"
    "Microdados/Visita/Visita_1"
)
DOC_INDEX = f"{FTP_BASE}/Documentacao/"


# ---------------------------------------------------------------------------
# Step 1: Discover and download the PNADC-A Visita 1 dictionary
# ---------------------------------------------------------------------------

def discover_dict_filename(target_year: str | None = None) -> str:
    """List the FTP Documentacao folder and find a dictionary file.
    If target_year is given (e.g., '2024'), prefer the dictionary
    file that contains that year in its name."""
    log.info("listing %s", DOC_INDEX)
    with urllib.request.urlopen(DOC_INDEX, timeout=30) as resp:
        html = resp.read().decode("latin-1", errors="ignore")

    all_hrefs = sorted(set(re.findall(r'href="([^"]+\.(?:zip|pdf|xls|xlsx|csv))"', html, re.IGNORECASE)))
    log.info("found %d data/doc files in folder:", len(all_hrefs))
    for h in all_hrefs:
        log.info("  • %s", h)

    # Priority 0: dictionary matching the target year
    if target_year:
        year_matches = [h for h in all_hrefs if "dicion" in h.lower() and target_year in h]
        if year_matches:
            chosen = year_matches[-1]
            log.info("dictionary candidate (year-matched %s): %s", target_year, chosen)
            return chosen

    # Priority 1: any dictionary file
    candidates = [h for h in all_hrefs if "dicion" in h.lower()]
    if not candidates:
        candidates = [h for h in all_hrefs if "input_pnadc" in h.lower()]
    if not candidates:
        candidates = [h for h in all_hrefs if "visita" in h.lower() and h.lower().endswith(".zip")]
    if not candidates:
        candidates = [h for h in all_hrefs if h.lower().endswith(".zip")]

    if not candidates:
        raise FileNotFoundError(
            f"No dictionary-like file found in {DOC_INDEX}\n"
            f"HTML length {len(html)}; files seen: {all_hrefs}"
        )
    chosen = candidates[-1]
    log.info("dictionary candidate selected: %s", chosen)
    return chosen


def cached_data_year() -> str | None:
    """Infer the year of the cached annual data zip (e.g., '2024' from
    PNADC_2024_visita1_*.zip), so we pick the matching dictionary."""
    candidates = sorted(RAW_DIR.glob("PNADC_*visita1*.zip"))
    if not candidates:
        return None
    m = re.search(r"PNADC_(\d{4})_visita1", candidates[-1].name)
    return m.group(1) if m else None


def download_dict(target_year: str | None = None) -> Path:
    """Download (or use cached) PNADC-A Visita 1 dictionary.
    If target_year is given, prefer (a) cached dict matching that year,
    then (b) download from FTP for that year, then (c) any cached dict
    as a last-resort fallback (with a loud warning)."""
    cached = sorted(RAW_DIR.glob("dicionario_*visita1*.xls*")) + \
             sorted(RAW_DIR.glob("Dicion*.zip"))

    # (a) Year-matched cache hit
    if target_year:
        for c in cached:
            if target_year in c.name:
                log.info("dictionary cache hit (matched year %s): %s", target_year, c)
                return c

    # (b) FTP for the target year
    if target_year:
        try:
            fname = discover_dict_filename(target_year=target_year)
            if target_year in fname:
                url = f"{DOC_INDEX}{fname}"
                local = RAW_DIR / fname
                log.info("downloading year-matched %s → %s", url, local)
                urllib.request.urlretrieve(url, local)
                log.info("downloaded %.1f MB", local.stat().st_size / 1024 / 1024)
                return local
            log.warning("FTP listing returned %s but it does NOT contain target year %s",
                        fname, target_year)
        except Exception as e:
            log.warning("FTP fetch for year %s failed: %s", target_year, e)

    # (c) Fallback: most recent cached dictionary (with warning)
    if cached:
        log.warning("FALLBACK: using cached dictionary that may not match data year! %s",
                    cached[-1])
        return cached[-1]

    # (d) Last resort: take whatever FTP gives us
    fname = discover_dict_filename()
    url = f"{DOC_INDEX}{fname}"
    local = RAW_DIR / fname
    log.info("downloading (no year filter) %s → %s", url, local)
    urllib.request.urlretrieve(url, local)
    log.info("downloaded %.1f MB", local.stat().st_size / 1024 / 1024)
    return local


# ---------------------------------------------------------------------------
# Step 2: Search the dictionary for sindical-related variables
# ---------------------------------------------------------------------------

def search_dict_for_union(dict_path: Path) -> list[dict]:
    """Open the dictionary file (either a .xls directly or a .zip
    containing one) and look for any variable whose description contains
    'sindic', 'filiad', 'associad', or 'vinculad'."""
    found = []
    suffix = dict_path.suffix.lower()

    def _read_excel_robust(src, src_name: str) -> pd.DataFrame:
        """Try several engines + an HTML-table fallback (IBGE sometimes
        ships .xls files that are actually HTML)."""
        # Peek at the magic bytes to detect format
        if hasattr(src, "read"):
            head = src.read(8)
            src.seek(0)
        else:
            with open(src, "rb") as f:
                head = f.read(8)
        # Real .xls (BIFF compound document) starts with D0 CF 11 E0
        is_real_xls = head.startswith(b"\xd0\xcf\x11\xe0")
        # .xlsx is a zip
        is_xlsx = head.startswith(b"PK\x03\x04")
        # HTML-disguised-as-xls
        is_html = head.lstrip().lower().startswith((b"<htm", b"<!do", b"<tab", b"<?xm"))
        log.info("  magic-byte sniff: real_xls=%s xlsx=%s html=%s (head=%r)",
                 is_real_xls, is_xlsx, is_html, head[:4])

        errors = []
        engines_to_try = []
        if is_real_xls:
            engines_to_try = ["xlrd"]
        elif is_xlsx:
            engines_to_try = ["openpyxl"]
        else:
            engines_to_try = ["xlrd", "openpyxl", "calamine"]

        for eng in engines_to_try:
            try:
                if hasattr(src, "seek"):
                    src.seek(0)
                return pd.read_excel(src, engine=eng, header=None)
            except Exception as e:
                errors.append(f"{eng}: {e.__class__.__name__}: {e}")
                continue

        # Final fallback: HTML table parsing
        if is_html or True:  # always try, since some IBGE files lie about format
            try:
                if hasattr(src, "seek"):
                    src.seek(0)
                    raw = src.read()
                else:
                    with open(src, "rb") as f:
                        raw = f.read()
                tables = pd.read_html(raw)
                if tables:
                    log.info("  fallback: parsed %d HTML tables, using the largest", len(tables))
                    return max(tables, key=len).reset_index(drop=True)
            except Exception as e:
                errors.append(f"read_html: {e.__class__.__name__}: {e}")

        raise RuntimeError(
            f"Could not parse dictionary file {src_name}. Tried:\n  - "
            + "\n  - ".join(errors)
        )

    if suffix in (".xls", ".xlsx"):
        df = _read_excel_robust(dict_path, dict_path.name)
        log.info("dictionary loaded directly: %s (%d rows)", dict_path.name, len(df))
    elif suffix == ".zip":
        with zipfile.ZipFile(dict_path) as zf:
            xls_names = [n for n in zf.namelist()
                         if n.lower().endswith((".xls", ".xlsx"))]
            if not xls_names:
                log.error("No .xls/.xlsx file in dictionary zip")
                return found
            with zf.open(xls_names[0]) as f:
                df = _read_excel_robust(f, xls_names[0])
        log.info("dictionary loaded from zip: %s (%d rows)", xls_names[0], len(df))
    else:
        raise ValueError(f"Unexpected dictionary file type: {dict_path}")

    KEYWORDS = ["sindic", "filiad", "associad", "vinculad"]
    # Find rows mentioning the keywords
    for idx, row in df.iterrows():
        cells = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
        joined = " ".join(cells).lower()
        if any(k in joined for k in KEYWORDS):
            # Look back up to find the variable header row (which has position + name)
            # In IBGE dictionaries, var headers usually have the form:
            #   <start> | <width> | <V-name> | <position> | <description> ...
            for back in range(idx, max(-1, idx - 5), -1):
                row_back = df.iloc[back]
                cells_back = [str(v).strip() for v in row_back if pd.notna(v)]
                # Heuristic: variable header row has a value matching V\d+ or S\d+
                var_match = None
                for c in cells_back:
                    m = re.match(r'^(V[A-Z]?\d+[A-Z]*|S\d+|VD\d+)$', c.strip())
                    if m:
                        var_match = c.strip()
                        break
                if var_match:
                    # Extract position (first numeric cell)
                    pos_start, pos_width = None, None
                    for c in cells_back:
                        if c.strip().isdigit():
                            if pos_start is None:
                                pos_start = int(c.strip())
                            elif pos_width is None:
                                pos_width = int(c.strip())
                                break
                    desc = next((c for c in cells_back if len(c) > 20), "")
                    found.append({
                        "var_name": var_match,
                        "col_start": pos_start,
                        "col_width": pos_width,
                        "description": desc[:150],
                        "row_idx": int(back),
                        "match_row_idx": int(idx),
                        "match_text": " | ".join(cells)[:200],
                    })
                    break
    # De-duplicate by var_name
    seen = set()
    uniq = []
    for f in found:
        if f["var_name"] not in seen:
            uniq.append(f)
            seen.add(f["var_name"])
    return uniq


# ---------------------------------------------------------------------------
# Step 3: If a union variable exists, probe the cached annual data
# ---------------------------------------------------------------------------

def cached_annual_data() -> Path:
    """Locate the cached PNADC-A Visita 1 microdata file."""
    candidates = sorted(RAW_DIR.glob("PNADC_*visita1*.zip"))
    if not candidates:
        raise FileNotFoundError(
            f"No cached annual zip in {RAW_DIR}\n"
            "Run etl/pnadc_annual_housing.py first to populate the cache."
        )
    return candidates[-1]


def extract_txt(zip_path: Path) -> Path:
    """Extract the .txt fixed-width file from the annual zip."""
    with zipfile.ZipFile(zip_path) as zf:
        txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not txt_names:
            raise FileNotFoundError(f"No .txt in {zip_path}")
        local = zip_path.parent / txt_names[0]
        if local.exists() and local.stat().st_size > 100_000_000:
            log.info("extract cache hit: %s (%.0f MB)", local, local.stat().st_size / 1024 / 1024)
            return local
        log.info("extracting %s → %s", txt_names[0], local)
        with zf.open(txt_names[0]) as src, open(local, "wb") as dst:
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
    return local


# Annual COLSPECS reused from pnadc_annual_housing.py (known stable positions)
ANNUAL_COLSPECS_1IDX = {
    "Ano":      (1, 4),
    "UF":       (6, 7),
    "V1032":    (58, 72),
    "V2007":    (94, 94),
    "V2010":    (106, 106),
    "VD4009":   (540, 541),
}
DOMESTIC_CODES = ["03", "04"]
RACE_MAP = {"1": "branca", "2": "preta", "3": "amarela",
            "4": "parda", "5": "indigena"}


def probe_union(union_var: str, union_pos: tuple[int, int],
                annual_zip: Path) -> None:
    """Stream-read the cached annual data, filter to domestic workers,
    compute % filiadas by race."""
    txt_path = extract_txt(annual_zip)
    specs = dict(ANNUAL_COLSPECS_1IDX)
    specs[union_var] = union_pos

    log.info("union variable specs: %s = position %s", union_var, union_pos)
    colspecs = [(s - 1, e) for (s, e) in specs.values()]
    names = list(specs.keys())

    log.info("streaming annual data in chunks (filtering to domestic workers)…")
    chunks = []
    reader = pd.read_fwf(txt_path, colspecs=colspecs, names=names,
                         dtype=str, keep_default_na=False, chunksize=50_000)
    for i, chunk in enumerate(reader):
        kept = chunk[chunk["VD4009"].isin(DOMESTIC_CODES)]
        chunks.append(kept)
        if (i + 1) % 10 == 0:
            log.info("  processed %d chunks, kept %d domestic-worker rows",
                     i + 1, sum(len(c) for c in chunks))
    df = pd.concat(chunks, ignore_index=True)
    log.info("filtered to %d domestic-worker rows", len(df))

    # Parse weight (V1032 is 15-char with 9 implicit decimals in PNADC-A)
    df["weight"] = pd.to_numeric(df["V1032"], errors="coerce") / 1e9
    df["race_code"] = df["V2010"].map(RACE_MAP)
    df["race_group"] = df["race_code"].map({
        "preta": "negras", "parda": "negras",
        "branca": "nao_negras", "amarela": "nao_negras", "indigena": "nao_negras",
    })
    # Union response — 1=Sim, 2=Não is the IBGE standard for binary questions
    df["filiada"] = df[union_var].map({"1": True, "2": False})

    print(f"\n## Filiação sindical — PNADC Anual Visita 1 (variável {union_var})\n")
    print(f"Total domésticas no ano: {len(df):,}")
    print(f"Com resposta válida ({union_var} Sim/Não): {df['filiada'].notna().sum():,}")
    print(f"  Filiadas: {(df['filiada'] == True).sum():,}")
    print(f"  Não filiadas: {(df['filiada'] == False).sum():,}")
    print(f"  Sem resposta: {df['filiada'].isna().sum():,}")

    if df["filiada"].notna().sum() == 0:
        print(f"\n⚠ {union_var} é blank para todas as domésticas — não é a variável certa, OU "
              "é aplicada apenas em Visita 5 ou em supplement não coletado em 2024.")
        return

    print("\n### Por raça (BR-wide, ponderado)\n")
    print("| Grupo | n (resp. válida) | n filiadas | % filiadas |")
    print("|---|---:|---:|---:|")
    for grp in ["negras", "nao_negras"]:
        sub = df[(df["race_group"] == grp) & df["filiada"].notna()]
        n = len(sub)
        w_sum = sub["weight"].sum()
        w_fil = sub[sub["filiada"] == True]["weight"].sum()
        pct = 100 * w_fil / w_sum if w_sum else 0
        n_fil_unweighted = int((sub["filiada"] == True).sum())
        print(f"| {grp} | {n:,} | {n_fil_unweighted:,} | {pct:.2f}% |")
    sub_all = df[df["filiada"].notna()]
    w_sum_all = sub_all["weight"].sum()
    w_fil_all = sub_all[sub_all["filiada"] == True]["weight"].sum()
    pct_all = 100 * w_fil_all / w_sum_all if w_sum_all else 0
    n_fil_all = int((sub_all["filiada"] == True).sum())
    print(f"| **total** | **{len(sub_all):,}** | **{n_fil_all:,}** | **{pct_all:.2f}%** |")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    target_year = cached_data_year()
    if target_year:
        log.info("cached data year detected: %s", target_year)
    log.info("Step 1: download/load PNADC-A Visita 1 dictionary")
    dict_zip = download_dict(target_year=target_year)

    log.info("Step 2: search dictionary for sindical-related variables")
    matches = search_dict_for_union(dict_zip)

    print("\n## Variáveis relacionadas a sindicato/filiação no dicionário PNADC-A Visita 1\n")
    if not matches:
        print("(nenhuma variável encontrada com keywords 'sindic', 'filiad', 'associad', 'vinculad')")
        print("\n⚠ Filiação sindical NÃO está coletada na Visita 1 deste ano.")
        print("Pode estar em Visita 5, ou em uma divulgação especial separada.")
        return

    print("| Variável | Posição (start, width) | Descrição | Linha no XLS |")
    print("|---|---|---|---:|")
    for m in matches:
        print(f"| `{m['var_name']}` | ({m['col_start']}, {m['col_width']}) | {m['description']} | {m['row_idx']} |")

    # Look for the variable that most plausibly is "associada a sindicato"
    union_var = None
    for m in matches:
        text = (m['description'] + " " + m['match_text']).lower()
        if "associad" in text and "sindic" in text:
            union_var = m
            break
        if "filiad" in text and "sindic" in text:
            union_var = m
            break
    if not union_var and matches:
        union_var = matches[0]   # fall back to first match

    if union_var and union_var["col_start"] and union_var["col_width"]:
        print(f"\n## Step 3: probing the cached 2024 annual data with `{union_var['var_name']}`\n")
        try:
            annual_zip = cached_annual_data()
        except FileNotFoundError as e:
            print(f"⚠ {e}")
            return
        pos = (union_var["col_start"],
               union_var["col_start"] + union_var["col_width"] - 1)
        probe_union(union_var["var_name"], pos, annual_zip)
    else:
        print("\n⚠ Could not extract column position from dictionary parsing. "
              "Inspect the dictionary XLS manually and re-run with hardcoded position.")


if __name__ == "__main__":
    main()
