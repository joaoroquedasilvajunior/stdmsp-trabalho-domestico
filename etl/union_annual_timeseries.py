"""
union_annual_timeseries.py — V4097 filiação sindical, PNADC-A 2012–2024
========================================================================

Pipeline multi-ano para a série temporal de filiação sindical das
trabalhadoras domésticas. Para cada ano disponível do PNADC Anual
Visita 1, baixa (com cache) o dicionário ano-casado, extrai posições
fixas das variáveis-chave (V4097, V2010, V1032, VD4009), baixa (com
cache) os microdados, filtra para domésticas (VD4009 ∈ {"03","04"}),
e produz:

  - série temporal nacional ponderada (% filiadas / ano)
  - série por grupo racial (negras / não-negras)
  - série por formalidade (com_carteira / sem_carteira)

Saídas:
  - dashboard/data/fact_union_timeseries.csv   linha por (ano, grupo)
  - chapter/fact_union_summary.md              tabela resumo legível
  - logs detalhados em chapter/union_timeseries_log.txt (via tee)

USAGE
-----
    python etl/union_annual_timeseries.py

YEARS TO PROCESS
----------------
Edita YEARS abaixo. Anos PNADC-A V1 disponíveis no FTP IBGE:
  2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024
(IBGE pulou 2020/2021 por interrupção de campo COVID; 2025 já tem
dicionário publicado mas microdados podem não estar prontos.)

DESIGN NOTES
------------
- Posições de coluna podem variar entre dicionários ano a ano,
  então parseamos cada dicionário separadamente em vez de assumir
  uma layout fixa. As variáveis-alvo são fixas (V4097 etc.).
- O cache local em etl/raw/pnadc_annual/ é a fonte da verdade.
  Cada zip de microdado é ~150-200 MB, dicionário <1 MB.
- O parse SAS-style dos dicionários PNADC-A é mais frágil que o
  trimestral: o XLS é uma tabela com "Ord", "Posição", "Tamanho",
  "Nome", "Descrição". Localizamos linhas por nome de variável
  (V4097) e lemos as colunas adjacentes.
"""

from __future__ import annotations

import logging
import math
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("union_ts")


ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "etl" / "raw" / "pnadc_annual"
RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_DATA = ROOT / "dashboard" / "data"
OUT_DATA.mkdir(parents=True, exist_ok=True)
OUT_SUMMARY = ROOT / "chapter" / "fact_union_summary.md"


FTP_BASE = ("https://ftp.ibge.gov.br/Trabalho_e_Rendimento/"
            "Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/"
            "Anual/Microdados/Visita/Visita_1")
DOC_INDEX = FTP_BASE + "/Documentacao/"
DATA_INDEX = FTP_BASE + "/Dados/"
HTTP_HEADERS = {"User-Agent": "stdmsp-etl/1.0"}

YEARS = [2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024]
# UF added 2026-06-22 for the SP × BR comparative panel in the Mayer chapter.
# Cache will auto-invalidate because the var set grew.
TARGET_VARS = ["V4097", "V2010", "V1032", "VD4009", "UF"]
DOMESTIC_CODES = ["03", "04"]

RACE_MAP = {"1": "branca", "2": "preta", "3": "amarela", "4": "parda", "5": "indigena"}
FORMALITY_MAP = {"03": "com_carteira", "04": "sem_carteira"}

# IBGE UF codes (2-char, zero-padded)
UF_CODES = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}


# ---------------------------------------------------------------------------
# Dictionary download + parsing
# ---------------------------------------------------------------------------

_DICT_YEAR_RE = re.compile(r"microdados_(\d{4})(?:_a_(\d{4}))?_visita1", re.IGNORECASE)


def _dict_filename_matches_year(fname: str, year: int) -> bool:
    """Parse the reference-year(s) out of a PNADC dictionary filename
    (e.g., 'dicionario_PNADC_microdados_2012_a_2014_visita1_20220224.xls'
    → covers 2012-2014). Returns True if `year` is in the covered range.
    Ignores the trailing release-date suffix entirely."""
    m = _DICT_YEAR_RE.search(fname)
    if not m:
        return False
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    return start <= year <= end


