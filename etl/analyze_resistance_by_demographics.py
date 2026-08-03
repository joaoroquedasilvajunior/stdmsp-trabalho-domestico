"""
analyze_resistance_by_demographics.py
=====================================

Cruza o repertório de resistência (saída/voz/evitação/lealdade/espiritualidade/
solidariedade) das passagens da Pesquisa B com a demografia da respondente.

Pergunta de fundo (para o capítulo do Mayer):
  As mulheres NEGRAS mobilizam registros de resistência diferentes das brancas?
  As MIGRANTES? As FILIADAS ao sindicato? As SEM CARTEIRA?

Entradas (todas locais, rode DEPOIS de embed_survey_b.py):
  chapter/survey_b_explorer/survey_b_resistance_scores.csv   (nível-passagem)
  chapter/survey_harmonized/survey_consolidated.xlsx          (demografia B-001..)
  Final version May_2023.xlsx                                 (Q32 filiação)

Método (importante):
  1. INTENSIDADE, NÃO RÓTULO BINÁRIO. Cada respondente responde ~21 perguntas
     abertas; se marcássemos "usa o registro" com só 1 passagem saliente,
     quase todas usariam todos os registros (satura ~100%). Em vez disso
     medimos a INTENSIDADE de cada registro no depoimento da respondente:
       - z-score de cada passagem DENTRO do conceito (torna os 6 comparáveis
         apesar de alcances diferentes: saída chega a 0,87, fé a 0,69);
       - por respondente, a MÉDIA dos z daquele conceito = quão "carregado"
         é o depoimento dela naquele registro.
  2. Comparação entre grupos: Mann-Whitney U (não-paramétrico, robusto a n
     pequeno e assimetria) sobre a intensidade média; reporta a MEDIANA de
     cada grupo + p.
  3. Também: registro DOMINANTE por respondente (maior intensidade média) —
     distribuição por grupo, como leitura complementar.

CAUTELA: n pequeno (241, menos por célula). Trate como EXPLORATÓRIO e valide
lendo as passagens (use o semantic_explorer.html). Não é confirmatório.

Saída:
  chapter/survey_b_explorer/resistance_by_demographics.md   (só agregados;
  sem citações individuais -> pode compartilhar com o Mayer)
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy import stats
except Exception:
    stats = None

ROOT = Path(__file__).parent.parent
SCORES = ROOT / "chapter" / "survey_b_explorer" / "survey_b_resistance_scores.csv"
HARM = ROOT / "chapter" / "survey_harmonized" / "survey_consolidated.xlsx"
RAWB = ROOT / "Final version May_2023.xlsx"
OUT_MD = ROOT / "chapter" / "survey_b_explorer" / "resistance_by_demographics.md"

CONCEPTS = ["saida_exit", "voz_voice", "evitacao_avoidance",
            "lealdade_loyalty", "espiritualidade_faith", "solidariedade_kin"]
CONCEPT_PT = {
    "saida_exit": "Saída", "voz_voice": "Voz", "evitacao_avoidance": "Evitação",
    "lealdade_loyalty": "Lealdade", "espiritualidade_faith": "Espiritualidade",
    "solidariedade_kin": "Solidariedade",
}
Z_SALIENT = 1.0   # limiar de saliência (z-score por conceito)


def load_respondent_profile() -> pd.DataFrame:
    """Agrega scores de passagem -> INTENSIDADE (média de z) por respondente."""
    df = pd.read_csv(SCORES)
    # z-score por conceito (comparabilidade entre conceitos)
    for c in CONCEPTS:
        mu, sd = df[c].mean(), df[c].std(ddof=0) or 1.0
        df[c + "_z"] = (df[c] - mu) / sd

    rows = []
    for anon, g in df.groupby("anon_id"):
        row = {"anon_id": anon, "n_passagens": len(g)}
        for c in CONCEPTS:
            row["z_" + c] = g[c + "_z"].mean()   # intensidade bruta do registro
        # NORMALIZAÇÃO DENTRO-DA-RESPONDENTE (row-centering): subtrai a média
        # dos 6 registros da própria respondente. Isola PARA QUAL registro ela
        # PENDE (relativo ao seu baseline de expressividade), removendo o
        # confundidor de "quem escreve mais/mais marcado pontua alto em tudo".
        base = np.mean([row["z_" + c] for c in CONCEPTS])
        for c in CONCEPTS:
            row["zc_" + c] = row["z_" + c] - base
        # registro dominante = maior intensidade (row-centering não muda o argmax)
        zmeans = {c: row["z_" + c] for c in CONCEPTS}
        row["dominante"] = max(zmeans, key=zmeans.get)
        rows.append(row)
    return pd.DataFrame(rows)


def load_demographics() -> pd.DataFrame:
    h = pd.read_excel(HARM)
    h = h[h["survey_id"] == "B"].copy()
    keep = {"respondent_anon_id": "anon_id"}
    for c in ["raca_grupo", "is_negra", "tem_carteira", "is_migrante_para_sp",
              "estado_origem_regiao", "faixa_etaria_5b", "nivel_educacao"]:
        if c in h.columns:
            keep[c] = c
    d = h[list(keep)].rename(columns=keep)

    # Q32 filiação da base bruta (B-001.. por ordem de linha)
    raw = pd.read_excel(RAWB)
    raw.insert(0, "anon_id", [f"B-{i+1:03d}" for i in range(len(raw))])
    q32 = next((c for c in raw.columns if c.strip().startswith("32 -")), None)
    if q32:
        fil = raw[["anon_id", q32]].rename(columns={q32: "filiada"})
        fil["filiada"] = fil["filiada"].map(
            lambda v: "Sim" if str(v).strip().lower() == "sim"
            else ("Não" if str(v).strip().lower() in ("não", "nao") else None))
        d = d.merge(fil, on="anon_id", how="left")
    return d


def crosstab_block(prof, demo, split_col, groups, md):
    """Bloco: intensidade mediana (z) de cada registro por grupo + Mann-Whitney."""
    m = prof.merge(demo[["anon_id", split_col]], on="anon_id", how="left")
    m = m[m[split_col].notna()]
    present = [g for g in groups if (m[split_col] == g).any()]
    if len(present) < 2:
        return
    md.append(f"\n### Por {split_col}\n")
    md.append("*Pendor relativo = mediana do z-score do registro **centrado na própria respondente** "
              "(0 = registro na média dos 6 dela; >0 = ela pende para este; <0 = pende contra). "
              "Remove o confundidor de expressividade. p = Mann-Whitney, 1º vs 2º grupo.*\n")
    header = "| Registro | " + " | ".join(
        f"{g} (n={int((m[split_col]==g).sum())})" for g in present) + " | Δ mediana / p |"
    md.append(header)
    md.append("|" + "---|" * (len(present) + 2))
    for c in CONCEPTS:
        col = "zc_" + c
        cells, medians, arrays = [], [], []
        for g in present:
            vals = m.loc[m[split_col] == g, col].dropna().values
            med = float(np.median(vals)) if len(vals) else float("nan")
            medians.append(med)
            arrays.append(vals)
            cells.append(f"{med:+.2f}")
        p = None
        if stats is not None and len(arrays[0]) and len(arrays[1]):
            try:
                _, p = stats.mannwhitneyu(arrays[0], arrays[1], alternative="two-sided")
            except ValueError:
                p = None
        delta = medians[0] - medians[1]
        star = " *" if (p is not None and p < 0.05) else ""
        dstr = f"{delta:+.2f}{star}" + (f" (p={p:.3f})" if p is not None else "")
        md.append(f"| {CONCEPT_PT[c]} | " + " | ".join(cells) + f" | {dstr} |")

    # leitura complementar: registro dominante por grupo
    md.append(f"\n*Registro dominante (maior intensidade) por grupo em {split_col}:*\n")
    md.append("| Grupo | " + " | ".join(CONCEPT_PT[c] for c in CONCEPTS) + " |")
    md.append("|" + "---|" * (len(CONCEPTS) + 1))
    for g in present:
        sub = m[m[split_col] == g]
        n = len(sub)
        counts = sub["dominante"].value_counts()
        cells = [f"{100*counts.get(c,0)/n:.0f}%" for c in CONCEPTS]
        md.append(f"| {g} (n={n}) | " + " | ".join(cells) + " |")


def main():
    prof = load_respondent_profile()
    demo = load_demographics()
    n_resp = len(prof)

    md = []
    md.append("# Repertório de resistência × demografia — Pesquisa B\n")
    md.append(f"**Respondentes:** {n_resp}  ·  **Método:** pendor relativo = z-score de cada "
              "registro **centrado na própria respondente** (remove o confundidor de "
              "expressividade — quem escreve mais/mais marcado não pontua alto em tudo).\n")
    md.append("> ⚠ Exploratório. n pequeno por célula. `*` = p<0,05 (Mann-Whitney, 1º vs 2º grupo). "
              "Validar lendo as passagens no explorador.\n")

    # Registro dominante geral (single-label, distribuição)
    md.append("\n## Registro dominante — distribuição geral\n")
    md.append("| Registro | % das respondentes |")
    md.append("|---|---:|")
    dom_counts = prof["dominante"].value_counts()
    for c in CONCEPTS:
        pct = 100 * dom_counts.get(c, 0) / n_resp
        md.append(f"| {CONCEPT_PT[c]} | {pct:.0f}% |")

    md.append("\n## Cruzamentos\n")
    crosstab_block(prof, demo, "raca_grupo", ["negras", "nao_negras"], md)
    if "filiada" in demo.columns:
        crosstab_block(prof, demo, "filiada", ["Sim", "Não"], md)
    crosstab_block(prof, demo, "tem_carteira", ["Sim", "Nao"], md)
    if "is_migrante_para_sp" in demo.columns:
        demo["migrante"] = demo["is_migrante_para_sp"].map({1: "Migrante", 1.0: "Migrante",
                                                            0: "Nativa SP", 0.0: "Nativa SP"})
        crosstab_block(prof, demo, "migrante", ["Migrante", "Nativa SP"], md)
    crosstab_block(prof, demo, "estado_origem_regiao", ["Nordeste", "Sudeste"], md)

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Relatório: {OUT_MD}")
    print("\n".join(md))


if __name__ == "__main__":
    main()
