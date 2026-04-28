"""
fetch_sidra.py
==============

ETL: SIDRA (IBGE) → Supabase (`domestic_work` schema).

For each dataset entry in `manifest.yaml`:
  1. Build the apisidra URL from explicit numeric codes (no name-matching —
     IBGE renumbers/renames categories between table versions).
  2. Pull the table.
  3. Reshape rows into long-form facts (one row per period × geo × demographic
     slice).
  4. Validate row count + magnitude, then upsert into Supabase.

Idempotent — the unique constraint on (time × geo × dims × source_table)
means re-runs only insert new rows.

Usage:
    python fetch_sidra.py                       # all datasets in the manifest
    python fetch_sidra.py pnadc_workers_brazil  # one dataset
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv
from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential

# ----- config & logging --------------------------------------------------------

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch_sidra")

ROOT = Path(__file__).parent
MANIFEST = yaml.safe_load((ROOT / "manifest.yaml").read_text(encoding="utf-8"))

sb: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
SCHEMA = sb.schema("domestic_work")

# Map SIDRA category-id → our dim_formality.code. Hardcoded because table 6320's
# c11913 IDs are stable.
FORMALITY_FROM_CAT_ID = {
    31724: "total",         # Trabalhador doméstico
    31725: "com_carteira",  # Trabalhador doméstico - com carteira
    31726: "sem_carteira",  # Trabalhador doméstico - sem carteira
}


# ----- SIDRA HTTP --------------------------------------------------------------

_metadata_cache: dict[int, dict] = {}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
def get_metadata(table: int) -> dict:
    if table in _metadata_cache:
        return _metadata_cache[table]
    url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{table}/metadados"
    log.info("metadata: %s", url)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    _metadata_cache[table] = r.json()
    return _metadata_cache[table]


def resolve_latest_period(table: int) -> str:
    """Return the most recent period code from a SIDRA table's metadata.
    Format depends on the table: '202602' for trimestre móvel, '2024' for annual."""
    meta = get_metadata(table)
    fim = meta.get("periodicidade", {}).get("fim")
    if fim is None:
        raise ValueError(f"Table {table} metadata has no periodicidade.fim")
    return str(fim)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
def fetch_sidra(table: int, level: str, variables: list[int],
                classifications: dict[str, list[int]], period: str) -> pd.DataFrame:
    """Fetch from SIDRA. Returns a DataFrame whose columns are the Portuguese
    labels from the header row (e.g. 'Valor', 'Trimestre Móvel (Código)')."""
    base = MANIFEST["defaults"]["base_url"]
    fmt = MANIFEST["defaults"]["request_format"]   # empty string — default format with header row
    var_str = ",".join(str(v) for v in variables)
    cls_path = "".join(
        f"/c{cls}/{','.join(str(c) for c in cats)}"
        for cls, cats in classifications.items()
    )

    # Resolve 'latest' to a real period code at request time (lets manifests stay date-agnostic).
    if period == "latest":
        period = resolve_latest_period(table)

    period_segment = f"/p/{period}"

    url = f"{base}{fmt}/t/{table}/{level}/all/v/{var_str}{period_segment}{cls_path}"
    log.info("fetch: %s", url)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    rows = r.json()
    if not rows or len(rows) < 2:
        return pd.DataFrame()

    # SIDRA default response shape: rows[0] is a header dict mapping short keys
    # ({NC, NN, V, D1C, D1N, D2C, D2N, D3C, D3N, ...}) to Portuguese column labels.
    # Subsequent rows are data dicts using those same short keys.
    header = rows[0]
    df = pd.DataFrame(rows[1:]).rename(columns=header)
    return df


# ----- column resolution -------------------------------------------------------

def resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Find the columns we need by matching against the Portuguese header labels.
    Looks for trailing '(Código)' on the territorial and classification columns —
    that's how SIDRA distinguishes code from label columns."""
    cols = list(df.columns)
    out: dict[str, str] = {}

    def find(predicate, label):
        match = next((c for c in cols if predicate(c)), None)
        if match is None:
            raise KeyError(
                f"Could not locate {label} column in SIDRA response. "
                f"Available columns: {cols}"
            )
        return match

    out["value"] = find(lambda c: c == "Valor", "value")
    # period: 'Trimestre Móvel (Código)' or 'Ano (Código)'
    out["period"] = find(
        lambda c: ("Trimestre" in c or c.startswith("Ano")) and "(Código)" in c,
        "period",
    )
    # geo code: 'Brasil (Código)' for n1, 'Unidade da Federação (Código)' for n3
    out["geo_code"] = find(
        lambda c: "(Código)" in c and ("Brasil" in c or "Federa" in c or "UF" in c or "Município" in c),
        "geo_code",
    )
    # classification c11913 code
    out["pos_id"] = find(
        lambda c: "(Código)" in c and ("Posição" in c or "ocupação" in c.lower()),
        "pos_id",
    )
    return out


