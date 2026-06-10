"""
probe_general_pop_race.py — General-population race composition by UF
======================================================================

ANALYTICAL PURPOSE
------------------
Every chart in the dashboard that shows "% pretas+pardas among domestic
workers" needs a baseline to be interpretable. Without it, a state like
Santa Catarina reads as "low racialization" (25% Black domestic workers)
when in fact Black women are *overrepresented* in SC's domestic-work
category (baseline ~15% in general population → ratio ~1.67×).

This probe computes the general-population racial composition (BR-wide
and by UF) from the same cached PNADC microdata we use everywhere else,
WITHOUT filtering on VD4009. Result lands at
`dashboard/data/general_pop_race.json` and provides the baselines used
by the dashboard's enhanced map tooltips, the "% pretas+pardas" KPI
tile context, and the race-composition-over-time chart's reference line.

USAGE
-----
    python etl/probe_general_pop_race.py 012026

OUTPUT
------
Writes dashboard/data/general_pop_race.json with:
  - period_code, period_label
  - br_baseline (% pretas+pardas BR-wide, all ages, all sexes)
  - uf_baselines: list of {uf_code, uf_name_pt, uf_name_en, pct_negras, pct_nao_negras, n}
"""

from __future__ import annotations

import sys
import json
import logging
from pathlib import Path

import pandas as pd

from pnadc_microdata import load_column_specs, extract_txt, RACE_MAP, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("probe_general_pop_race")

UF_NAMES_PT = {
    "11": "Rondônia", "12": "Acre", "13": "Amazonas", "14": "Roraima", "15": "Pará", "16": "Amapá", "17": "Tocantins",
    "21": "Maranhão", "22": "Piauí", "23": "Ceará", "24": "Rio Grande do Norte", "25": "Paraíba", "26": "Pernambuco",
    "27": "Alagoas", "28": "Sergipe", "29": "Bahia",
    "31": "Minas Gerais", "32": "Espírito Santo", "33": "Rio de Janeiro", "35": "São Paulo",
    "41": "Paraná", "42": "Santa Catarina", "43": "Rio Grande do Sul",
    "50": "Mato Grosso do Sul", "51": "Mato Grosso", "52": "Goiás", "53": "Distrito Federal",
}
UF_NAMES_EN = {
    "11": "Rondônia", "12": "Acre", "13": "Amazonas", "14": "Roraima", "15": "Pará", "16": "Amapá", "17": "Tocantins",
    "21": "Maranhão", "22": "Piauí", "23": "Ceará", "24": "Rio Grande do Norte", "25": "Paraíba", "26": "Pernambuco",
    "27": "Alagoas", "28": "Sergipe", "29": "Bahia",
    "31": "Minas Gerais", "32": "Espírito Santo", "33": "Rio de Janeiro", "35": "São Paulo",
    "41": "Paraná", "42": "Santa Catarina", "43": "Rio Grande do Sul",
    "50": "Mato Grosso do Sul", "51": "Mato Grosso", "52": "Goiás", "53": "Federal District",
}


def cached_microdata_zip(period: str) -> Path:
    candidates = sorted(RAW_DIR.glob(f"PNADC_{period}*.zip"))
    if not candidates:
        raise FileNotFoundError(f"No cached zip matching PNADC_{period}*.zip in {RAW_DIR}")
    return candidates[-1]


