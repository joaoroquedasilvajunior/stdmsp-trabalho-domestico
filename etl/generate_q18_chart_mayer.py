"""
generate_q18_chart_mayer.py
===========================

Chart Q18 usando a categorização MANUAL do JF Mayer (arquivo enviado
2026-07-03: q18_categorized.xlsx com 215 respostas categorizadas à mão).

Fonte de verdade: q18_categorized.xlsx  (upload do Mayer)
  colunas: respondent_anon_id, raw_text, categoria_num, categoria_label

Junta com o XLSX original pelo raw_text para preservar a variável de raça
(Q3), e roda o crosstab afro/branca/total.

Comparação com minha heurística automatizada:
  Cat 1 Defesa:      Mayer 64 vs eu 47  (Mayer captura mais 'direitos'
                                          gerais, além de 'defesa/defender')
  Cat 2 Orientação:  Mayer 30 vs eu 25
  Cat 3 Jurídico:    Mayer 23 vs eu 24  (Mayer prioriza Cat 3 sobre Cat 1
                                          quando aparecem termos legais)
  Cat 4 Cuidado:     Mayer 13 vs eu 16
  Cat 5 Residual:    Mayer 85 vs eu 103

Output:
    chapter/survey_a_analysis/Q12_union_function.png  (+ .pdf)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams


# ============================================================
# STYLE
# ============================================================
rcParams['font.family']       = 'serif'
rcParams['font.size']         = 10
rcParams['axes.linewidth']    = 0.7
rcParams['axes.spines.top']   = False
rcParams['axes.spines.right'] = False
rcParams['axes.edgecolor']    = '#222222'
rcParams['xtick.color']       = '#222222'
rcParams['ytick.color']       = '#222222'
rcParams['pdf.fonttype']      = 42
rcParams['ps.fonttype']       = 42

COL_AFRO       = '#b91c1c'    # accent red — afro-descendentes
COL_BRANCA     = '#475569'    # slate — brancas
COL_TOTAL      = '#9ca3af'    # gray médio — total race-known (afro+brancas)
COL_TOTAL_ALL  = '#cbd5e1'    # gray claro — total geral (todo Q18, inclui outras + sem raça)


ROOT = Path(__file__).parent.parent
SURVEY_XLSX = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
MAYER_XLSX  = Path("/sessions/stoic-great-hamilton/mnt/uploads/q18_categorized.xlsx")
# Fallback: if the upload path isn't reachable in a future run, copy the file
# to etl/ and update this constant.

OUT_DIR = ROOT / "chapter" / "survey_a_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PNG = OUT_DIR / "Q12_union_function.png"


# ============================================================
# UTILS
# ============================================================

def find_col(df: pd.DataFrame, prefix: str) -> str:
    for c in df.columns:
        if c.startswith(prefix):
            return c
    raise KeyError(f"No column starting with {prefix!r}")


def pct_pt(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:.1f}%".replace(".", ",")


def race_group(v):
    if pd.isna(v):
        return None
    s = str(v).strip().lower()
    if s in ("pardo", "parda", "preto", "preta"):
        return "afro"
    if s in ("branco", "branca"):
        return "branca"
    return "outras"


def wrap_label(s: str, width: int = 32) -> str:
    s = str(s)
    return "\n".join(textwrap.wrap(s, width=width)) or s


# ============================================================
# LOAD + JOIN
# ============================================================

def norm(s):
    """Normalize text for join matching.

    Colapsa espaços múltiplos + strip + lowercase.  Fix 2026-07-03 pra
    recuperar 1 resposta que estava presa por causa de "atendimento sim,  mas"
    (dois espaços) no XLSX original vs "atendimento sim, mas" (um espaço) no
    arquivo de categorização do Mayer.
    """
    if pd.isna(s):
        return None
    import re
    return re.sub(r"\s+", " ", str(s).strip().lower())


def load_data():
    """Join Mayer's manual categorization back to the original survey rows.

    Strategy: since many Q18 responses are TEXTUALLY IDENTICAL across
    respondents (e.g. "Defender os nossos direitos" was written by 3-4
    women independently), we cannot do a naive text-based join without
    exploding the row count.

    Assumption we validate: Mayer's manual categorization is
    text-deterministic — the same raw_text always gets the same category.
    So we deduplicate Mayer's file on normalized raw_text, then left-join
    each survey row (with non-null Q18) to that dedup lookup.
    """
    # Mayer's categorization
    m = pd.read_excel(MAYER_XLSX)
    m = m[["respondent_anon_id","raw_text","categoria_num","categoria_label"]].dropna(subset=["raw_text"])
    m["_norm"] = m["raw_text"].apply(norm)
    m["categoria_num"] = m["categoria_num"].astype(int)

    # Validate: does any raw_text get 2+ distinct categories?
    dup_cats = (m.groupby("_norm")["categoria_num"].nunique() > 1)
    if dup_cats.any():
        print("⚠  Texts with inconsistent Mayer categories:")
        for txt in dup_cats[dup_cats].index:
            print(f"   {txt!r}  →  {m[m['_norm']==txt]['categoria_num'].unique()}")

    # Dedup Mayer on normalized text (keep first)
    m_dedup = m.drop_duplicates("_norm", keep="first")[["_norm","categoria_num","categoria_label"]]

    # Original survey — keep every row with a non-null Q18 response
    s = pd.read_excel(SURVEY_XLSX)
    q3_col  = find_col(s, "3 -")
    q18_col = find_col(s, "18 -")
    s["race_group"] = s[q3_col].apply(race_group)
    s["_norm"] = s[q18_col].apply(norm)
    s = s[["_norm","race_group"]].dropna(subset=["_norm"])
    s = s[s["_norm"] != ""].copy()

    # Left-join survey → Mayer's dedup lookup
    merged = s.merge(m_dedup, on="_norm", how="left")
    n_no_cat = merged["categoria_num"].isna().sum()
    if n_no_cat:
        print(f"⚠  {n_no_cat} survey responses without a Mayer category "
              f"(text differences?). Excluding from chart.")
        # Show them so we can diagnose
        for txt in merged.loc[merged["categoria_num"].isna(), "_norm"].unique()[:10]:
            print(f"     {txt!r}")

    merged = merged.dropna(subset=["categoria_num"])
    merged["categoria_num"] = merged["categoria_num"].astype(int)
    return merged


# ============================================================
# CROSSTAB
# ============================================================

def crosstab_by_race(df: pd.DataFrame) -> pd.DataFrame:
    """Crosstab 4-way: afro, branca, total race-known (afro+brancas),
    total geral (todos que responderam Q18, inclui outras e sem raça)."""
    rows = []
    # Build the Mayer label lookup once
    label_lookup = {}
    for cat_num in [1, 2, 3, 4, 5]:
        m = df[df["categoria_num"] == cat_num]
        if not m.empty:
            label_lookup[cat_num] = m["categoria_label"].iloc[0]

    for cat_num in [1, 2, 3, 4, 5]:
        row = {"cat_num": cat_num, "cat_label": label_lookup.get(cat_num, "")}
        for grp in ["afro", "branca", "total_race_known", "total_all"]:
            if grp == "total_race_known":
                mask = df["race_group"].isin(["afro", "branca"])
            elif grp == "total_all":
                mask = pd.Series(True, index=df.index)   # todo mundo do Mayer
            else:
                mask = df["race_group"] == grp
            n_grp = mask.sum()
            n_cat = (mask & (df["categoria_num"] == cat_num)).sum()
            pct = 100 * n_cat / n_grp if n_grp else None
            row[f"{grp}_n"] = int(n_cat)
            row[f"{grp}_pct"] = pct
        rows.append(row)
    return pd.DataFrame(rows)


# ============================================================
# CHART
# ============================================================

def render_chart(df_xtab: pd.DataFrame, title: str, subtitle: str,
                 out_path: Path) -> None:
    afro   = df_xtab["afro_pct"].tolist()
    branca = df_xtab["branca_pct"].tolist()
    total  = df_xtab["total_race_known_pct"].tolist()
    n_cats = len(afro)

    # Prefix labels with cat number for consistency with prior version
    cats = [f"{i}. {label}" for i, label in zip(df_xtab["cat_num"], df_xtab["cat_label"])]

    wrapped = [wrap_label(c, width=32) for c in cats]
    extra_lines = sum(max(0, w.count("\n")) for w in wrapped)
    fig_h = max(3.4, 0.95 * n_cats + 1.8 + 0.18 * extra_lines)
    fig, ax = plt.subplots(figsize=(8.8, fig_h))

    y = np.arange(n_cats)
    bar_h = 0.22

    ax.barh(y + bar_h, afro,   bar_h, color=COL_AFRO,
            label=f'Afro-descendentes (n={int(sum(df_xtab["afro_n"]))})',
            edgecolor='white', linewidth=0.6)
    ax.barh(y,        branca, bar_h, color=COL_BRANCA,
            label=f'Brancas (n={int(sum(df_xtab["branca_n"]))})',
            edgecolor='white', linewidth=0.6)
    ax.barh(y - bar_h, total,  bar_h, color=COL_TOTAL,
            label=f'Total (n={int(sum(df_xtab["total_race_known_n"]))})',
            edgecolor='white', linewidth=0.6)

    MIN_LABEL_PCT = 1.5
    def label_bars(vals, offset):
        for i, v in enumerate(vals):
            if v is None or pd.isna(v) or v < MIN_LABEL_PCT:
                continue
            ax.text(v + 0.8, i + offset, pct_pt(v),
                    va='center', fontsize=8.5, color='#1a252f')
    label_bars(afro,   bar_h)
    label_bars(branca, 0)
    label_bars(total,  -bar_h)

    ax.set_yticks(y)
    ax.set_yticklabels(wrapped, fontsize=9.5)
    ax.invert_yaxis()

    max_val = max((v for v in afro + branca + total if v is not None), default=0)
    upper = int(min(100, max(40, np.ceil((max_val + 10) / 10) * 10)))
    ax.set_xlim(0, upper)
    xticks = list(range(0, upper + 1, 10))
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{t}%" for t in xticks], fontsize=9)
    ax.set_xlabel('% dentro do grupo racial', fontsize=10, labelpad=10)
    ax.grid(axis='x', linestyle=':', linewidth=0.4, color='#bbbbbb', alpha=0.6)
    ax.set_axisbelow(True)

    ax.legend(loc='lower left', bbox_to_anchor=(0, 1.04), ncol=3,
              fontsize=9, framealpha=0,
              handlelength=1.4, columnspacing=1.5, handletextpad=0.5)

    ax.text(0, 1.22, title, transform=ax.transAxes,
            fontsize=11.5, fontweight='bold', color='#1a252f')
    if subtitle:
        ax.text(0, 1.16, subtitle, transform=ax.transAxes,
                fontsize=9, color='#6b7280', style='italic')

    plt.subplots_adjust(left=0.30, top=0.82, bottom=0.13, right=0.96)
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(out_path.with_suffix('.pdf'),
                bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ============================================================
# MAIN
# ============================================================

def main():
    df = load_data()
    print(f"Loaded {len(df)} categorized responses from Mayer's file")

    xt = crosstab_by_race(df)
    print("\nDistribuição Q18 (categorização Mayer):")
    print(xt[["cat_num","cat_label","afro_n","afro_pct",
              "branca_n","branca_pct",
              "total_race_known_n","total_race_known_pct"]].to_string(index=False))

    render_chart(
        xt,
        title='Q18 — Função mais importante do sindicato (5 categorias)',
        subtitle='',
        out_path=OUT_PNG,
    )
    print(f"\nChart saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