# ----- normalization helpers ---------------------------------------------------

def _resolve_value_period_geo(df: pd.DataFrame) -> dict[str, str]:
    """Subset of resolve_columns shared between fact_workers and fact_wages.
    Both need: value, period, geo_code. Workers also needs pos_id."""
    cols = list(df.columns)

    def find(predicate, label):
        match = next((c for c in cols if predicate(c)), None)
        if match is None:
            raise KeyError(f"Could not locate {label} column. Available: {cols}")
        return match

    return {
        "value":     find(lambda c: c == "Valor", "value"),
        "period":    find(lambda c: ("Trimestre" in c or c.startswith("Ano")) and "(Código)" in c, "period"),
        "geo_code":  find(lambda c: "(Código)" in c and ("Brasil" in c or "Federa" in c or "UF" in c or "Município" in c), "geo_code"),
    }


# ----- normalization to fact_workers rows --------------------------------------

def parse_period_code(raw: str) -> tuple[int, int | None, str]:
    """Convert SIDRA period strings to (year, calendar_quarter|None, period_code).

    PNADC trimestres móveis are rolling 3-month windows updated monthly; each
    distinct 6-digit code (YYYYMM, where MM is the END month of the window) is
    its own period. We keep the raw 6-digit code as the canonical period_code so
    distinct trimestres don't collapse together.

    Examples:
      '201203' → (2012, 1, '201203')   # jan-fev-mar 2012
      '201204' → (2012, 2, '201204')   # fev-mar-abr 2012
      '202602' → (2026, 1, '202602')   # dez 2025-jan-fev 2026
      '2024'   → (2024, None, '2024')  # annual
    """
    s = str(raw).strip()
    if len(s) == 6 and s.isdigit():
        year = int(s[:4])
        end_month = int(s[4:])
        # Calendar quarter the window ENDS in — informational only, not unique.
        quarter = (end_month - 1) // 3 + 1
        return year, quarter, s
    if len(s) == 4 and s.isdigit():
        return int(s), None, s
    raise ValueError(f"Unrecognized period code: {raw!r}")


def batch_upsert_dim_time(period_raws: set[str]) -> dict[str, int]:
    """Bulk-upsert all needed period codes in a single REST call, return {period_code: time_id}."""
    payload = []
    for raw in period_raws:
        year, quarter, code = parse_period_code(raw)
        payload.append({"year": year, "quarter": quarter, "period_code": code})
    if payload:
        SCHEMA.table("dim_time").upsert(payload, on_conflict="period_code").execute()
    # Re-read to get time_ids (upsert returns rows but in upsert order, not insertion order; safer to re-fetch).
    res = SCHEMA.table("dim_time").select("period_code,time_id").execute()
    return {r["period_code"]: r["time_id"] for r in res.data}


def fetch_geo_lookup() -> dict[tuple[str, str], int]:
    """Return {(level, code): geo_id} for the whole dim_geo table (33 rows, fits easily)."""
    res = SCHEMA.table("dim_geo").select("level,code,geo_id").execute()
    return {(r["level"], r["code"]): r["geo_id"] for r in res.data}