def load_microdata(period: str) -> pd.DataFrame:
    """Stream the fixed-width file in chunks, applying NO domestic-worker filter.

    Only filters out rows with missing race (V2010 ∉ {1..5}) since we cannot
    classify them. Keeps everyone else for the population denominator.
    """
    specs = load_column_specs()
    zip_path = cached_microdata_zip(period)
    log.info("cache hit: %s (%d MB)", zip_path, zip_path.stat().st_size // 1024 // 1024)
    txt_path = extract_txt(zip_path)

    colspecs = [(s - 1, e) for (s, e) in specs.values()]
    names = list(specs.keys())
    log.info("streaming %s in chunks…", txt_path.name)

    chunks = []
    reader = pd.read_fwf(txt_path, colspecs=colspecs, names=names, dtype=str, keep_default_na=False, chunksize=50_000)
    for i, chunk in enumerate(reader):
        kept = chunk[chunk["V2010"].isin(["1", "2", "3", "4", "5"])]
        chunks.append(kept)
        if (i + 1) % 5 == 0:
            log.info("  processed %d chunks, kept %d rows so far",
                     i + 1, sum(len(c) for c in chunks))
    df = pd.concat(chunks, ignore_index=True)
    log.info("filtered to %d rows with valid race", len(df))

    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9
    df["race_code"] = df["V2010"].map(RACE_MAP)
    df["race_group"] = df["race_code"].map({
        "preta": "negras", "parda": "negras",
        "branca": "nao_negras", "amarela": "nao_negras", "indigena": "nao_negras",
    })

    return df


def compute_baselines(df: pd.DataFrame) -> dict:
    """BR + per-UF weighted % pretas+pardas (vs. não-negras)."""
    out = {}

    # BR
    w_total = df["weight"].sum()
    w_negras = df[df["race_group"] == "negras"]["weight"].sum()
    out["br_baseline"] = {
        "pct_negras": round(100 * w_negras / w_total, 2) if w_total else None,
        "pct_nao_negras": round(100 * (w_total - w_negras) / w_total, 2) if w_total else None,
        "n": int(len(df)),
        "weighted_total_thousands": round(float(w_total) / 1000, 1),
    }

    # UF
    uf_rows = []
    for uf, group in df.groupby("UF"):
        if uf not in UF_NAMES_PT:
            continue
        w_uf = group["weight"].sum()
        if w_uf == 0:
            continue
        w_negras_uf = group[group["race_group"] == "negras"]["weight"].sum()
        uf_rows.append({
            "uf_code": uf,
            "uf_name_pt": UF_NAMES_PT[uf],
            "uf_name_en": UF_NAMES_EN[uf],
            "pct_negras": round(100 * w_negras_uf / w_uf, 2),
            "pct_nao_negras": round(100 * (w_uf - w_negras_uf) / w_uf, 2),
            "n": int(len(group)),
            "weighted_total_thousands": round(float(w_uf) / 1000, 1),
        })
    uf_rows.sort(key=lambda r: r["uf_code"])
    out["uf_baselines"] = uf_rows

    return out


def main():
    if len(sys.argv) != 2:
        print("Usage: python etl/probe_general_pop_race.py <period>", file=sys.stderr)
        sys.exit(1)
    period = sys.argv[1]

    log.info("loading period %s (full population, no VD4009 filter)…", period)
    df = load_microdata(period)
    log.info("computing baselines…")
    baselines = compute_baselines(df)

    db_period = period[2:] + period[:2]  # 012026 -> 202601
    period_label_pt = f"{period[1]}T {period[2:]}" if period[0] == "0" else f"{period[:2]}T {period[2:]}"
    period_label_en = f"{period[2:]}Q{period[1]}" if period[0] == "0" else f"{period[2:]}Q{period[:2]}"

    payload = {
        "period_code": db_period,
        "period_label_pt": period_label_pt,
        "period_label_en": period_label_en,
        "generated_by": f"etl/probe_general_pop_race.py {period}",
        "source": "PNADC-MICRODATA",
        "notes": "General-population race composition (NOT restricted to domestic workers). Used as baseline for overrepresentation calculations. Re-run when a new PNADC quarter is ingested.",
        **baselines,
    }

    out_path = Path(__file__).parent.parent / "dashboard" / "data" / "general_pop_race.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("wrote %s", out_path)

    # Print readable summary
    print(f"\n## BR baseline ({period_label_pt}): {baselines['br_baseline']['pct_negras']}% pretas+pardas\n")
    print("| UF | pretas+pardas | não-negras | overrep vs. BR domestic 67.5% |")
    print("|----|--------------:|-----------:|-----------------------------:|")
    for row in baselines["uf_baselines"]:
        # Rough overrep ratio at BR scale (the exact UF-level domestic share would need fact_workers)
        overrep_br = 67.5 / row["pct_negras"] if row["pct_negras"] > 0 else None
        overrep_s = f"{overrep_br:.2f}×" if overrep_br else "—"
        print(f"| {row['uf_code']} {row['uf_name_pt']} | {row['pct_negras']:.1f}% | {row['pct_nao_negras']:.1f}% | {overrep_s} |")


if __name__ == "__main__":
    main()
