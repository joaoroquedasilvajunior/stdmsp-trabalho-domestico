"""
generate_q18_chart.py
=====================

Script standalone que gera o chart Q18 (função mais importante do sindicato)
disaggregado por raça.  Extrai os pedaços relevantes de analyze_survey_a.py
num arquivo isolado — pode rodar sozinho com:

    python3 etl/generate_q18_chart.py

Fonte:
    ROOT/"Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"

Output:
    chapter/survey_a_analysis/Q12_union_function.png  (+ .pdf)

Categorização:
    5 buckets (1-5).  Heurística keyword-first com prioridade Cat 1 → 5.
    Correção 2026-07-03 pós-auditoria: usa RADICAIS para capturar todas as
    flexões verbais (cuid, proteg, acolh, ampar, defend, orient, inform,
    esclarec, divulg, conscientiz, fiscaliz, cobr, jurídic).

Recortes raciais:
    afro          → Pardo + Preto    (~n=140 total, ~n=123 com resposta Q18)
    branca        → Branco           (~n=93 total, ~n=84 com resposta Q18)
    total_race_known = afro + branca
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams


# ============================================================
# STYLE — paleta consistente com os outros charts do projeto
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

COL_AFRO   = '#b91c1c'    # vermelho accent — afro-descendentes
COL_BRANCA = '#475569'    # slate — brancas
COL_TOTAL  = '#9ca3af'    # cinza — total de referência


ROOT = Path(__file__).parent.parent
SRC  = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT_DIR = ROOT / "chapter" / "survey_a_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PNG = OUT_DIR / "Q12_union_function.png"


# ============================================================
# UTILITÁRIOS
# ============================================================

def find_col(df: pd.DataFrame, prefix: str) -> str:
    """Localiza coluna do XLSX pelo prefixo do rótulo Google Forms."""
    for c in df.columns:
        if c.startswith(prefix):
            return c
    raise KeyError(f"Nenhuma coluna começa com {prefix!r}")


def pct_pt(v):
    """Formata percentual em pt-BR (vírgula decimal)."""
    if v is None or pd.isna(v):
        return "—"
    return f"{v:.1f}%".replace(".", ",")


def add_race_group(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona coluna 'race_group' com afro / branca / outras / None."""
    race_col = find_col(df, "3 -")
    def cls(v):
        if pd.isna(v):
            return None
        s = str(v).strip().lower()
        if s in ("pardo", "parda", "preto", "preta"):
            return "afro"
        if s in ("branco", "branca"):
            return "branca"
        return "outras"
    df = df.copy()
    df["race_group"] = df[race_col].apply(cls)
    return df


def wrap_label(s: str, width: int = 32) -> str:
    """Quebra rótulos longos em múltiplas linhas."""
    s = str(s)
    return "\n".join(textwrap.wrap(s, width=width)) or s


# ============================================================
# CATEGORIZAÇÃO Q18 (5 buckets, heurística por radicais)
# ============================================================

Q18_BUCKETS = {
    "1": "1. Defesa dos direitos trabalhistas",
    "2": "2. Orientação sobre direitos",
    "3": "3. Apoio jurídico e cobrança dos patrões",
    "4": "4. Cuidado, proteção e acolhimento",
    "5": "5. Todas / não sabe / vago",
}


