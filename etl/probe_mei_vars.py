"""
probe_mei_vars.py — Validate V4010 / V4012 / V4019 byte positions
====================================================================

Step 2 (gate) of mei_proxy_path.md. Before extending pnadc_microdata.py
with build_autonomous_rows() and committing to a 56-quarter backfill,
confirm three things in a single cached PNADC quarter:

  1. Byte positions of V4010 (CBO-Domiciliar 4-digit), V4012 (raw
     position before VD4009 derivation), V4019 (CNPJ? 1=Sim 2=Não)
     resolve correctly from the dictionary.
  2. V4019 is NOT NaN for the vast majority of VD4009 ∈ {'08','09'}
     (empregador / conta-própria). If V4019 is mostly NaN inside that
     subset, the byte position is wrong.
  3. V4010 top-15 codes among conta-própria contain the codes named
     in CBO_DOMESTIC_ADJACENT (5121, 5141, 5143, 5162) at non-trivial
     frequencies. If the codes don't appear, the CBO mapping needs
     revising (likely CBO-2022 vs CBO-2002 drift).

Output goes to stdout (markdown-style tables) and to a small JSON file
chapter/probe_mei_vars_result.json for downstream sanity gates.

USAGE
-----
    # Default: probe the most recent cached quarter
    python etl/probe_mei_vars.py

    # Explicit period (must have its zip cached at etl/raw/pnadc/PNADC_<period>.zip)
    python etl/probe_mei_vars.py 012026

NO Supabase writes — read-only probe.
"""

from __future__ import annotations

import json
import logging
import sys
import zipfile
from pathlib import Path

import pandas as pd

from pnadc_microdata import (
    RAW_DIR, parse_sas_input, extract_txt, RACE_MAP, SEX_MAP,
)


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("probe_mei")


PROBE_VARS = [
    "Ano", "Trimestre", "UF",
    "V1028",   # population weight
    "V2007",   # sex
    "V2010",   # cor/raça
    "V4010",   # CBO-Domiciliar (occupation)
    "V4012",   # raw position (sanity check)
    "V4019",   # CNPJ? 1=Sim 2=Não      ← THE MEI proxy variable
    "V4032",   # previdência (1/2)
    "VD4009",  # posição na ocupação derivada
    "VD4019",  # rendimento mensal habitual
]

# CBO-Domiciliar groupings the spec wants to validate
CBO_DOMESTIC_ADJACENT = {
    "5121": "domestic_5121",
    "5141": "cleaning_5141",
    "5143": "cleaning_5141",
    "5162": "caregiver_5162",
}

# VD4009 codes for the autonomous-worker subset
AUTONOMY_CODES = {"08": "empregador", "09": "conta_propria"}