def normalize_workers_simple(df: pd.DataFrame, source_code: str, classification_code_map: dict[int, str] | None = None) -> list[dict]:
    """For tables that already pre-filter to trabalhadores domésticos
    (e.g. Tabela 6383). Output goes into fact_workers; formality_code is taken
    from the classification's category id via `classification_code_map`, with
    'total' as the fallback when no map is provided.

    classification_code_map example for Tabela 6383 c785:
      {40276: 'total', 40277: 'mensalista', 40278: 'diarista'}
    """
    if df.empty:
        return []
    cols = _resolve_value_period_geo(df)
    # Find the classification's "(Código)" column. Exclude every other (Código) column we
    # know about (value/period/geo, plus Nível Territorial and Variável which SIDRA always
    # includes regardless of the table). What's left is the user-asked-for classification.
    used = {cols["value"], cols["period"], cols["geo_code"]}
    EXCLUDE_PREFIXES = ("Trimestre", "Ano", "Nível Territorial", "Variável", "Unidade de Medida")
    EXCLUDE_SUBSTRS = ("Brasil", "Federa", "Município", "Região", "Mesorregião", "Microrregião")
    classif_code_col = next(
        (c for c in df.columns
         if c not in used
         and "(Código)" in c
         and not any(c.startswith(p) for p in EXCLUDE_PREFIXES)
         and not any(s in c for s in EXCLUDE_SUBSTRS)
         and not c == "UF (Código)"),
        None,
    )
    log.info("normalize_workers_simple cols → value=%r period=%r geo=%r classif=%r",
             cols.get("value"), cols.get("period"), cols.get("geo_code"), classif_code_col)
    if not df.empty:
        sample = df.iloc[0].to_dict()
        log.info("normalize_workers_simple sample row: %s", sample)

    rows = []
    for _, r in df.iterrows():
        raw_val = str(r[cols["value"]]).strip()
        if raw_val in ("", "...", "-", "X", ".."):
            continue
        try:
            value = float(raw_val.replace(",", "."))
        except ValueError:
            continue

        # Category-id-based mapping for the formality slot.
        formality_code = "total"
        if classification_code_map is not None:
            if classif_code_col is None:
                raise RuntimeError(
                    f"classification_code_map provided but no classification column found in "
                    f"SIDRA response. Columns: {list(df.columns)}"
                )
            try:
                cat_id = int(r[classif_code_col])
            except (ValueError, TypeError):
                continue
            if cat_id not in classification_code_map:
                continue   # skip categories not in the map
            formality_code = classification_code_map[cat_id]

        geo_code_raw = str(r[cols["geo_code"]]).strip()
        if geo_code_raw == "1":
            geo_level, geo_code = "country", "BR"
        else:
            geo_level, geo_code = "uf", geo_code_raw.zfill(2)

        rows.append({
            "_period":     r[cols["period"]],
            "_geo_level":  geo_level,
            "_geo_code":   geo_code,
            "_formality":  formality_code,
            "_sex":        "T",
            "_race":       "total",
            "_age":        "total",
            "workers_thousands": value,
            "source_table": source_code,
        })
    return rows


def normalize_wages(df: pd.DataFrame, source_code: str) -> list[dict]:
    """Reshape SIDRA wage response (Table 6391) into fact_wages rows.
    No sex/race/formality breakdown — those dimensions get the 'total' codes."""
    if df.empty:
        return []
    cols = _resolve_value_period_geo(df)

    rows = []
    for _, r in df.iterrows():
        raw_val = str(r[cols["value"]]).strip()
        if raw_val in ("", "...", "-", "X", ".."):
            continue
        try:
            value = float(raw_val.replace(",", "."))
        except ValueError:
            continue

        geo_code_raw = str(r[cols["geo_code"]]).strip()
        if geo_code_raw == "1":
            geo_level, geo_code = "country", "BR"
        else:
            geo_level, geo_code = "uf", geo_code_raw.zfill(2)

        rows.append({
            "_period":       r[cols["period"]],
            "_geo_level":    geo_level,
            "_geo_code":     geo_code,
            "_sex":          "T",
            "_race":         "total",
            "_formality":    "total",
            "mean_wage_brl_real":   value,
            "median_wage_brl_real": None,
            "source_table":  source_code,
        })
    return rows


def normalize_workers(df: pd.DataFrame, source_code: str) -> list[dict]:
    if df.empty:
        return []
    cols = resolve_columns(df)

    rows = []
    for _, r in df.iterrows():
        raw_val = str(r[cols["value"]]).strip()
        if raw_val in ("", "...", "-", "X", ".."):
            continue
        try:
            value = float(raw_val.replace(",", "."))
        except ValueError:
            continue

        try:
            cat_id = int(r[cols["pos_id"]])
        except (ValueError, TypeError):
            continue
        formality_code = FORMALITY_FROM_CAT_ID.get(cat_id)
        if formality_code is None:
            continue   # skip categories we didn't ask for

        geo_code_raw = str(r[cols["geo_code"]]).strip()
        if geo_code_raw == "1":
            geo_level, geo_code = "country", "BR"
        else:
            geo_level, geo_code = "uf", geo_code_raw.zfill(2)

        rows.append({
            "_period": r[cols["period"]],
            "_geo_level": geo_level,
            "_geo_code": geo_code,
            "_formality": formality_code,
            "_sex": "T",
            "_race": "total",
            "_age": "total",
            "workers_thousands": value,
            "source_table": source_code,
        })
    return rows


