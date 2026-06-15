"""
probe_survey_b_union.py — Pesquisa B Q32 (filiação sindical)
=============================================================

Reads the raw Survey B XLSX file and finds the union-membership
question(s). Reports column matches, then computes:
  - overall % filiadas / não / sem resposta
  - by race group (negras vs nao_negras)
  - by faixa etária (5 bands)
  - by tem_carteira (direct Q13)

This is the third "scale" in the three-scale contrast:
  1. PNADC-A 2024 — all BR domestic workers      → 2,60%
  2. RAIS / PNADC-A formal-only                  → pending
  3. STDMSP network (Survey B Q32) n≤241         → THIS SCRIPT

The third figure is expected to be significantly higher than
the PNADC baseline due to selection bias: respondents are women
in contact with the union via a face-to-face interview circuit.

USAGE
-----
    python etl/probe_survey_b_union.py
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import pandas as pd


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("probe_survey_b_union")


ROOT = Path(__file__).parent.parent
FILE_B = ROOT / "Final version May_2023.xlsx"
OUT_DIR = ROOT / "chapter" / "survey_harmonized"


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def norm_text(s) -> str:
    if pd.isna(s):
        return ""
    return strip_accents(str(s)).strip().lower()


def norm_race(v):
    if pd.isna(v):
        return None
    s = strip_accents(str(v).strip().lower())
    mapping = {
        "preta": "preta", "preto": "preta",
        "parda": "parda", "pardo": "parda",
        "branca": "branca", "branco": "branca",
        "amarela": "amarela", "amarelo": "amarela",
        "indigena": "indigena",
    }
    return mapping.get(s)


def race_group(race):
    if race in ("preta", "parda"):
        return "negras"
    if race in ("branca", "amarela", "indigena"):
        return "nao_negras"
    return None


def norm_sim_nao(v):
    s = norm_text(v)
    if not s:
        return None
    if s.startswith(("sim", "s ", "yes")):
        return "Sim"
    if s.startswith(("nao", "no ", "n ")):
        return "Nao"
    if s == "n":
        return "Nao"
    if s == "s":
        return "Sim"
    return None


def main():
    log.info("loading Survey B from %s", FILE_B)
    df = pd.read_excel(FILE_B)
    n = len(df)
    log.info("loaded %d rows × %d columns", n, df.shape[1])

    # ---- Step 1: find columns about sindical/filiação ----
    KEYWORDS = ["sindic", "filiad", "associad", "vinculad"]
    matches = []
    for col in df.columns:
        col_norm = norm_text(col)
        for kw in KEYWORDS:
            if kw in col_norm:
                matches.append((col, kw))
                break

    print("\n## Pesquisa B — Colunas com palavras-chave sindical/filiação\n")
    if not matches:
        print("(nenhuma coluna encontrada — listando primeiros 50 cabeçalhos)\n")
        for i, c in enumerate(df.columns[:50]):
            print(f"  {i:3d}. {c}")
        return
    print("| # | Coluna | Keyword |")
    print("|---|---|---|")
    for i, (col, kw) in enumerate(matches, 1):
        # Truncate very long column headers for the table
        short = col if len(col) <= 90 else col[:87] + "..."
        print(f"| {i} | {short} | `{kw}` |")

    # ---- Step 2: for each candidate, show value distribution ----
    print("\n## Distribuição de respostas por coluna candidata\n")
    for col, kw in matches:
        print(f"### `{col[:120]}`\n")
        vc = df[col].astype(str).replace("nan", pd.NA).dropna()
        if len(vc) == 0:
            print("(0 respostas válidas)\n")
            continue
        # Show top 10 distinct answers
        top = vc.value_counts().head(15)
        print(f"  n válidas: {len(vc)} de {n} ({100*len(vc)/n:.1f}%)\n")
        print("  | Resposta | n |")
        print("  |---|---:|")
        for v, c in top.items():
            v_show = str(v)[:80]
            print(f"  | {v_show} | {c} |")
        print()

    # ---- Step 3: if exactly one candidate looks binary Sim/Não, compute headline ----
    binary_candidates = []
    for col, kw in matches:
        vals = df[col].apply(norm_sim_nao)
        n_valid = vals.notna().sum()
        if n_valid >= 50:
            binary_candidates.append((col, vals, n_valid))

    if not binary_candidates:
        log.warning("No clearly binary Sim/Não union question found among candidates.")
        return

    # Pick the candidate with the most valid responses (likely the canonical Q)
    binary_candidates.sort(key=lambda t: t[2], reverse=True)
    col_chosen, vals_chosen, n_valid = binary_candidates[0]
    print(f"\n## Headline — coluna escolhida (mais respostas válidas):\n")
    print(f"`{col_chosen}`\n")
    print(f"n válidas: {n_valid} de {n}\n")

    n_sim = (vals_chosen == "Sim").sum()
    n_nao = (vals_chosen == "Nao").sum()
    print(f"- Filiadas (Sim): **{n_sim}** ({100*n_sim/n_valid:.1f}%)")
    print(f"- Não filiadas (Não): {n_nao} ({100*n_nao/n_valid:.1f}%)")

    # ---- Step 4: cross-tabs ----
    df_work = df.copy()
    df_work["filiada"] = vals_chosen
    # Race
    raca_col_candidates = [c for c in df.columns if "origem" in norm_text(c) or "raca" in norm_text(c)]
    if raca_col_candidates:
        raca_col = raca_col_candidates[0]
        df_work["raca_etnia"] = df_work[raca_col].apply(norm_race)
        df_work["raca_grupo"] = df_work["raca_etnia"].apply(race_group)

        print("\n### Filiação × raça (grupo)\n")
        print("| Grupo | n válidas | n filiadas | % filiadas |")
        print("|---|---:|---:|---:|")
        for grp in ["negras", "nao_negras"]:
            sub = df_work[(df_work["raca_grupo"] == grp) & df_work["filiada"].notna()]
            if len(sub) == 0:
                continue
            n_fil = (sub["filiada"] == "Sim").sum()
            pct = 100 * n_fil / len(sub) if len(sub) else 0
            print(f"| {grp} | {len(sub)} | {n_fil} | {pct:.1f}% |")

    # Carteira
    carteira_col_candidates = [c for c in df.columns
                               if "carteira" in norm_text(c) and "assinada" in norm_text(c)]
    if not carteira_col_candidates:
        # broader search
        carteira_col_candidates = [c for c in df.columns if "13" in c and "carteira" in norm_text(c)]
    if carteira_col_candidates:
        car_col = carteira_col_candidates[0]
        df_work["tem_carteira"] = df_work[car_col].apply(norm_sim_nao)

        print("\n### Filiação × tem carteira (Q13)\n")
        print("| Carteira | n válidas | n filiadas | % filiadas |")
        print("|---|---:|---:|---:|")
        for carteira in ["Sim", "Nao"]:
            sub = df_work[(df_work["tem_carteira"] == carteira) & df_work["filiada"].notna()]
            if len(sub) == 0:
                continue
            n_fil = (sub["filiada"] == "Sim").sum()
            pct = 100 * n_fil / len(sub) if len(sub) else 0
            label = "com_carteira" if carteira == "Sim" else "sem_carteira"
            print(f"| {label} | {len(sub)} | {n_fil} | {pct:.1f}% |")

    # ---- Step 5: persist a small CSV for downstream use ----
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    persist = pd.DataFrame({
        "respondent_anon_id": [f"B-{i:03d}" for i in range(1, n + 1)],
        "q_filiacao_raw": df[col_chosen].values,
        "filiada_norm": vals_chosen.values,
    })
    out_path = OUT_DIR / "survey_b_q32_union.csv"
    persist.to_csv(out_path, index=False)
    log.info("persisted normalized filiação column → %s", out_path)


if __name__ == "__main__":
    main()