def categorize_q18(s):
    """Categoriza uma resposta livre de Q18 em 1-5.

    Prioridade: Cat 1 → 2 → 3 → 4 → 5 (residual).
    Primeira lista de keywords que casar com o texto define a categoria.
    Não há sobreposição — cada resposta cai em UMA categoria só.
    """
    if s is None or pd.isna(s):
        return None
    text = str(s).strip().lower()
    if not text:
        return None

    # Cat 1: Defesa dos direitos trabalhistas
    if any(kw in text for kw in [
            "defend", "defesa", "direitos trabalh", "lutar pelo bem",
            "lutar pelos direitos", "garantir o que o trabalho",
            "garantia dos direitos", "garantir o direito",
            "buscar direitos", "buscar os direitos"]):
        return "1"

    # Cat 2: Orientação sobre direitos
    if any(kw in text for kw in [
            "orient", "inform", "esclarec", "esclaresc",
            "divulg", "conscientiz", "instruir", "ensinar", "valoriza"]):
        return "2"

    # Cat 3: Apoio jurídico e cobrança dos patrões
    if any(kw in text for kw in [
            "jurídic", "advogad", "processo", "lei ", "leis",
            "judicial", "fiscaliz", "cobr", "patrão", "patrões", "empregador"]):
        return "3"

    # Cat 4: Cuidado, proteção e acolhimento
    if any(kw in text for kw in [
            "cuid", "proteg", "acolh", "ampar",
            "apoio", "apoiar", "suporte", "ajudar todos",
            "ajudar nas necessidades", "ajudar quem precis"]):
        return "4"

    # Cat 5: residual
    return "5"


# ============================================================
# CROSSTAB — resposta × grupo racial (% dentro do grupo)
# ============================================================

def crosstab(df: pd.DataFrame, col: str, order=None) -> pd.DataFrame:
    """Cross-tab com % dentro do grupo racial.  Colunas: afro, branca, total."""
    sub = df[[col, "race_group"]].dropna(subset=[col]).copy()
    sub[col] = sub[col].astype(str).str.strip()
    if order is None:
        order = sub[col].value_counts().index.tolist()

    rows = []
    for cat in order:
        row = {"category": cat}
        for grp in ["afro", "branca", "total_race_known"]:
            if grp == "total_race_known":
                mask = sub["race_group"].isin(["afro", "branca"])
            else:
                mask = sub["race_group"] == grp
            n_in_grp_total = mask.sum()
            n_cat = (mask & (sub[col] == cat)).sum()
            pct = 100 * n_cat / n_in_grp_total if n_in_grp_total else None
            row[f"{grp}_n"] = int(n_cat)
            row[f"{grp}_pct"] = pct
        rows.append(row)
    return pd.DataFrame(rows)


# ============================================================
# CHART — barras horizontais grupadas afro/branca/total
# ============================================================

def render_chart(df_xtab: pd.DataFrame, title: str, subtitle: str,
                 out_path: Path) -> None:
    """Barra horizontal 3-way: afro (vermelho), branca (slate), total (cinza)."""
    cats   = df_xtab["category"].tolist()
    afro   = df_xtab["afro_pct"].tolist()
    branca = df_xtab["branca_pct"].tolist()
    total  = df_xtab["total_race_known_pct"].tolist()
    n_cats = len(cats)

    # Quebra os rótulos longos e calcula altura da figura
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

    # Rótulos das % no final de cada barra (≥ 1.5%)
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
    df = pd.read_excel(SRC)
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    df = add_race_group(df)

    # Categorização Q18
    col_q18 = find_col(df, "18 -")
    df["q18_bucket"] = df[col_q18].apply(categorize_q18)

    # Crosstab bucket × raça
    bucket_order = list(Q18_BUCKETS.keys())
    xt = crosstab(df, "q18_bucket", order=bucket_order)
    xt["category"] = xt["category"].map(Q18_BUCKETS)

    # Distribuição no console
    print("\nDistribuição Q18 (n com resposta = "
          f"{int(sum(xt['total_race_known_n']))}):")
    for _, r in xt.iterrows():
        print(f"  {r['category']:45s}  "
              f"afro {r['afro_n']:3d} ({pct_pt(r['afro_pct'])})  "
              f"brancas {r['branca_n']:3d} ({pct_pt(r['branca_pct'])})  "
              f"total {r['total_race_known_n']:3d} ({pct_pt(r['total_race_known_pct'])})")

    # Chart
    render_chart(
        xt,
        title='Q18 — Função mais importante do sindicato (5 categorias)',
        subtitle='',
        out_path=OUT_PNG,
    )
    print(f"\nChart saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