# ----- upsert orchestration ----------------------------------------------------

def upsert_fact_workers(rows: list[dict]) -> int:
    """Pre-batch all dimension lookups, then bulk-upsert the facts.
    Reduces REST calls from ~2N to ~6 regardless of N — fixes the connection-reset
    we saw at N=504."""
    if not rows:
        return 0

    # 1. Batch-upsert any missing periods in one call.
    needed_periods = {r["_period"] for r in rows}
    time_lookup = batch_upsert_dim_time(needed_periods)

    # 2. Fetch each dimension once.
    geo_lookup = fetch_geo_lookup()
    dim_lookups = {
        "sex":       {r["code"]: r["sex_id"]       for r in SCHEMA.table("dim_sex").select("code,sex_id").execute().data},
        "race":      {r["code"]: r["race_id"]      for r in SCHEMA.table("dim_race").select("code,race_id").execute().data},
        "formality": {r["code"]: r["formality_id"] for r in SCHEMA.table("dim_formality").select("code,formality_id").execute().data},
        "age":       {r["code"]: r["age_id"]       for r in SCHEMA.table("dim_age_group").select("code,age_id").execute().data},
    }

    # 3. Build the payload from in-memory lookups (zero network calls in the loop).
    payload = []
    for r in rows:
        _, _, period_code = parse_period_code(r["_period"])
        try:
            time_id = time_lookup[period_code]
            geo_id = geo_lookup[(r["_geo_level"], r["_geo_code"])]
        except KeyError as e:
            log.warning("missing dim lookup for row %s: %s", r, e)
            continue
        payload.append({
            "time_id":      time_id,
            "geo_id":       geo_id,
            "sex_id":       dim_lookups["sex"][r["_sex"]],
            "race_id":      dim_lookups["race"][r["_race"]],
            "formality_id": dim_lookups["formality"][r["_formality"]],
            "age_id":       dim_lookups["age"][r["_age"]],
            "workers_thousands": r["workers_thousands"],
            "source_table": r["source_table"],
        })

    # 4. Bulk-upsert in chunks of 250 (smaller than before, plays nicer with PostgREST).
    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i+250]
        res = SCHEMA.table("fact_workers").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,formality_id,age_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def upsert_fact_wages(rows: list[dict]) -> int:
    """Mirror of upsert_fact_workers, for wage rows."""
    if not rows:
        return 0

    needed_periods = {r["_period"] for r in rows}
    time_lookup = batch_upsert_dim_time(needed_periods)
    geo_lookup = fetch_geo_lookup()
    dim_lookups = {
        "sex":       {r["code"]: r["sex_id"]       for r in SCHEMA.table("dim_sex").select("code,sex_id").execute().data},
        "race":      {r["code"]: r["race_id"]      for r in SCHEMA.table("dim_race").select("code,race_id").execute().data},
        "formality": {r["code"]: r["formality_id"] for r in SCHEMA.table("dim_formality").select("code,formality_id").execute().data},
    }

    payload = []
    for r in rows:
        _, _, period_code = parse_period_code(r["_period"])
        try:
            time_id = time_lookup[period_code]
            geo_id = geo_lookup[(r["_geo_level"], r["_geo_code"])]
        except KeyError as e:
            log.warning("missing dim lookup for wage row %s: %s", r, e)
            continue
        payload.append({
            "time_id":      time_id,
            "geo_id":       geo_id,
            "sex_id":       dim_lookups["sex"][r["_sex"]],
            "race_id":      dim_lookups["race"][r["_race"]],
            "formality_id": dim_lookups["formality"][r["_formality"]],
            "mean_wage_brl_real":   r["mean_wage_brl_real"],
            "median_wage_brl_real": r["median_wage_brl_real"],
            "source_table": r["source_table"],
        })

    inserted = 0
    for i in range(0, len(payload), 250):
        chunk = payload[i:i+250]
        res = SCHEMA.table("fact_wages").upsert(
            chunk,
            on_conflict="time_id,geo_id,sex_id,race_id,formality_id,source_table",
        ).execute()
        inserted += len(res.data or [])
    return inserted


