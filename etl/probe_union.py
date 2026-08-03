"""
probe_union.py — One-quarter probe: union membership × race × contract
========================================================================

ANALYTICAL QUESTION
-------------------
What share of domestic workers are union members (filiadas a sindicato)?
How does it vary by race and contract type (mensalista vs. diarista)?

PNADC Trimestral variable V4082 ("Era associado a algum sindicato no
período de referência da semana?") — codes: 1=Sim, 2=Não. The variable
is not in our production NEEDED_VARS list yet; this probe loads the
column position directly from the PNADC dictionary cache.

This probe is the literature gap test: DIEESE doesn't publish this
figure for domestic workers, SIDRA PNADCA doesn't cross union membership
× occupation in its published tables, so we have to compute it directly.

USAGE
-----
    python etl/probe_union.py 012026

OUTPUT
------
Markdown table to stdout: filiação rate by race, by contract, with
Wilson 95% CIs, weighted (V1028) and unweighted sample sizes.
"""

from __future__ import annotations

import sys
import logging
import math
from pathlib import Path

import pandas as pd

# Re-use parsing helpers from the production pipeline.
from pnadc_microdata import (
    parse_sas_input, extract_txt, RACE_MAP, RAW_DIR,
    CONTRACT_MAP, FORMALITY_MAP,
)
import zipfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("probe_union")

# Variables we need from the PNADC microdata for this probe.
# V4082 is the new one — not in production NEEDED_VARS yet.
PROBE_VARS = [
    "Ano", "Trimestre", "UF",
    "V1028",   # population weight
    "V2007",   # sex
    "V2010",   # cor/raça
    "V4024",   # diarista vs mensalista
    "V4082",   # NEW — associada a sindicato?
    "VD4009",  # posição na ocupação (formality + domestic-worker filter)
]


def load_full_specs() -> dict[str, tuple[int, int]]:
    """Load specs for ALL PNADC variables (not just NEEDED_VARS) so we
    can pick out V4082. Reads the locally cached dictionary zip — does
    NOT hit IBGE FTP, so this works in the sandbox."""
    candidates = sorted(RAW_DIR.glob("Dicionario*.zip"))
    if not candidates:
        raise FileNotFoundError(
            f"No cached dictionary zip in {RAW_DIR}. "
            "Re-run pnadc_microdata.py once to populate the cache."
        )
    dict_zip = candidates[-1]
    log.info("dictionary cache hit: %s", dict_zip)
    with zipfile.ZipFile(dict_zip) as zf:
        sas_names = [n for n in zf.namelist() if n.lower().endswith(".sas")]
        if not sas_names:
            raise FileNotFoundError("No .sas file in PNADC dictionary zip")
        with zf.open(sas_names[0]) as f:
            text = f.read().decode("latin-1")
    return parse_sas_input(text)


def cached_microdata_zip(period: str) -> Path:
    candidates = sorted(RAW_DIR.glob(f"PNADC_{period}*.zip"))
    if not candidates:
        raise FileNotFoundError(f"No cached zip matching PNADC_{period}*.zip in {RAW_DIR}")
    return candidates[-1]


def load_microdata(period: str) -> pd.DataFrame:
    """Load + filter PNADC quarter for domestic workers, including V4082."""
    full_specs = load_full_specs()
    # Filter to just the variables we care about for this probe
    specs = {v: full_specs[v] for v in PROBE_VARS if v in full_specs}
    missing = [v for v in PROBE_VARS if v not in full_specs]
    if missing:
        log.warning("Variables missing from dictionary: %s", missing)
    log.info("loaded specs for %d variables (V4082 position: %s)",
             len(specs), specs.get("V4082"))

    zip_path = cached_microdata_zip(period)
    log.info("cache hit: %s (%d MB)", zip_path, zip_path.stat().st_size // 1024 // 1024)
    txt_path = extract_txt(zip_path)

    colspecs = [(s - 1, e) for (s, e) in specs.values()]
    names = list(specs.keys())
    log.info("streaming %s in chunks (filtering to domestic workers)…", txt_path.name)

    chunks = []
    reader = pd.read_fwf(txt_path, colspecs=colspecs, names=names, dtype=str,
                         keep_default_na=False, chunksize=50_000)
    for i, chunk in enumerate(reader):
        kept = chunk[chunk["VD4009"].isin(["03", "04"])]
        chunks.append(kept)
        if (i + 1) % 5 == 0:
            log.info("  processed %d chunks, kept %d domestic-worker rows so far",
                     i + 1, sum(len(c) for c in chunks))
    df = pd.concat(chunks, ignore_index=True)
    log.info("filtered to %d domestic-worker rows", len(df))

    df = df.copy()
    df["weight"] = pd.to_numeric(df["V1028"], errors="coerce")
    if df["weight"].max() > 1e9:
        df["weight"] = df["weight"] / 1e9

    df["race_code"]       = df["V2010"].map(RACE_MAP)
    df["race_group"]      = df["race_code"].map({
        "preta": "negras", "parda": "negras",
        "branca": "nao_negras", "amarela": "nao_negras", "indigena": "nao_negras",
    })
    df["contract_code"]   = df["V4024"].astype(str).map(CONTRACT_MAP)
    df["formality_code"]  = df["VD4009"].map(FORMALITY_MAP)

    # V4082: 1 = Sim, 2 = Não. Anything else → NaN.
    df["filiada"] = df["V4082"].map({"1": True, "2": False})
    return df


def wilson_ci(p: float, n: int, z: float = 1.96):
    """Wilson 95% CI for proportion p with n trials. Returns (lo, hi) in %."""
    if n <= 0 or p is None or math.isnan(p):
        return (None, None)
    denom = 1 + (z * z) / n
    center = (p + (z * z) / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + (z * z) / (4 * n * n))) / denom
    return (100 * max(0, center - half), 100 * min(1, center + half))


