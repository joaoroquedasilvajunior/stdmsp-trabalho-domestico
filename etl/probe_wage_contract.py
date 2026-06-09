"""
probe_wage_contract.py — One-quarter probe: wage × contract × formality × race
==============================================================================

ANALYTICAL QUESTION
-------------------
Does the per-hour racial wage gap survive within homogeneous (contract ×
formality) buckets? Or does the gap collapse once we control for contract
type and signed-card status?

- If gap COLLAPSES within formal mensalista → racial wage gap is mostly
  COMPOSITION (Black workers concentrated in lower-paying contract types).
- If gap PERSISTS within formal mensalista → PRICE DISCRIMINATION inside
  the same contract.

This probe processes one cached PNADC quarter (microdata zip already on
disk) and prints a clean markdown table of weighted-mean hourly wages
by race × contract × formality, plus the racial wage gap ratio within
each homogeneous cell. Run this ahead of investing in a full pipeline
extension that would add fact_wages_contract for all 56 quarters.

USAGE
-----
    python etl/probe_wage_contract.py 012026

The argument is the PNADC period code (e.g. "012026" for 1T 2026).
Requires the cached zip in etl/raw/pnadc/PNADC_<period>_*.zip.

OUTPUT
------
Markdown table to stdout with one row per (race × contract × formality)
cell, columns: workers_thousands, mean_wage_brl, mean_hourly_brl,
n_unweighted. Then a within-bucket racial gap section.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

import pandas as pd

# Re-use the production pipeline's loaders so the data path is identical.
from pnadc_microdata import (
    load_column_specs, extract_txt, parse_microdata,
    RACE_MAP, FORMALITY_MAP, CONTRACT_MAP, RAW_DIR,
)


def cached_microdata_zip(period: str) -> Path:
    """Find the locally cached zip for `period` without hitting IBGE.

    Matches both naming conventions: PNADC_<TTYYYY>.zip and
    PNADC_<TTYYYY>_<YYYYMMDD>.zip. Picks the latest if multiple exist.
    """
    candidates = sorted(RAW_DIR.glob(f"PNADC_{period}*.zip"))
    if not candidates:
        raise FileNotFoundError(
            f"No cached zip matching PNADC_{period}*.zip in {RAW_DIR}\n"
            f"Run the full pipeline first to download it."
        )
    return candidates[-1]

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("probe_wage_contract")

WEEKS_PER_MONTH = 4.33   # PNADC standard hours-per-month conversion


def load_microdata(period: str) -> pd.DataFrame:
    """Load + parse + filter one quarter's microdata to domestic workers.

    Streams the fixed-width file in chunks and filters each chunk on
    VD4009 ∈ {03, 04} (domestic workers) on the fly. Avoids holding the
    full ~500K-row dataset in memory; final filtered set is ~5K rows.
    """
    specs = load_column_specs()
    zip_path = cached_microdata_zip(period)
    log.info("cache hit: %s (%d MB)", zip_path, zip_path.stat().st_size // 1024 // 1024)
    txt_path = extract_txt(zip_path)

    colspecs = [(s - 1, e) for (s, e) in specs.values()]
    names = list(specs.keys())
    log.info("streaming %s in chunks…", txt_path.name)

    chunks = []
    reader = pd.read_fwf(
        txt_path, colspecs=colspecs, names=names, dtype=str,
        keep_default_na=False, chunksize=50_000,
    )
    for i, chunk in enumerate(reader):
        kept = chunk[chunk["VD4009"].isin(["03", "04"])]
        chunks.append(kept)
        if (i + 1) % 5 == 0:
            log.info("  processed %d chunks, kept %d domestic-worker rows",
                     i + 1, sum(len(c) for c in chunks))
    df = pd.concat(chunks, ignore_index=True)
    log.info("filtered to %d domestic-worker rows", len(df))

    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
    df["wage"]  = pd.to_numeric(df["VD4019"], errors="coerce")
    df["hours"] = pd.to_numeric(df["V4039"], errors="coerce")

    # Keep only rows with positive wage (some domestic workers had no income reported)
    df = df[df["wage"].notna() & (df["wage"] > 0)].copy()
    df["race_code"]     = df["V2010"].map(RACE_MAP)
    df["contract_code"] = df["V4024"].astype(str).map(CONTRACT_MAP)
    df["formality_code"] = df["VD4009"].map(FORMALITY_MAP)
    df = df[df["race_code"].notna()
            & df["contract_code"].notna()
            & df["formality_code"].notna()].copy()

    # Race aggregates used in the table
    df["race_group"] = df["race_code"].map({
        "preta": "negras", "parda": "negras",
        "branca": "nao_negras", "amarela": "nao_negras", "indigena": "nao_negras",
    })

    return df


def cell_stats(group: pd.DataFrame) -> dict:
    """Weighted mean monthly + hourly wage for a (race × contract × formality) cell."""
    w_sum = group["weight"].sum()
    if w_sum == 0:
        return {"workers_thousands": 0.0, "mean_wage_brl": None, "mean_hourly_brl": None, "n": 0}

    workers_thousands = round(float(w_sum) / 1000, 1)
    mean_wage = float((group["wage"] * group["weight"]).sum() / w_sum)

    # Hourly: restrict to workers with valid hours
    with_hours = group[group["hours"].notna() & (group["hours"] > 0) & (group["hours"] <= 98)]
    if with_hours["weight"].sum() > 0:
        hourly = with_hours["wage"] / (with_hours["hours"] * WEEKS_PER_MONTH)
        mean_hourly = float((hourly * with_hours["weight"]).sum() / with_hours["weight"].sum())
    else:
        mean_hourly = None

    return {
        "workers_thousands": workers_thousands,
        "mean_wage_brl":   round(mean_wage, 2),
        "mean_hourly_brl": round(mean_hourly, 2) if mean_hourly is not None else None,
        "n": int(len(group)),
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python etl/probe_wage_contract.py <period>", file=sys.stderr)
        print("Example: python etl/probe_wage_contract.py 012026", file=sys.stderr)
        sys.exit(1)
    period = sys.argv[1]

    log.info("loading period %s", period)
    df = load_microdata(period)
    log.info("loaded %d domestic-worker rows with valid wage", len(df))

    # Compute cell stats for each (race_group, contract, formality)
    cells = {}
    for race in ["negras", "nao_negras"]:
        for contract in ["mensalista", "diarista"]:
            for formality in ["com_carteira", "sem_carteira"]:
                mask = (
                    (df["race_group"] == race)
                    & (df["contract_code"] == contract)
                    & (df["formality_code"] == formality)
                )
                cells[(race, contract, formality)] = cell_stats(df[mask])

    # Print main table
    print(f"\n## Wage × contract × formality, period {period}\n")
    print("| race | contract | formality | workers (k) | mean wage R$ | mean hourly R$ | n |")
    print("|------|----------|-----------|------------:|-------------:|---------------:|--:|")
    for (race, contract, formality), st in cells.items():
        mw = f"R$ {st['mean_wage_brl']:,.2f}" if st['mean_wage_brl'] is not None else "—"
        mh = f"R$ {st['mean_hourly_brl']:,.2f}" if st['mean_hourly_brl'] is not None else "—"
        print(f"| {race} | {contract} | {formality} | {st['workers_thousands']:.1f} | {mw} | {mh} | {st['n']} |")

    # Within-bucket racial gap: negras / nao_negras
    print(f"\n## Within-bucket racial gap (negras ÷ não-negras), period {period}\n")
    print("| contract | formality | monthly gap | hourly gap | n (negras) | n (não-negras) |")
    print("|----------|-----------|------------:|-----------:|-----------:|---------------:|")
    for contract in ["mensalista", "diarista"]:
        for formality in ["com_carteira", "sem_carteira"]:
            n_cell = cells[("negras", contract, formality)]
            nn_cell = cells[("nao_negras", contract, formality)]
            m_gap = None
            if n_cell["mean_wage_brl"] and nn_cell["mean_wage_brl"]:
                m_gap = 100 * n_cell["mean_wage_brl"] / nn_cell["mean_wage_brl"]
            h_gap = None
            if n_cell["mean_hourly_brl"] and nn_cell["mean_hourly_brl"]:
                h_gap = 100 * n_cell["mean_hourly_brl"] / nn_cell["mean_hourly_brl"]
            m_s = f"{m_gap:.1f}%" if m_gap is not None else "—"
            h_s = f"{h_gap:.1f}%" if h_gap is not None else "—"
            print(f"| {contract} | {formality} | {m_s} | {h_s} | {n_cell['n']} | {nn_cell['n']} |")

    # Cross-reference: BR-wide aggregate hourly gap (race × formality=total)
    print(f"\n## Cross-reference: aggregate gap by formality (any contract), period {period}\n")
    print("| formality | monthly gap | hourly gap |")
    print("|-----------|------------:|-----------:|")
    for formality in ["com_carteira", "sem_carteira", "total"]:
        if formality == "total":
            n_mask  = (df["race_group"] == "negras")
            nn_mask = (df["race_group"] == "nao_negras")
        else:
            n_mask  = (df["race_group"] == "negras")     & (df["formality_code"] == formality)
            nn_mask = (df["race_group"] == "nao_negras") & (df["formality_code"] == formality)
        n_st  = cell_stats(df[n_mask])
        nn_st = cell_stats(df[nn_mask])
        m_gap = 100 * n_st["mean_wage_brl"] / nn_st["mean_wage_brl"] if n_st["mean_wage_brl"] and nn_st["mean_wage_brl"] else None
        h_gap = 100 * n_st["mean_hourly_brl"] / nn_st["mean_hourly_brl"] if n_st["mean_hourly_brl"] and nn_st["mean_hourly_brl"] else None
        m_s = f"{m_gap:.1f}%" if m_gap is not None else "—"
        h_s = f"{h_gap:.1f}%" if h_gap is not None else "—"
        print(f"| {formality} | {m_s} | {h_s} |")


if __name__ == "__main__":
    main()
