"""
build_dw_union_json.py — Converts fact_union_timeseries.csv into the
JSON shape used by dashboard/index.html and writes it to
dashboard/data/dw_union.json + bumps the manifest.

The output is a list of records keyed by (year, cut, group), mirroring
the long-format CSV but with friendlier camel/snake fields and PT/EN
display labels for direct rendering in Chart.js.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


ROOT = Path(__file__).parent.parent
SRC = ROOT / "dashboard" / "data" / "fact_union_timeseries.csv"
OUT_LIST = ROOT / "dashboard" / "data" / "dw_union.json"
OUT_EXTRAS = ROOT / "dashboard" / "data" / "union_extras.json"
MANIFEST = ROOT / "dashboard" / "data" / "manifest.json"


# Static facts from Survey B Q32 — the STDMSP entorno ceiling
SURVEY_B_Q32 = {
    "n_valid": 231,
    "n_filiadas": 72,
    "pct_filiadas": 31.2,
    "by_race": {
        "negras":     {"n": 157, "n_filiadas": 44, "pct": 28.0},
        "nao_negras": {"n":  69, "n_filiadas": 26, "pct": 37.7},
    },
    "by_carteira": {
        "com_carteira": {"n": 114, "n_filiadas": 46, "pct": 40.4},
        "sem_carteira": {"n": 114, "n_filiadas": 24, "pct": 21.1},
    },
    "source": "Pesquisa B (STDMSP, 2021-23, n=241)",
}


# Labels for display
GROUP_LABELS = {
    "all":                       {"pt": "Total Brasil",          "en": "Brazil total"},
    "negras":                    {"pt": "Negras (pretas+pardas)", "en": "Black (preta+parda)"},
    "nao_negras":                {"pt": "Não-negras",            "en": "Non-Black"},
    "com_carteira":              {"pt": "Com carteira",          "en": "With signed card"},
    "sem_carteira":              {"pt": "Sem carteira",          "en": "Without signed card"},
    "negras_com_carteira":       {"pt": "Negras × com carteira",     "en": "Black × signed card"},
    "negras_sem_carteira":       {"pt": "Negras × sem carteira",     "en": "Black × no signed card"},
    "nao_negras_com_carteira":   {"pt": "Não-negras × com carteira", "en": "Non-Black × signed card"},
    "nao_negras_sem_carteira":   {"pt": "Não-negras × sem carteira", "en": "Non-Black × no signed card"},
}


def main():
    df = pd.read_csv(SRC)
    print(f"loaded {len(df)} rows from {SRC.name}")
    print(f"  years: {sorted(df.year.unique())}")
    print(f"  cuts:  {sorted(df.cut.unique())}")

    # Build the JSON records — long format, one row per (year, cut, group)
    records = []
    for _, r in df.iterrows():
        group_key = str(r["group"])
        label = GROUP_LABELS.get(group_key, {"pt": group_key, "en": group_key})
        rec = {
            "year": int(r["year"]),
            "cut": r["cut"],
            "group": group_key,
            "label_pt": label["pt"],
            "label_en": label["en"],
            "n": int(r["n"]) if pd.notna(r["n"]) else 0,
            "n_filiadas": int(r["n_filiadas_unw"]) if pd.notna(r["n_filiadas_unw"]) else 0,
            "pct_filiadas": float(r["pct_filiadas"]) if pd.notna(r["pct_filiadas"]) else None,
            "ci_lo": float(r["ci_lo"]) if pd.notna(r["ci_lo"]) else None,
            "ci_hi": float(r["ci_hi"]) if pd.notna(r["ci_hi"]) else None,
        }
        records.append(rec)
    records.sort(key=lambda x: (x["cut"], x["group"], x["year"]))

    # Headline figures for the KPI tiles
    df_overall = df[df["cut"] == "overall"].sort_values("year")
    pct_2024 = float(df_overall.loc[df_overall["year"] == 2024, "pct_filiadas"].iloc[0])
    pct_2023_floor = float(df_overall.loc[df_overall["year"] == 2023, "pct_filiadas"].iloc[0])
    pct_2016_peak = float(df_overall.loc[df_overall["year"] == 2016, "pct_filiadas"].iloc[0])

    # Absolute floor: negras × com_carteira 2024
    df_rxf = df[df["cut"] == "race_x_formality"]
    pct_floor_absolute = float(df_rxf.loc[
        (df_rxf["year"] == 2024) & (df_rxf["group"] == "negras_com_carteira"),
        "pct_filiadas"
    ].iloc[0])

    headline = {
        "pct_baseline_2024":      round(pct_2024, 2),
        "pct_floor_2023":         round(pct_2023_floor, 2),
        "pct_peak_2016":          round(pct_2016_peak, 2),
        "pct_floor_absolute":     round(pct_floor_absolute, 2),
        "pct_stdmsp_entorno":     SURVEY_B_Q32["pct_filiadas"],
        "ratio_entorno_floor":    round(SURVEY_B_Q32["pct_filiadas"] / pct_floor_absolute, 1),
        "ratio_entorno_baseline": round(SURVEY_B_Q32["pct_filiadas"] / pct_2024, 1),
    }

    # dw_union.json = flat list (matches the other views[] in the dashboard)
    OUT_LIST.parent.mkdir(parents=True, exist_ok=True)
    OUT_LIST.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"wrote {OUT_LIST}  ({len(records)} rows)")

    # union_extras.json = headline + Survey B (separate fetch in dashboard,
    # mirroring the wage_contract_snapshot.json convention)
    extras = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": ("PNADC Anual Visita 1, variável V4097 (associação a sindicato), "
                   "2012-2024 (anos 2020-2021 indisponíveis na PNADC-A V1 por interrupção "
                   "de campo COVID). Cálculos ponderados por V1032."),
        "n_years": int(df["year"].nunique()),
        "years": sorted([int(y) for y in df["year"].unique()]),
        "headline": headline,
        "survey_b_q32": SURVEY_B_Q32,
    }
    OUT_EXTRAS.write_text(json.dumps(extras, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(f"wrote {OUT_EXTRAS}")
    print(f"  headline.pct_baseline_2024={headline['pct_baseline_2024']}% · "
          f"headline.ratio_entorno_floor={headline['ratio_entorno_floor']}×")

    # Bump the manifest so the dashboard knows to fetch the new file
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        manifest = {"views": {}}
    manifest.setdefault("views", {})
    manifest["views"]["dw_union"] = len(records)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"updated {MANIFEST.name} (dw_union={len(records)} records)")


if __name__ == "__main__":
    main()