def cell_stats(group: pd.DataFrame) -> dict:
    """Return weighted % filiadas + unweighted n + Wilson CI."""
    valid = group[group["filiada"].notna()]
    n = len(valid)
    if n == 0:
        return {"n": 0, "pct_filiadas": None, "ci_lo": None, "ci_hi": None,
                "n_filiadas_unweighted": 0, "weighted_total_thousands": 0}
    w_sum = valid["weight"].sum()
    w_fil = valid[valid["filiada"] == True]["weight"].sum()
    pct = 100 * w_fil / w_sum if w_sum else None
    # Wilson CI uses unweighted n
    p_unw = valid["filiada"].sum() / n
    lo, hi = wilson_ci(p_unw, n)
    return {
        "n": n,
        "n_filiadas_unweighted": int(valid["filiada"].sum()),
        "pct_filiadas": round(pct, 2) if pct is not None else None,
        "ci_lo": round(lo, 2) if lo is not None else None,
        "ci_hi": round(hi, 2) if hi is not None else None,
        "weighted_total_thousands": round(w_sum / 1000, 1),
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python etl/probe_union.py <period>", file=sys.stderr)
        sys.exit(1)
    period = sys.argv[1]

    df = load_microdata(period)

    print(f"\n## Filiação sindical das trabalhadoras domésticas — PNADC {period}\n")
    print(f"Total domesticas no quarter (n unweighted): {len(df)}")
    print(f"Com resposta válida V4082 (Sim/Não): {df['filiada'].notna().sum()}")
    print(f"Filiadas (Sim, unweighted): {(df['filiada'] == True).sum()}")
    print(f"Não filiadas (Não, unweighted): {(df['filiada'] == False).sum()}")
    print(f"Sem resposta (NaN): {df['filiada'].isna().sum()}")

    # Overall BR-wide
    print("\n### Por raça (BR-wide)\n")
    print("| Grupo | n (resp. válida) | n filiadas | % filiadas | IC 95% |")
    print("|---|---:|---:|---:|---|")
    for grp in ["negras", "nao_negras"]:
        stats = cell_stats(df[df["race_group"] == grp])
        ci = f"[{stats['ci_lo']}, {stats['ci_hi']}]" if stats["ci_lo"] is not None else "—"
        pct = f"{stats['pct_filiadas']}%" if stats["pct_filiadas"] is not None else "—"
        print(f"| {grp} | {stats['n']} | {stats['n_filiadas_unweighted']} | {pct} | {ci} |")
    stats_all = cell_stats(df)
    ci_all = f"[{stats_all['ci_lo']}, {stats_all['ci_hi']}]" if stats_all["ci_lo"] is not None else "—"
    pct_all = f"{stats_all['pct_filiadas']}%" if stats_all["pct_filiadas"] is not None else "—"
    print(f"| **total** | **{stats_all['n']}** | **{stats_all['n_filiadas_unweighted']}** | **{pct_all}** | **{ci_all}** |")

    # By contract type
    print("\n### Por tipo de contrato (BR-wide)\n")
    print("| Contrato | n (resp. válida) | n filiadas | % filiadas | IC 95% |")
    print("|---|---:|---:|---:|---|")
    for contract in ["mensalista", "diarista"]:
        stats = cell_stats(df[df["contract_code"] == contract])
        ci = f"[{stats['ci_lo']}, {stats['ci_hi']}]" if stats["ci_lo"] is not None else "—"
        pct = f"{stats['pct_filiadas']}%" if stats["pct_filiadas"] is not None else "—"
        print(f"| {contract} | {stats['n']} | {stats['n_filiadas_unweighted']} | {pct} | {ci} |")

    # Race × contract
    print("\n### Raça × contrato (BR-wide)\n")
    print("| Raça | Contrato | n | n filiadas | % filiadas | IC 95% |")
    print("|---|---|---:|---:|---:|---|")
    for grp in ["negras", "nao_negras"]:
        for contract in ["mensalista", "diarista"]:
            sub = df[(df["race_group"] == grp) & (df["contract_code"] == contract)]
            stats = cell_stats(sub)
            ci = f"[{stats['ci_lo']}, {stats['ci_hi']}]" if stats["ci_lo"] is not None else "—"
            pct = f"{stats['pct_filiadas']}%" if stats["pct_filiadas"] is not None else "—"
            print(f"| {grp} | {contract} | {stats['n']} | {stats['n_filiadas_unweighted']} | {pct} | {ci} |")

    # By formality (carteira)
    print("\n### Por formalidade (carteira) — BR-wide\n")
    print("| Formalidade | n | n filiadas | % filiadas | IC 95% |")
    print("|---|---:|---:|---:|---|")
    for form in ["com_carteira", "sem_carteira"]:
        stats = cell_stats(df[df["formality_code"] == form])
        ci = f"[{stats['ci_lo']}, {stats['ci_hi']}]" if stats["ci_lo"] is not None else "—"
        pct = f"{stats['pct_filiadas']}%" if stats["pct_filiadas"] is not None else "—"
        print(f"| {form} | {stats['n']} | {stats['n_filiadas_unweighted']} | {pct} | {ci} |")


if __name__ == "__main__":
    main()