def validate_wages(rows: list[dict], dataset_name: str) -> None:
    if not rows:
        log.warning("[%s] zero wage rows after normalization", dataset_name)
        return
    values = [r["mean_wage_brl_real"] for r in rows if r["mean_wage_brl_real"] is not None]
    if not values:
        log.warning("[%s] all wage values null", dataset_name)
        return
    p_max, p_min = max(values), min(values)
    # Sanity: real BRL wages for serviços domésticos should be in roughly [400, 2500] over 2012-2026
    if p_max > 5000 or p_min < 100:
        log.warning("[%s] wage values outside expected range: [%.0f, %.0f] BRL", dataset_name, p_min, p_max)
    log.info("[%s] %d wage rows · range [R$ %.0f, R$ %.0f]", dataset_name, len(rows), p_min, p_max)


# ----- validation --------------------------------------------------------------

def validate_workers(rows: list[dict], dataset_name: str) -> None:
    if not rows:
        log.warning("[%s] zero rows after normalization", dataset_name)
        return
    values = [r["workers_thousands"] for r in rows if r["workers_thousands"] is not None]
    if not values:
        log.warning("[%s] all values null", dataset_name)
        return
    p_max, p_min = max(values), min(values)
    if p_max > 30000:
        log.warning("[%s] suspiciously high max value: %.1f (mil pessoas)", dataset_name, p_max)
    log.info("[%s] %d normalized rows · range [%.1f, %.1f] mil pessoas", dataset_name, len(rows), p_min, p_max)


# ----- main --------------------------------------------------------------------

def run_dataset(name: str, spec: dict) -> None:
    log.info("=== %s ===", name)
    keep_n = spec.get("keep_latest_n_periods")
    for level in spec["levels"]:
        df = fetch_sidra(
            table=spec["sidra_table"],
            level=level,
            variables=spec["variables"],
            classifications={k: v for k, v in spec.get("classifications", {}).items()},
            period=spec["period"],
        )
        log.info("[%s] %s: %d rows from SIDRA", name, level, len(df))
        if df.empty:
            continue

        # Optional: keep only the latest N trimestres (post-filter, since SIDRA's
        # /p/-N relative-period syntax isn't supported on every endpoint).
        if keep_n:
            cols = resolve_columns(df)
            unique_periods = sorted(df[cols["period"]].astype(str).unique())
            keep_periods = set(unique_periods[-keep_n:])
            df = df[df[cols["period"]].astype(str).isin(keep_periods)]
            log.info("[%s] kept latest %d periods: %s", name, keep_n, sorted(keep_periods))

        if spec["target_table"] == "fact_workers":
            rows = normalize_workers(df, spec["source_code"])
            validate_workers(rows, name)
            n = upsert_fact_workers(rows)
            log.info("[%s] upserted %d rows into fact_workers", name, n)
        elif spec["target_table"] == "fact_workers_simple":
            # Tables that already pre-filter to trabalhadores domésticos (e.g. 6383).
            # The optional classification_code_map maps SIDRA category-ids to formality codes.
            raw_map = spec.get("classification_code_map") or {}
            code_map = {int(k): v for k, v in raw_map.items()} if raw_map else None
            rows = normalize_workers_simple(df, spec["source_code"], code_map)
            validate_workers(rows, name)
            n = upsert_fact_workers(rows)
            log.info("[%s] upserted %d rows into fact_workers", name, n)
        elif spec["target_table"] == "fact_wages":
            rows = normalize_wages(df, spec["source_code"])
            validate_wages(rows, name)
            n = upsert_fact_wages(rows)
            log.info("[%s] upserted %d rows into fact_wages", name, n)
        else:
            log.warning("[%s] target_table=%s not yet implemented", name, spec["target_table"])


def main(argv: list[str]) -> None:
    selected = argv[1:] if len(argv) > 1 else list(MANIFEST["datasets"].keys())
    for name in selected:
        spec = MANIFEST["datasets"].get(name)
        if not spec:
            log.error("dataset '%s' not in manifest, skipping", name)
            continue
        try:
            run_dataset(name, spec)
        except Exception as e:
            log.exception("[%s] failed: %s", name, e)


if __name__ == "__main__":
    main(sys.argv)