def load_full_specs() -> dict[str, tuple[int, int]]:
    """Load ALL variable specs from the locally cached dictionary zip
    (does NOT hit IBGE FTP). Mirrors probe_union.py."""
    candidates = sorted(RAW_DIR.glob("Dicionario*.zip"))
    if not candidates:
        raise FileNotFoundError(
            f"No cached dictionary zip in {RAW_DIR}. "
            "Run pnadc_microdata.py once for any quarter to populate the cache."
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
        raise FileNotFoundError(
            f"No cached zip matching PNADC_{period}*.zip in {RAW_DIR}.\n"
            f"Available zips: {sorted(p.name for p in RAW_DIR.glob('PNADC_*.zip'))}\n"
            f"Run: python etl/pnadc_microdata.py {period}  to download it."
        )
    return candidates[-1]


def load_microdata(period: str) -> pd.DataFrame:
    full_specs = load_full_specs()
    specs = {v: full_specs[v] for v in PROBE_VARS if v in full_specs}
    missing = [v for v in PROBE_VARS if v not in full_specs]
    if missing:
        log.warning("Variables missing from dictionary: %s", missing)
    log.info("loaded specs for %d variables", len(specs))
    for v in ["V4010", "V4012", "V4019"]:
        if v in specs:
            log.info("  %s position: start=%d, end=%d  (width=%d)",
                     v, specs[v][0], specs[v][1], specs[v][1] - specs[v][0] + 1)
        else:
            log.warning("  %s NOT in dictionary — abort", v)
            raise SystemExit(1)

    zip_path = cached_microdata_zip(period)
    log.info("microdata zip: %s (%d MB)",
             zip_path, zip_path.stat().st_size // 1024 // 1024)
    txt_path = extract_txt(zip_path)

    colspecs = [(s - 1, e) for (s, e) in specs.values()]
    names = list(specs.keys())
    log.info("streaming %s in chunks…", txt_path.name)

    # NO domestic-worker filter here — we want the autonomous subset
    chunks = []
    reader = pd.read_fwf(txt_path, colspecs=colspecs, names=names,
                         dtype=str, keep_default_na=False, chunksize=200_000)
    for i, chunk in enumerate(reader):
        chunks.append(chunk)
        if (i + 1) % 5 == 0:
            log.info("  %d chunks · %d rows so far",
                     i + 1, sum(len(c) for c in chunks))
    df = pd.concat(chunks, ignore_index=True)
    log.info("loaded %d total rows", len(df))
    return df


def main():
    period = sys.argv[1] if len(sys.argv) > 1 else None
    if period is None:
        cached = sorted(RAW_DIR.glob("PNADC_*.zip"))
        cached = [p for p in cached if "Dicion" not in p.name]
        if not cached:
            raise SystemExit("No cached PNADC zip found. Run pnadc_microdata.py first.")
        # Extract period from filename: PNADC_<period>_*.zip or PNADC_<period>.zip
        import re
        m = re.match(r"PNADC_(\d{6})", cached[-1].name)
        period = m.group(1) if m else None
        if period is None:
            raise SystemExit(f"Cannot extract period from {cached[-1].name}")
    log.info("PROBE for period %s", period)

    df = load_microdata(period)

    print(f"\n## Gate 1 — Variable positions for {period}\n")
    full_specs = load_full_specs()
    print("| Var | start | end | width |")
    print("|---|---:|---:|---:|")
    for v in ["V4010", "V4012", "V4019"]:
        if v in full_specs:
            s, e = full_specs[v]
            print(f"| {v} | {s} | {e} | {e - s + 1} |")
        else:
            print(f"| {v} | — | — | NOT FOUND |")

    # ---- Gate 2: V4019 conditional on autonomous subset ----
    print(f"\n## Gate 2 — V4019 distribution conditional on VD4009 ∈ {{08,09}}\n")
    auto = df[df["VD4009"].isin(AUTONOMY_CODES.keys())].copy()
    print(f"  N autonomous rows (empregador + conta-própria): {len(auto):,}")
    print(f"  N total rows: {len(df):,}")
    print(f"  Autonomous share: {100*len(auto)/len(df):.1f}%\n")

    # V4019 value distribution within autonomous subset
    v4019 = auto["V4019"].astype(str).str.strip()
    print("| V4019 value | n | % |")
    print("|---|---:|---:|")
    dist = v4019.value_counts(dropna=False).head(10)
    for val, n in dist.items():
        pct = 100 * n / len(auto)
        marker = ""
        if val == "1":
            marker = "  ← Sim (CNPJ)"
        elif val == "2":
            marker = "  ← Não (sem CNPJ)"
        elif val in ("", "nan", "NaN"):
            marker = "  ← MISSING / blank"
        print(f"| `{val!r}` | {n:,} | {pct:.1f}%{marker} |")

    n_valid = v4019.isin(["1", "2"]).sum()
    n_blank = ((v4019 == "") | (v4019 == " ")).sum()
    print(f"\n  V4019 ∈ {{1,2}}: {n_valid:,} of {len(auto):,} ({100*n_valid/len(auto):.1f}%)")
    print(f"  V4019 blank:    {n_blank:,} of {len(auto):,} ({100*n_blank/len(auto):.1f}%)")
    gate2_pass = n_valid / max(len(auto), 1) >= 0.85
    print(f"\n  **GATE 2: {'✓ PASS' if gate2_pass else '✗ FAIL'}** "
          f"(need ≥85% valid V4019 in the autonomous subset)")
    if not gate2_pass:
        print("  Likely cause: wrong byte position for V4019. Check dictionary parser.")

    # ---- Gate 3: V4010 top codes among conta-própria ----
    print("\n## Gate 3 — V4010 top codes among conta-própria (VD4009='09')\n")
    cp = auto[auto["VD4009"] == "09"]
    print(f"  N conta-própria rows: {len(cp):,}\n")
    v4010 = cp["V4010"].astype(str).str.strip().str[:4]   # first 4 digits
    top = v4010.value_counts().head(20)
    print("| V4010 (4-digit) | n | % | CBO-adjacent? |")
    print("|---|---:|---:|---|")
    for code, n in top.items():
        pct = 100 * n / len(cp)
        adj = CBO_DOMESTIC_ADJACENT.get(code, "")
        marker = f"  ★ `{adj}`" if adj else ""
        print(f"| `{code}` | {n:,} | {pct:.2f}%{marker} |")

    adj_total = sum(n for code, n in v4010.value_counts().items()
                    if code in CBO_DOMESTIC_ADJACENT)
    adj_pct = 100 * adj_total / max(len(cp), 1)
    print(f"\n  Domestic-adjacent CBO total: {adj_total:,} ({adj_pct:.1f}% of conta-própria)")
    gate3_pass = any(c in CBO_DOMESTIC_ADJACENT for c in top.index)
    print(f"\n  **GATE 3: {'✓ PASS' if gate3_pass else '✗ FAIL'}** "
          f"(at least one CBO-adjacent code in top 20)")

    # ---- Gate 4: spec-magnitude check on CBO 5162 (caregivers) ----
    print("\n## Gate 4 — Spec sanity: CBO 5162 (caregiver) cells\n")
    cuid = cp[v4010.values == "5162"]
    if len(cuid) == 0:
        print("  ⚠ No CBO 5162 rows in this quarter. Either too small a sample,")
        print("    or the CBO bucket has shifted in CBO-2022.")
        gate4_pass = False
    else:
        cuid_v4019 = cuid["V4019"].astype(str).str.strip()
        n_with_cnpj = (cuid_v4019 == "1").sum()
        n_total_valid = cuid_v4019.isin(["1", "2"]).sum()
        weight = pd.to_numeric(cuid["V1028"], errors="coerce")
        if weight.max() > 1e9:
            weight = weight / 1e9
        w_with_cnpj = weight[cuid_v4019 == "1"].sum()
        w_valid = weight[cuid_v4019.isin(["1", "2"])].sum()
        pct_unw = 100 * n_with_cnpj / max(n_total_valid, 1)
        pct_w = 100 * w_with_cnpj / max(w_valid, 1)
        print(f"  N CBO 5162 conta-própria rows: {len(cuid):,}")
        print(f"  With valid V4019: {n_total_valid:,}")
        print(f"  With CNPJ (unweighted): {n_with_cnpj:,} ({pct_unw:.1f}%)")
        print(f"  With CNPJ (weighted):   {pct_w:.1f}%")
        print(f"  Weighted total: ~{w_valid/1000:.0f}k workers")
        # Spec gate: 15-25% expected
        gate4_pass = 10 <= pct_w <= 35
        print(f"\n  **GATE 4: {'✓ PASS' if gate4_pass else '✗ FAIL'}** "
              f"(weighted %CNPJ inside CBO 5162 should be 10-35%; got {pct_w:.1f}%)")

    # ---- Persist summary for downstream ----
    out_path = Path(__file__).parent.parent / "chapter" / "probe_mei_vars_result.json"
    out_path.parent.mkdir(exist_ok=True, parents=True)
    result = {
        "period": period,
        "n_total_rows": int(len(df)),
        "n_autonomous_rows": int(len(auto)),
        "n_conta_propria_rows": int(len(cp)),
        "var_positions": {
            v: list(full_specs[v]) if v in full_specs else None
            for v in ["V4010", "V4012", "V4019"]
        },
        "v4019_validity_in_autonomous_pct": round(100*n_valid/max(len(auto),1), 2),
        "cbo_adjacent_pct_in_cp": round(adj_pct, 2),
        "gates": {
            "gate2_v4019_valid": bool(gate2_pass),
            "gate3_cbo_present": bool(gate3_pass),
            "gate4_cuidadora_pct_cnpj": bool(gate4_pass),
        },
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\nResult JSON written to {out_path}")

    # ---- Final verdict ----
    all_pass = gate2_pass and gate3_pass and gate4_pass
    print("\n" + "=" * 60)
    print(f"OVERALL: {'✓ ALL GATES PASSED — safe to implement build_autonomous_rows()'
                     if all_pass
                     else '✗ ONE OR MORE GATES FAILED — investigate before proceeding'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