def discover_year_dict(year: int) -> str | None:
    """List FTP Documentacao/ and find the dictionary file for `year`,
    parsing the year reference out of the filename (NOT the release date)."""
    log.info("[%d] listing %s", year, DOC_INDEX)
    try:
        req = urllib.request.Request(DOC_INDEX, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("latin-1", errors="ignore")
    except Exception as e:
        log.error("[%d] FTP listing failed: %s", year, e)
        return None
    all_hrefs = re.findall(r'href="([^"]+\.xls)"', html, re.IGNORECASE)
    for href in all_hrefs:
        if "dicion" in href.lower() and _dict_filename_matches_year(href, year):
            return href
    return None


def get_dict_path(year: int) -> Path | None:
    """Return a Path to the dictionary for `year`, downloading if needed.
    Uses filename year-reference parsing (NOT substring match), so the
    release-date suffix (e.g. '_20220224') can't fool us."""
    cached = sorted(RAW_DIR.glob("dicionario_*visita1*.xls*"))
    for c in cached:
        if _dict_filename_matches_year(c.name, year):
            log.info("[%d] dict cache hit: %s", year, c.name)
            return c

    fname = discover_year_dict(year)
    if fname is None:
        log.error("[%d] no dictionary found in FTP listing", year)
        return None
    url = DOC_INDEX + fname
    local = RAW_DIR / fname
    log.info("[%d] downloading dict %s → %s", year, url, local)
    try:
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r, open(local, "wb") as f:
            f.write(r.read())
        log.info("[%d] downloaded %.1f MB", year, local.stat().st_size / 1024 / 1024)
        return local
    except Exception as e:
        log.error("[%d] dict download failed: %s", year, e)
        return None


def read_xls_robust(src) -> pd.DataFrame:
    """Read .xls / .xlsx with format sniffing + HTML fallback."""
    if hasattr(src, "read"):
        head = src.read(8); src.seek(0)
    else:
        with open(src, "rb") as f:
            head = f.read(8)
    is_xls = head.startswith(b"\xd0\xcf\x11\xe0")
    is_xlsx = head.startswith(b"PK\x03\x04")
    is_html = head.lstrip().lower().startswith((b"<htm", b"<!do", b"<tab", b"<?xm"))
    engines = ["xlrd"] if is_xls else (["openpyxl"] if is_xlsx else ["xlrd", "openpyxl"])
    last_err = None
    for eng in engines:
        try:
            if hasattr(src, "seek"): src.seek(0)
            return pd.read_excel(src, engine=eng, header=None)
        except Exception as e:
            last_err = e
    # HTML fallback
    try:
        if hasattr(src, "seek"):
            src.seek(0); raw = src.read()
        else:
            with open(src, "rb") as f: raw = f.read()
        tables = pd.read_html(raw)
        if tables:
            return max(tables, key=len).reset_index(drop=True)
    except Exception as e:
        last_err = e
    raise RuntimeError(f"read_xls_robust failed: {last_err}")


def parse_var_positions(dict_df: pd.DataFrame, var_names: list[str]) -> dict[str, tuple[int, int]]:
    """For each variable name in `var_names`, find its row in the
    dictionary XLS and return (start_pos, width). PNADC dicts have
    Posição (start, 1-indexed) and Tamanho (width)."""
    # Heuristic: scan all cells, find one matching exact var name,
    # then read numeric cells from the same row.
    positions = {}
    rows = dict_df.values
    for var in var_names:
        for r_idx in range(len(rows)):
            row = rows[r_idx]
            for c_idx, cell in enumerate(row):
                if pd.isna(cell):
                    continue
                if str(cell).strip().upper() == var.upper():
                    # Read numeric cells in the same row
                    nums = []
                    for c2 in row:
                        if pd.isna(c2):
                            continue
                        try:
                            n = int(float(str(c2).strip()))
                            nums.append(n)
                        except (ValueError, TypeError):
                            pass
                    if len(nums) >= 2:
                        # The two smallest plausible numbers are usually
                        # (Posição, Tamanho). They appear in order in PNADC dicts.
                        # Heuristic: pick the first two ints that look like (start, width).
                        start, width = nums[0], nums[1]
                        if 1 <= start <= 1500 and 1 <= width <= 30:
                            positions[var] = (start, width)
                            break
            if var in positions:
                break
        if var not in positions:
            log.warning("variable %s not found in dictionary", var)
    return positions


# ---------------------------------------------------------------------------
# Microdata download
# ---------------------------------------------------------------------------

_data_listing_cache = None  # one-shot scrape of Dados/ listing


def _get_data_listing_html() -> str:
    """Fetch the flat Dados/ index once and cache for the run."""
    global _data_listing_cache
    if _data_listing_cache is not None:
        return _data_listing_cache
    log.info("scraping data index %s", DATA_INDEX)
    req = urllib.request.Request(DATA_INDEX, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        _data_listing_cache = r.read().decode("iso-8859-1", errors="replace")
    return _data_listing_cache


def discover_year_data(year: int) -> str | None:
    """Find the latest PNADC_<year>_visita1_*.zip filename in the
    flat Dados/ folder."""
    try:
        html = _get_data_listing_html()
    except Exception as e:
        log.error("[%d] data listing failed: %s", year, e)
        return None
    pattern = re.compile(rf"PNADC_{year}_visita1_(\d{{8}})\.zip", re.IGNORECASE)
    matches = set(pattern.findall(html))
    if not matches:
        return None
    latest = sorted(matches)[-1]
    return f"PNADC_{year}_visita1_{latest}.zip"


def get_data_path(year: int) -> Path | None:
    cached = sorted(RAW_DIR.glob(f"PNADC_{year}_visita1*.zip"))
    if cached:
        log.info("[%d] data cache hit: %s", year, cached[-1].name)
        return cached[-1]
    fname = discover_year_data(year)
    if fname is None:
        log.error("[%d] no data zip found", year)
        return None
    url = DATA_INDEX + fname
    local = RAW_DIR / fname
    log.info("[%d] downloading data %s → %s (this may take a while)", year, url, local)
    try:
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=900) as r, open(local, "wb") as f:
            chunk_size = 1024 * 1024
            total = 0
            while True:
                chunk = r.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                if total % (40 * chunk_size) == 0:
                    log.info("[%d]   … %d MB downloaded", year, total // (1024 * 1024))
        log.info("[%d] downloaded %.1f MB", year, local.stat().st_size / 1024 / 1024)
        return local
    except Exception as e:
        log.error("[%d] data download failed: %s", year, e)
        return None


def open_txt_stream_from_zip(zip_path: Path):
    """Open the largest .txt inside the zip as a forward-only stream
    (no extraction to disk). Returns (zip_handle, stream) — caller is
    responsible for closing both, ideally via a context manager wrap.
    Streaming is critical: extracted .txt files are ~1 GB per year and
    fill the disk quickly. pd.read_fwf works fine with the stream when
    iterated forward via chunksize."""
    zf = zipfile.ZipFile(zip_path)
    txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
    if not txt_names:
        zf.close()
        return None, None
    sizes = [(n, zf.getinfo(n).file_size) for n in txt_names]
    txt_name = max(sizes, key=lambda t: t[1])[0]
    log.info("streaming %s from %s (no disk extraction)", txt_name, zip_path.name)
    return zf, zf.open(txt_name)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def wilson_ci(p: float, n: int, z: float = 1.96):
    if n <= 0 or p is None or math.isnan(p):
        return (None, None)
    denom = 1 + (z * z) / n
    center = (p + (z * z) / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + (z * z) / (4 * n * n))) / denom
    return (100 * max(0, center - half), 100 * min(1, center + half))


def compute_cell(sub: pd.DataFrame) -> dict:
    valid = sub[sub["filiada"].notna()]
    n = len(valid)
    if n == 0:
        return {"n": 0, "n_filiadas_unw": 0, "pct_filiadas": None, "ci_lo": None, "ci_hi": None}
    w = valid["weight"]
    pct = 100 * valid.loc[valid["filiada"], "weight"].sum() / w.sum() if w.sum() else None
    p_unw = (valid["filiada"]).sum() / n
    lo, hi = wilson_ci(p_unw, n)
    return {
        "n": n,
        "n_filiadas_unw": int(valid["filiada"].sum()),
        "pct_filiadas": round(pct, 3) if pct is not None else None,
        "ci_lo": round(lo, 3) if lo is not None else None,
        "ci_hi": round(hi, 3) if hi is not None else None,
    }


# ---------------------------------------------------------------------------
# Per-year processing
# ---------------------------------------------------------------------------

def process_year(year: int) -> list[dict]:
    """Process one year, return a list of fact rows (one per cut)."""
    log.info("=" * 60)
    log.info("YEAR %d", year)
    log.info("=" * 60)

    dict_path = get_dict_path(year)
    if dict_path is None:
        return []
    try:
        if dict_path.suffix.lower() in (".xls", ".xlsx"):
            dict_df = read_xls_robust(dict_path)
        else:
            with zipfile.ZipFile(dict_path) as zf:
                xls_names = [n for n in zf.namelist() if n.lower().endswith((".xls", ".xlsx"))]
                with zf.open(xls_names[0]) as f:
                    dict_df = read_xls_robust(f)
    except Exception as e:
        log.error("[%d] dict parse failed: %s", year, e)
        return []

    positions = parse_var_positions(dict_df, TARGET_VARS)
    log.info("[%d] var positions: %s", year, positions)
    missing = [v for v in TARGET_VARS if v not in positions]
    if missing:
        log.error("[%d] missing required variables: %s — skipping year", year, missing)
        return []

    data_zip = get_data_path(year)
    if data_zip is None:
        return []

    colspecs = [(positions[v][0] - 1, positions[v][0] - 1 + positions[v][1]) for v in TARGET_VARS]
    names = TARGET_VARS

    zf, stream = open_txt_stream_from_zip(data_zip)
    if stream is None:
        log.error("[%d] no .txt inside zip %s", year, data_zip)
        return []
    chunks = []
    try:
        reader = pd.read_fwf(stream, colspecs=colspecs, names=names,
                             dtype=str, keep_default_na=False, chunksize=200_000,
                             encoding="latin-1")
        for i, chunk in enumerate(reader):
            kept = chunk[chunk["VD4009"].isin(DOMESTIC_CODES)]
            chunks.append(kept)
            if (i + 1) % 20 == 0:
                log.info("[%d]   %d chunks, %d domestic rows so far",
                         year, i + 1, sum(len(c) for c in chunks))
    finally:
        try: stream.close()
        except Exception: pass
        try: zf.close()
        except Exception: pass
    df = pd.concat(chunks, ignore_index=True)
    log.info("[%d] filtered %d domestic-worker rows", year, len(df))

    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1032"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
    df["filiada"] = df["V4097"].map({"1": True, "2": False})
    df["race"] = df["V2010"].map(RACE_MAP)
    df["race_group"] = df["race"].map({
        "preta": "negras", "parda": "negras",
        "branca": "nao_negras", "amarela": "nao_negras", "indigena": "nao_negras",
    })
    df["formality"] = df["VD4009"].map(FORMALITY_MAP)
    df["uf_code"] = df["UF"].astype(str).str.strip().str.zfill(2)
    df["uf_sigla"] = df["uf_code"].map(UF_CODES)

    rows = []
    # BR-WIDE cuts (unchanged from v1)
    s = compute_cell(df); s.update({"year": year, "cut": "overall", "group": "all"})
    rows.append(s)
    for grp in ["negras", "nao_negras"]:
        s = compute_cell(df[df["race_group"] == grp])
        s.update({"year": year, "cut": "race", "group": grp})
        rows.append(s)
    for form in ["com_carteira", "sem_carteira"]:
        s = compute_cell(df[df["formality"] == form])
        s.update({"year": year, "cut": "formality", "group": form})
        rows.append(s)
    for grp in ["negras", "nao_negras"]:
        for form in ["com_carteira", "sem_carteira"]:
            sub = df[(df["race_group"] == grp) & (df["formality"] == form)]
            s = compute_cell(sub)
            s.update({"year": year, "cut": "race_x_formality", "group": f"{grp}_{form}"})
            rows.append(s)

    # NEW: UF × overall (all 27 UFs)
    for uf_code, uf_sigla in UF_CODES.items():
        sub = df[df["uf_code"] == uf_code]
        if len(sub) < 30:    # too thin even for total
            continue
        s = compute_cell(sub)
        s.update({"year": year, "cut": "uf_overall", "group": uf_sigla})
        rows.append(s)

    # NEW: SP-specific cross-tabs (sample is large enough for SP)
    sp = df[df["uf_code"] == "35"]
    if len(sp) >= 30:
        # SP overall is redundant with uf_overall above but useful to flag
        # SP × race
        for grp in ["negras", "nao_negras"]:
            sub = sp[sp["race_group"] == grp]
            if len(sub) >= 30:
                s = compute_cell(sub)
                s.update({"year": year, "cut": "sp_race", "group": grp})
                rows.append(s)
        # SP × formality
        for form in ["com_carteira", "sem_carteira"]:
            sub = sp[sp["formality"] == form]
            if len(sub) >= 30:
                s = compute_cell(sub)
                s.update({"year": year, "cut": "sp_formality", "group": form})
                rows.append(s)
        # SP × race × formality (likely thin but emit anyway with n<30 nulled)
        for grp in ["negras", "nao_negras"]:
            for form in ["com_carteira", "sem_carteira"]:
                sub = sp[(sp["race_group"] == grp) & (sp["formality"] == form)]
                if len(sub) >= 15:   # lower threshold for this 4-way cut
                    s = compute_cell(sub)
                    s.update({"year": year, "cut": "sp_race_x_formality",
                              "group": f"{grp}_{form}"})
                    rows.append(s)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("PNADC-A V4097 time series — %d years to process", len(YEARS))

    # Incremental CSV: write rows as each year finishes so partial runs
    # don't lose progress. If the file already exists, we append; we also
    # remember which years are already in it so we don't reprocess them.
    out_csv = OUT_DATA / "fact_union_timeseries.csv"
    cols = ["year", "cut", "group", "n", "n_filiadas_unw",
            "pct_filiadas", "ci_lo", "ci_hi"]
    done_years = set()
    if out_csv.exists():
        try:
            existing = pd.read_csv(out_csv)
            done_years = set(existing["year"].unique().tolist())
            log.info("resuming — %d years already in %s: %s",
                     len(done_years), out_csv.name, sorted(done_years))
        except Exception:
            pass
    else:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=cols).to_csv(out_csv, index=False)

    for year in YEARS:
        if year in done_years:
            log.info("[%d] skipping — already in CSV", year)
            continue
        try:
            rows = process_year(year)
            if rows:
                # Append rows for this year
                pd.DataFrame(rows)[cols].to_csv(out_csv, mode="a", header=False, index=False)
                log.info("[%d] appended %d rows to %s", year, len(rows), out_csv.name)
        except Exception as e:
            log.exception("[%d] processing failed: %s", year, e)

    # Read back the full file for the summary
    try:
        df_out = pd.read_csv(out_csv)
    except Exception:
        log.error("Could not read final CSV %s", out_csv)
        return
    log.info("final CSV has %d rows across %d years",
             len(df_out), df_out["year"].nunique())

    if len(df_out) == 0:
        log.error("No data produced. Aborting.")
        return

    # Pretty summary
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with OUT_SUMMARY.open("w") as f:
        f.write("# Filiação sindical — trabalhadoras domésticas — série temporal\n\n")
        f.write("Fonte: PNADC Anual Visita 1, variável V4097 ('Na semana de referência ")
        f.write("era associado a algum sindicato?'). Cálculos ponderados pelo peso amostral V1032. ")
        f.write("Intervalos de confiança Wilson 95% usam n não-ponderado.\n\n")
        for cut in ["overall", "race", "formality", "race_x_formality"]:
            f.write(f"## Corte: `{cut}`\n\n")
            sub = df_out[df_out["cut"] == cut].sort_values(["year", "group"])
            if len(sub) == 0:
                continue
            f.write("| Ano | Grupo | n | n filiadas | % | IC 95% |\n")
            f.write("|---|---|---:|---:|---:|---|\n")
            for _, r in sub.iterrows():
                ci = f"[{r['ci_lo']}, {r['ci_hi']}]" if r["ci_lo"] is not None else "—"
                pct = f"{r['pct_filiadas']}%" if r["pct_filiadas"] is not None else "—"
                f.write(f"| {r['year']} | {r['group']} | {r['n']} | "
                        f"{r['n_filiadas_unw']} | {pct} | {ci} |\n")
            f.write("\n")
    log.info("wrote summary → %s", OUT_SUMMARY)


if __name__ == "__main__":
    main()
