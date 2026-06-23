"""
analyze_survey_a.py — Race-disaggregated analysis of STDMSP Survey A (2024)
=============================================================================

Reads the raw Survey A xlsx ("Condições de Trabalho para as Trabalhadoras
Domésticas (Responses).xlsx"), produces a race-disaggregated breakdown of
12 questions (Q1-Q18 with gaps), and emits:

  - chapter/survey_a_analysis/report.md           narrative + tables
  - chapter/survey_a_analysis/Q01_age.png …       12 horizontal bar charts
  - chapter/survey_a_analysis/data.csv            long-form (q, race, cat, n, pct)

Race grouping:
  - afro          → Pardo + Preto    (n=140)
  - branca        → Branco           (n=93)
  - total         → race-known       (n=233; excludes 2 Amarela/Indígena)

The 2 Amarela/Indígena and the 7 race-unknown rows are dropped from
the race breakdown but counted in the "total" of categorical questions.

Reference floors for the salary question (Q9, 2024):
  R$ 1,412.00   federal Brazil minimum wage 2024
  R$ 1,476.75   STDMSP/CC doméstica SP floor 2024 (the threshold in the survey's brackets)
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams


# ---------- style ----------
rcParams['font.family'] = 'serif'
rcParams['font.size'] = 10
rcParams['axes.linewidth'] = 0.7
rcParams['axes.spines.top'] = False
rcParams['axes.spines.right'] = False
rcParams['axes.edgecolor'] = '#222222'
rcParams['xtick.color'] = '#222222'
rcParams['ytick.color'] = '#222222'
rcParams['pdf.fonttype'] = 42
rcParams['ps.fonttype'] = 42

# Colors — accent palette aligned with the project's dashboard
COL_AFRO   = '#b91c1c'    # accent red (afro-descendentes)
COL_BRANCA = '#475569'    # slate (brancas)
COL_TOTAL  = '#9ca3af'    # gray (overall reference)


ROOT = Path(__file__).parent.parent
SRC = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT_DIR = ROOT / "chapter" / "survey_a_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------- column lookup helpers ----------

def find_col(df: pd.DataFrame, prefix: str) -> str:
    for c in df.columns:
        if c.startswith(prefix):
            return c
    raise KeyError(f"No column starting with {prefix!r}")


def pct_pt(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:.1f}%".replace(".", ",")


# ---------- race grouping ----------

def add_race_group(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'race_group' column with afro / branca / outras / nan."""
    race_col = find_col(df, "3 -")
    def cls(v):
        if pd.isna(v):
            return None
        s = str(v).strip().lower()
        if s in ("pardo", "parda", "preto", "preta"):
            return "afro"
        if s in ("branco", "branca"):
            return "branca"
        return "outras"   # amarela/indígena — too small to compare
    df = df.copy()
    df["race_group"] = df[race_col].apply(cls)
    return df


# ---------- generic cross-tab + chart ----------

def crosstab(df: pd.DataFrame, col: str,
             order: list[str] | None = None,
             normalize_to_valid: bool = True) -> pd.DataFrame:
    """Returns a DataFrame with rows = categories and columns = race groups.

    Each cell is a tuple (n, pct) where pct is within the race group.
    NaN rows are excluded (assumed non-response). If `order` is given,
    rows follow that ordering."""
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
    df_out = pd.DataFrame(rows)
    # Footer row with denominators
    return df_out


def wrap_label(s: str, width: int = 32) -> str:
    """Wrap long category labels onto multiple lines."""
    s = str(s)
    return "\n".join(textwrap.wrap(s, width=width)) or s


def render_chart(df_xtab: pd.DataFrame, title: str, subtitle: str,
                 out_path: Path, order_label: str | None = None) -> None:
    """Race-disaggregated horizontal bar chart.

    Layout improvements over v1 (2026-06-22):
      - More vertical room per category (0.95 in y-units instead of 0.6)
      - Bar group tightened (bar_h 0.22 instead of 0.26) → 0.34 gap between
        adjacent categories instead of 0.22 — bars don't visually touch
      - Long category labels wrapped to multiple lines (width=32)
      - Value labels skipped for bars below 1.5% (reduces clutter on
        sparse cells)
      - Legend pinned above plot, outside bar area (avoids overlap with
        the last category's value label)
      - Title + subtitle have explicit spacing budget so they don't
        collide with each other or the legend"""
    cats = df_xtab["category"].tolist()
    afro = df_xtab["afro_pct"].tolist()
    branca = df_xtab["branca_pct"].tolist()
    total = df_xtab["total_race_known_pct"].tolist()
    n_cats = len(cats)

    # Wrap each category label and find max line count so we can size the figure
    wrapped = [wrap_label(c, width=32) for c in cats]
    extra_lines = sum(max(0, w.count("\n")) for w in wrapped)

    # Per-category vertical budget (in inches of figure height)
    per_cat = 0.95
    fig_h = max(3.4, per_cat * n_cats + 1.8 + 0.18 * extra_lines)
    fig, ax = plt.subplots(figsize=(8.8, fig_h))

    y = np.arange(n_cats)
    bar_h = 0.22                      # ↓ from 0.26 — clearer gap between groups

    ax.barh(y + bar_h,  afro,   bar_h, color=COL_AFRO,
            label=f'Afro-descendentes (n={int(sum(df_xtab["afro_n"]))})',
            edgecolor='white', linewidth=0.6)
    ax.barh(y,           branca, bar_h, color=COL_BRANCA,
            label=f'Brancas (n={int(sum(df_xtab["branca_n"]))})',
            edgecolor='white', linewidth=0.6)
    ax.barh(y - bar_h,   total,  bar_h, color=COL_TOTAL,
            label=f'Total (n={int(sum(df_xtab["total_race_known_n"]))})',
            edgecolor='white', linewidth=0.6)

    # value labels at the end of each bar — only when bar ≥ 1.5%, padded
    MIN_LABEL_PCT = 1.5
    def label(vals, offset):
        for i, v in enumerate(vals):
            if v is None or pd.isna(v) or v < MIN_LABEL_PCT:
                continue
            ax.text(v + 0.8, i + offset, pct_pt(v),
                    va='center', fontsize=8.5, color='#1a252f')
    label(afro,   bar_h)
    label(branca, 0)
    label(total,  -bar_h)

    ax.set_yticks(y)
    ax.set_yticklabels(wrapped, fontsize=9.5)
    ax.invert_yaxis()

    # X-axis: round up to nearest 10 above max, with sensible bounds
    max_val = max((v for v in afro + branca + total if v is not None), default=0)
    upper = int(min(100, max(40, np.ceil((max_val + 10) / 10) * 10)))
    ax.set_xlim(0, upper)
    xticks = list(range(0, upper + 1, 10))
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{t}%" for t in xticks], fontsize=9)
    ax.set_xlabel('% dentro do grupo racial', fontsize=10, labelpad=10)
    ax.grid(axis='x', linestyle=':', linewidth=0.4, color='#bbbbbb', alpha=0.6)
    ax.set_axisbelow(True)

    # Legend ABOVE the plot — out of the bar area entirely
    ax.legend(loc='lower left', bbox_to_anchor=(0, 1.04), ncol=3,
              fontsize=9, framealpha=0,
              handlelength=1.4, columnspacing=1.5, handletextpad=0.5)

    # Title and subtitle stacked above the legend
    # Subtitle at y=1.16, title at y=1.22 in axes coords
    ax.text(0, 1.22, title, transform=ax.transAxes,
            fontsize=11.5, fontweight='bold', color='#1a252f')
    if subtitle:
        ax.text(0, 1.16, subtitle, transform=ax.transAxes,
                fontsize=9, color='#6b7280', style='italic')

    # Make sure the wrapped y-axis labels don't get cut on the left
    plt.subplots_adjust(left=0.30, top=0.82, bottom=0.13, right=0.96)

    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(out_path.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    plt.close(fig)


def render_continuous(df: pd.DataFrame, col: str, title: str, subtitle: str,
                      out_path: Path, unit: str = "R$") -> dict:
    """Boxplot by race for a continuous (BRL) variable. Returns {race: median}."""
    sub = df[[col, "race_group"]].dropna(subset=[col]).copy()
    # Parse "200,00" → 200.00
    def parse(v):
        s = str(v).strip().replace(".", "").replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None
    sub["val"] = sub[col].apply(parse)
    sub = sub.dropna(subset=["val"])
    sub = sub[sub["val"] > 0]
    if len(sub) < 5:
        return {}
    afro_vals   = sub[sub["race_group"] == "afro"]["val"].tolist()
    branca_vals = sub[sub["race_group"] == "branca"]["val"].tolist()
    total_vals  = sub[sub["race_group"].isin(["afro", "branca"])]["val"].tolist()

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    data = [afro_vals, branca_vals, total_vals]
    labels = [f"Afro-descendentes\n(n={len(afro_vals)})",
              f"Brancas\n(n={len(branca_vals)})",
              f"Total\n(n={len(total_vals)})"]
    colors = [COL_AFRO, COL_BRANCA, COL_TOTAL]
    bp = ax.boxplot(data, vert=True, patch_artist=True, widths=0.55,
                    medianprops=dict(color='black', linewidth=1.6),
                    boxprops=dict(linewidth=0.7, edgecolor='#1a252f'),
                    whiskerprops=dict(linewidth=0.7, color='#1a252f'),
                    capprops=dict(linewidth=0.7, color='#1a252f'),
                    flierprops=dict(marker='o', markersize=3.5,
                                    markerfacecolor='none',
                                    markeredgecolor='#777777', alpha=0.5))
    for patch, c in zip(bp['boxes'], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.55)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel(f'Valor por diária ({unit})', fontsize=10, labelpad=10)
    ax.grid(axis='y', linestyle=':', linewidth=0.4, color='#bbbbbb', alpha=0.6)
    ax.set_axisbelow(True)

    # Expand y-axis range so median annotations have headroom above the max
    all_vals = afro_vals + branca_vals + total_vals
    if all_vals:
        ymin = min(all_vals)
        ymax = max(all_vals)
        ax.set_ylim(max(0, ymin - 20), ymax + 60)

    # Median annotations — positioned ABOVE the box (not on top of the median line)
    def med(vals):
        return float(np.median(vals)) if vals else None
    medians = {"afro": med(afro_vals), "branca": med(branca_vals), "total": med(total_vals)}
    for i, (lbl, vals) in enumerate(zip(labels, data)):
        if vals:
            m = np.median(vals)
            q3 = float(np.percentile(vals, 75))
            # Place annotation above the upper quartile so it doesn't touch the box top
            ax.annotate(f'mediana\nR$ {m:.0f}',
                        xy=(i + 1, q3), xytext=(0, 28),
                        textcoords='offset points',
                        ha='center', fontsize=9, fontweight='bold',
                        color='#1a252f',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                                  edgecolor='#cccccc', linewidth=0.5),
                        arrowprops=dict(arrowstyle='-', color='#888888',
                                        linewidth=0.6))

    # Title + subtitle ABOVE plot, like the bar charts
    ax.text(0, 1.14, title, transform=ax.transAxes,
            fontsize=11.5, fontweight='bold', color='#1a252f')
    if subtitle:
        ax.text(0, 1.06, subtitle, transform=ax.transAxes,
                fontsize=9, color='#6b7280', style='italic')

    plt.subplots_adjust(top=0.83, bottom=0.16, left=0.12, right=0.96)
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(out_path.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return medians


# ---------- markdown helpers ----------

def md_table(df_xtab: pd.DataFrame, label_col: str = "category") -> str:
    """Render an xtab DataFrame as a markdown table with afro/branca/total and
    a 'Gap (afro − branca, pp)' column highlighting absolute gaps ≥ 10pp."""
    lines = ["| Categoria | Afro | Brancas | Total | Δ (pp) |",
             "|---|---:|---:|---:|---:|"]
    for _, r in df_xtab.iterrows():
        afro = r["afro_pct"]
        branca = r["branca_pct"]
        total = r["total_race_known_pct"]
        delta = (afro - branca) if (afro is not None and branca is not None) else None
        delta_str = f"{delta:+.1f}".replace(".", ",") if delta is not None else "—"
        if delta is not None and abs(delta) >= 10:
            delta_str = f"**{delta_str}**"
        cat_str = str(r[label_col])
        if len(cat_str) > 50:
            cat_str = cat_str[:47] + "…"
        lines.append(
            f"| {cat_str} | {pct_pt(afro)} ({r['afro_n']}) "
            f"| {pct_pt(branca)} ({r['branca_n']}) "
            f"| {pct_pt(total)} ({r['total_race_known_n']}) "
            f"| {delta_str} |"
        )
    return "\n".join(lines)


def find_discrepancies(df_xtab: pd.DataFrame, threshold: float = 10.0) -> list[dict]:
    """Return rows where |afro - branca| ≥ threshold pp."""
    hits = []
    for _, r in df_xtab.iterrows():
        afro = r["afro_pct"]
        branca = r["branca_pct"]
        if afro is None or branca is None or pd.isna(afro) or pd.isna(branca):
            continue
        delta = afro - branca
        if abs(delta) >= threshold:
            hits.append({"category": r["category"], "afro": afro,
                         "branca": branca, "delta": delta})
    return hits


# ---------- main ----------

def main():
    df = pd.read_excel(SRC)
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    df = add_race_group(df)
    race_dist = df["race_group"].value_counts(dropna=False)
    print(f"Race distribution: {race_dist.to_dict()}")

    sections = []   # list of (id, title, subtitle, md_body, png_basename)

    # ============================================================
    # Q1 — Age
    # ============================================================
    col = find_col(df, "1 -")
    age_order = ["Entre 18 e 29 anos", "Entre 30 e 39 anos",
                 "Entre 40 e 49 anos", "Entre 50 e 59 anos",
                 "Acima de 60 anos"]
    xt = crosstab(df, col, order=age_order)
    out_png = OUT_DIR / "Q01_age.png"
    render_chart(xt,
                 title='Q1 — Idade das trabalhadoras domésticas',
                 subtitle='STDMSP Pesquisa A (2024) · % dentro de cada grupo racial',
                 out_path=out_png)
    discrepancies = find_discrepancies(xt)
    commentary = (
        "A categoria é envelhecida em ambos os grupos raciais — ~70% têm 40 anos ou mais. "
        "**Mas a distribuição etária é racialmente assimétrica:** "
        "**brancas concentram-se em 30-39 anos** (30,1% vs 13,4% afro, gap -16,7pp), enquanto "
        "**afro concentram-se em 50-59 anos** (37,3% vs 22,6% brancas, gap +14,7pp). "
        "Quase 56% das afro têm 50+ anos vs ~39% das brancas. Interpretação possível: "
        "trajetórias raciais diferentes na categoria — afro permanecem (ou se reinserem) "
        "mais tempo no trabalho doméstico; brancas entram e saem em fases mais jovens."
    )
    sections.append(("Q01", "Idade", "Distribuição por faixa etária", commentary, out_png, xt))

    # ============================================================
    # Q2 — Race (just the breakdown of the sample)
    # ============================================================
    col = find_col(df, "3 -")
    race_order = ["Pardo", "Branco", "Preto", "Amarelo", "Indígena"]
    # Different xtab — show race composition itself (not cross by race)
    # So we override: pct here is share of total race-known sample
    n_total_race_known = (df["race_group"].isin(["afro", "branca"])).sum()
    rows = []
    counts = df[col].value_counts(dropna=False)
    for r in race_order:
        n = int(counts.get(r, 0))
        rows.append({"category": r, "n": n,
                     "pct": 100*n/n_total_race_known if n_total_race_known else None})
    nan_n = int(counts.get(np.nan, 0))

    # Render simple horizontal bar chart for race breakdown
    fig, ax = plt.subplots(figsize=(8.0, 3.6))
    cats = [r["category"] for r in rows]
    n_vals = [r["n"] for r in rows]
    bars = ax.barh(cats, n_vals,
                   color=[COL_AFRO if c in ("Pardo", "Preto") else
                          COL_BRANCA if c == "Branco" else
                          '#d4d4d4' for c in cats],
                   edgecolor='white', linewidth=0.8, height=0.65)
    for i, r in enumerate(rows):
        pct = r["pct"]
        ax.text(r["n"] + 2, i,
                f"{r['n']}  ({pct_pt(pct)})",
                va='center', fontsize=9.5, fontweight='bold', color='#1a252f')
    ax.invert_yaxis()
    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels(cats, fontsize=10)
    ax.set_xlabel('Frequência absoluta · n=235 com resposta de raça',
                  fontsize=10, labelpad=10)
    ax.grid(axis='x', linestyle=':', linewidth=0.4, color='#bbbbbb', alpha=0.6)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(n_vals) + 30)
    ax.set_title('Q3 — Composição racial da amostra',
                 fontsize=11.5, pad=14, loc='left', color='#1a252f', fontweight='bold')
    out_png = OUT_DIR / "Q02_race.png"
    plt.tight_layout()
    plt.savefig(out_png, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    plt.close(fig)
    afro_n = sum(1 for v in df[col].dropna() if str(v).strip().lower() in ("pardo", "preto"))
    branca_n = sum(1 for v in df[col].dropna() if str(v).strip().lower() == "branco")
    outras_n = sum(1 for v in df[col].dropna() if str(v).strip().lower() in ("amarelo", "indígena"))
    commentary = (
        f"Da amostra com resposta de raça (n={n_total_race_known + outras_n}), "
        f"**{afro_n} são afro-descendentes** (pardas + pretas) e "
        f"**{branca_n} são brancas**. A composição da amostra A (60% afro) "
        f"é semelhante à composição racial da categoria doméstica em São Paulo "
        f"observada na PNADC (~56-60% pretas + pardas em 2024-2026)."
    )
    # No proper xtab here — use a dummy for the report builder
    dummy_xt = pd.DataFrame([{"category": r["category"], "afro_n": r["n"] if r["category"] in ("Pardo","Preto") else 0,
                              "afro_pct": None,
                              "branca_n": r["n"] if r["category"] == "Branco" else 0,
                              "branca_pct": None,
                              "total_race_known_n": r["n"],
                              "total_race_known_pct": r["pct"]} for r in rows])
    sections.append(("Q02", "Composição racial",
                     "Pardas + Pretas = afro-descendentes (n={n})".format(n=afro_n),
                     commentary, out_png, dummy_xt))

    # ============================================================
    # Q3 — Part-time / Full-time
    # ============================================================
    col = find_col(df, "6 -")
    pt_order = ["Diarista", "Com vínculo"]
    xt = crosstab(df, col, order=pt_order)
    out_png = OUT_DIR / "Q03_part_full_time.png"
    render_chart(xt,
                 title='Q6 — Diarista vs. com vínculo (proxy de jornada)',
                 subtitle='Diarista = até 2 dias/semana · Com vínculo = 3+ dias',
                 out_path=out_png)
    commentary = (
        "Aproximadamente metade da amostra trabalha como diarista, metade com vínculo. "
        "**Diarismo = jornada parcial** legal (LC 150/2015 art. 1º §1º) e implica "
        "exclusão da maioria dos direitos previdenciários automáticos."
    )
    for d in find_discrepancies(xt):
        commentary += (
            f" Discrepância na categoria **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q03", "Diarista vs vínculo", "% da amostra em cada modalidade",
                     commentary, out_png, xt))

    # ============================================================
    # Q4 — Salary base (Q9)
    # ============================================================
    col = find_col(df, "9 -")
    sal_order = ["Abaixo de R$ 1476,75",
                 "Entre R$ 1476,75 e R$ 2000,00",
                 "Entre R$ 2000,00 e R$ 3500,00",
                 "Acima de 3500,00"]
    xt = crosstab(df, col, order=sal_order)
    out_png = OUT_DIR / "Q04_base_salary.png"
    render_chart(xt,
                 title='Q9 — Salário base (faixas) por raça',
                 subtitle='Faixa 1 R$ 1.476,75 = piso da CC doméstica SP (2024) · "abaixo" significa descumprimento',
                 out_path=out_png)
    # Compute % below minimum
    below_min_afro = xt.loc[xt["category"] == "Abaixo de R$ 1476,75", "afro_pct"].iloc[0]
    below_min_branca = xt.loc[xt["category"] == "Abaixo de R$ 1476,75", "branca_pct"].iloc[0]
    above_3500_afro = xt.loc[xt["category"] == "Acima de 3500,00", "afro_pct"].iloc[0]
    above_3500_branca = xt.loc[xt["category"] == "Acima de 3500,00", "branca_pct"].iloc[0]
    commentary = (
        f"**Referências 2024:** salário mínimo federal R$ 1.412,00 · piso da Convenção "
        f"Coletiva doméstica SP R$ 1.476,75 (Faixa 1).  \n"
        f"**Achado inesperado — o gap racial vai na direção contrária do padrão PNADC:** "
        f"{pct_pt(below_min_afro)} das afro vs **{pct_pt(below_min_branca)} das brancas** "
        f"recebem abaixo do piso CC. Ou seja, **brancas estão mais abaixo do piso** que afro "
        f"nesta amostra (Δ {below_min_afro - below_min_branca:+.1f}pp). "
        f"Faixa central R$ 1.476-2.000: ~46% em ambos os grupos. No topo (>R$ 3.500): "
        f"{pct_pt(above_3500_afro)} afro vs {pct_pt(above_3500_branca)} brancas — paridade. \n\n"
        f"**Interpretação cautelosa:** o resultado provavelmente reflete o viés da amostra de "
        f"conveniência STDMSP. As brancas que respondem à pesquisa do sindicato podem ser "
        f"sistematicamente diferentes das brancas no PNADC — talvez mais periféricas, mais "
        f"velhas (idade não bate, ver Q1 — brancas são mais jovens, na verdade), ou em "
        f"arranjos mais informais. **Esse achado precisa de validação contra PNADC com filtro "
        f"de UF=SP + raça antes de qualquer interpretação política.**"
    )
    sections.append(("Q04", "Salário base", "R$ por mês · faixas",
                     commentary, out_png, xt))

    # ============================================================
    # Q5 — Diária value (Q16A, continuous)
    # ============================================================
    col = find_col(df, "16A")
    out_png = OUT_DIR / "Q05_diaria_value.png"
    medians = render_continuous(df, col,
                                title='Q16A — Valor cobrado por diária (R$)',
                                subtitle='Apenas respondentes que trabalham como diarista · n=73',
                                out_path=out_png)
    if medians and medians.get("afro") and medians.get("branca"):
        m_afro = medians["afro"]
        m_branca = medians["branca"]
        delta_pct = 100 * (m_branca - m_afro) / m_afro if m_afro else None
        commentary = (
            f"Mediana da diária: afro **R$ {m_afro:.0f}** vs brancas **R$ {m_branca:.0f}** "
            f"({'+' if delta_pct >= 0 else ''}{delta_pct:.0f}% diferença). "
        )
        if abs(delta_pct or 0) < 5:
            commentary += (
                f" **Sem hiato racial na mediana** dentro da amostra STDMSP — diferente "
                f"do padrão PNADC 1T 2026 que mostra hiato salarial por hora de 84,3% no "
                f"diarismo BR-wide. Possíveis explicações: (a) viés da amostra de "
                f"conveniência; (b) homogeneização do mercado paulista entre quem chega "
                f"ao raio de atuação do sindicato; (c) tamanho amostral pequeno "
                f"(n={int(sum(1 for v in df[col].dropna()))}) — dispersão alta, mediana "
                f"insensível a outliers."
            )
        else:
            commentary += (
                f" A diferença replica em escala micro o padrão BR-wide de discriminação "
                f"racial no preço da hora diarista. Amostra pequena, magnitude precisa cautela."
            )
    else:
        commentary = "Amostra muito pequena para comparação racial confiável."
    # Build a fake xt for the report builder
    dummy_xt = pd.DataFrame()
    sections.append(("Q05", "Valor da diária", "Apenas diaristas (n=73)",
                     commentary, out_png, dummy_xt))

    # ============================================================
    # Q6 — Paid for extra hours (Q8)
    # ============================================================
    col = find_col(df, "8 -")
    yn_order = ["Sim", "Não"]
    xt = crosstab(df, col, order=yn_order)
    out_png = OUT_DIR / "Q06_paid_overtime.png"
    render_chart(xt,
                 title='Q8 — Recebe horas extras (>44h semanais)?',
                 subtitle='LC 150/2015 art. 2º obriga remuneração de horas extras com adicional ≥50%',
                 out_path=out_png)
    nao_afro   = xt.loc[xt["category"] == "Não", "afro_pct"].iloc[0]
    nao_branca = xt.loc[xt["category"] == "Não", "branca_pct"].iloc[0]
    commentary = (
        f"**{pct_pt(nao_afro)} das afro-descendentes e {pct_pt(nao_branca)} das brancas "
        f"**não recebem horas extras** — descumprimento generalizado da LC 150 em ambos "
        f"os recortes raciais. "
    )
    for d in find_discrepancies(xt):
        commentary += (
            f"Diferença ≥10pp em **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q06", "Horas extras", "Recebem ou não pagamento por hora extra",
                     commentary, out_png, xt))

    # ============================================================
    # Q7 — Paid for official holidays (proxy: Dia da Trabalhadora 27/abr) (Q15)
    # ============================================================
    col = find_col(df, "15 -")
    hol_order = ["Trabalhou, mas recebeu o dia em dobro",
                 "Trabalhou, mas não recebeu o dia dia em dobro",
                 "Foi liberada de trabalhar nesse dia"]
    xt = crosstab(df, col, order=hol_order)
    out_png = OUT_DIR / "Q07_holiday_pay.png"
    render_chart(xt,
                 title='Q15 — Dia da Trabalhadora Doméstica (27/abr) — como foi tratado',
                 subtitle='Proxy para feriados oficiais · LC 150 reconhece como direito',
                 out_path=out_png)
    dobro_afro   = xt.loc[xt["category"].str.contains("recebeu o dia em dobro"), "afro_pct"].iloc[0] if any(xt["category"].str.contains("recebeu o dia em dobro")) else 0
    nao_dobro_afro = xt.loc[xt["category"].str.contains("não recebeu"), "afro_pct"].iloc[0] if any(xt["category"].str.contains("não recebeu")) else 0
    liberada_afro = xt.loc[xt["category"].str.contains("Foi liberada"), "afro_pct"].iloc[0] if any(xt["category"].str.contains("Foi liberada")) else 0
    commentary = (
        f"Maioria absoluta trabalhou no 27/abr **sem receber dia em dobro** "
        f"(afro {pct_pt(nao_dobro_afro)}, brancas {pct_pt(xt.loc[xt['category'].str.contains('não recebeu'), 'branca_pct'].iloc[0])}). "
        f"Apenas uma pequena minoria recebeu o dia em dobro como manda a lei "
        f"(afro {pct_pt(dobro_afro)}, brancas {pct_pt(xt.loc[xt['category'].str.contains('recebeu o dia em dobro'), 'branca_pct'].iloc[0])}). "
    )
    for d in find_discrepancies(xt):
        commentary += (
            f"Diferença ≥10pp em **{d['category'][:60]}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q07", "Feriado 27/abr",
                     "Proxy: como foi tratado no Dia da Trabalhadora Doméstica",
                     commentary, out_png, xt))

    # ============================================================
    # Q8 — Knows what a CC is (Q11)
    # ============================================================
    col = find_col(df, "11-")
    yn_order = ["Sim", "Não"]
    xt = crosstab(df, col, order=yn_order)
    out_png = OUT_DIR / "Q08_knows_cc.png"
    render_chart(xt,
                 title='Q11 — Você sabe o que é a Convenção Coletiva do Trabalho?',
                 subtitle='Conhecimento institucional sobre o instrumento legal',
                 out_path=out_png)
    sim_afro   = xt.loc[xt["category"] == "Sim", "afro_pct"].iloc[0]
    sim_branca = xt.loc[xt["category"] == "Sim", "branca_pct"].iloc[0]
    commentary = (
        f"**Apenas {pct_pt(sim_afro)} das afro-descendentes e {pct_pt(sim_branca)} das brancas "
        f"sabem o que é uma Convenção Coletiva.** Conhecimento institucional baixo em "
        f"ambos os recortes — o sindicato tem trabalho de divulgação pela frente. "
    )
    for d in find_discrepancies(xt):
        commentary += (
            f"Diferença ≥10pp em **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q08", "Conhece CC?", "Conhecimento conceitual",
                     commentary, out_png, xt))

    # ============================================================
    # Q9 — Knows CC exists in SP (Q10)
    # ============================================================
    col = find_col(df, "10 -")
    xt = crosstab(df, col, order=["Sim", "Não"])
    out_png = OUT_DIR / "Q09_knows_cc_sp.png"
    render_chart(xt,
                 title='Q10 — Sabe que existe Convenção Coletiva da categoria em São Paulo?',
                 subtitle='Conhecimento específico sobre a CC SP doméstica',
                 out_path=out_png)
    sim_afro   = xt.loc[xt["category"] == "Sim", "afro_pct"].iloc[0]
    sim_branca = xt.loc[xt["category"] == "Sim", "branca_pct"].iloc[0]
    commentary = (
        f"**{pct_pt(sim_afro)} das afro-descendentes e {pct_pt(sim_branca)} das brancas** "
        f"sabem da existência da CC paulista da categoria. A maioria absoluta — em ambos "
        f"os grupos — não sabe. Esse desconhecimento direto da existência do instrumento "
        f"que regula seus salários é o principal gargalo organizativo da STDMSP. "
    )
    for d in find_discrepancies(xt):
        commentary += (
            f"Diferença ≥10pp em **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q09", "Sabe da CC em SP?", "Conhecimento específico",
                     commentary, out_png, xt))

    # ============================================================
    # Q10 — CC brings benefit (Q13)
    # ============================================================
    col = find_col(df, "13 -")
    xt = crosstab(df, col, order=["Sim", "Não"])
    out_png = OUT_DIR / "Q10_cc_benefit.png"
    render_chart(xt,
                 title='Q13 — A Convenção Coletiva já trouxe benefício para você?',
                 subtitle='Auto-avaliação subjetiva do impacto material da CC',
                 out_path=out_png)
    sim_afro   = xt.loc[xt["category"] == "Sim", "afro_pct"].iloc[0]
    sim_branca = xt.loc[xt["category"] == "Sim", "branca_pct"].iloc[0]
    commentary = (
        f"Entre quem respondeu, **{pct_pt(sim_afro)} das afro vs {pct_pt(sim_branca)} das brancas** "
        f"afirmaram ter recebido algum benefício direto da CC. O fato de a CC ter trazido "
        f"benefício mesmo para quem não a conhece nominalmente (Q10/Q11) sugere que parte "
        f"da categoria já se beneficia da CC sem identificar a origem. "
    )
    for d in find_discrepancies(xt):
        commentary += (
            f"Diferença ≥10pp em **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q10", "CC trouxe benefício?", "Auto-avaliação",
                     commentary, out_png, xt))

    # ============================================================
    # Q11 — Union can help (Q17)
    # ============================================================
    col = find_col(df, "17 -")
    xt = crosstab(df, col, order=["Sim", "Não"])
    out_png = OUT_DIR / "Q11_union_helps.png"
    render_chart(xt,
                 title='Q17 — Sindicato pode ajudar em situações difíceis no trabalho?',
                 subtitle='Percepção de utilidade política da estrutura sindical',
                 out_path=out_png)
    sim_afro   = xt.loc[xt["category"] == "Sim", "afro_pct"].iloc[0]
    sim_branca = xt.loc[xt["category"] == "Sim", "branca_pct"].iloc[0]
    commentary = (
        f"**{pct_pt(sim_afro)} das afro e {pct_pt(sim_branca)} das brancas** acreditam que "
        f"o sindicato pode ajudar em situações difíceis. Apesar do baixo conhecimento sobre "
        f"CC (Q10/Q11), a confiança na ação sindical é alta — um achado político relevante "
        f"para a STDMSP que pode fundamentar campanhas. "
    )
    for d in find_discrepancies(xt):
        commentary += (
            f"Diferença ≥10pp em **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q11", "Sindicato ajuda?", "Confiança na estrutura sindical",
                     commentary, out_png, xt))

    # ============================================================
    # Q12 — Most important union function (Q18)
    # — uses the existing 5-category bucketing from etl/categorize_q18.py
    # ============================================================
    # Categories from etl/categorize_q18.py (the 9-bucket view: 1-4 substantive + 5a-5e residual)
    # We reduce to the 5-category top-level for clarity here.
    Q18_BUCKETS = {
        "1": "1. Defesa dos direitos trabalhistas",
        "2": "2. Orientação sobre direitos",
        "3": "3. Apoio jurídico e cobrança dos patrões",
        "4": "4. Cuidado, proteção e acolhimento",
        "5": "5. Todas / não sabe / vago",
    }
    def categorize_q18(s: str) -> str | None:
        if s is None or pd.isna(s):
            return None
        text = str(s).strip().lower()
        if not text:
            return None
        if any(kw in text for kw in ["defender", "defesa", "defend", "direitos trabalh", "lutar pelo bem",
                                       "lutar pelos direitos", "garantir o que o trabalho",
                                       "garantia dos direitos", "garantir o direito",
                                       "lutar pelos direitos", "buscar direitos", "buscar os direitos"]):
            return "1"
        if any(kw in text for kw in ["orientar", "orientação", "informar", "informação", "esclarecer",
                                       "esclarescer", "divulgar", "divulgação", "informe", "conscientiza",
                                       "instruir", "ensinar", "valoriza"]):
            return "2"
        if any(kw in text for kw in ["jurídic", "jurídico", "advogad", "processo", "lei", "leis",
                                       "judicial", "fiscaliza", "cobrar", "cobrança", "patrão",
                                       "patrões", "empregador"]):
            return "3"
        if any(kw in text for kw in ["cuidado", "proteção", "proteger", "acolher", "acolhimento",
                                       "amparar", "apoio", "apoiar", "suporte", "ajudar todos",
                                       "ajudar nas necessidades", "ajudar quem precis"]):
            return "4"
        return "5"
    col = find_col(df, "18 -")
    df["q18_bucket"] = df[col].apply(categorize_q18)
    bucket_order = list(Q18_BUCKETS.keys())
    xt = crosstab(df, "q18_bucket", order=bucket_order)
    # Replace bucket codes with readable labels
    xt["category"] = xt["category"].map(Q18_BUCKETS)
    out_png = OUT_DIR / "Q12_union_function.png"
    render_chart(xt,
                 title='Q18 — Função mais importante do sindicato (5 categorias)',
                 subtitle='Categorização heurística do texto livre · ~25% caem em "5 — residual"',
                 out_path=out_png)
    cat1_afro = xt.loc[xt["category"] == Q18_BUCKETS["1"], "afro_pct"].iloc[0]
    cat1_branca = xt.loc[xt["category"] == Q18_BUCKETS["1"], "branca_pct"].iloc[0]
    cat5_afro = xt.loc[xt["category"] == Q18_BUCKETS["5"], "afro_pct"].iloc[0]
    cat5_branca = xt.loc[xt["category"] == Q18_BUCKETS["5"], "branca_pct"].iloc[0]
    commentary = (
        f"**Defesa de direitos** lidera em ambos os grupos "
        f"(afro {pct_pt(cat1_afro)}, brancas {pct_pt(cat1_branca)}). "
        f"Respostas residuais ('todas', 'não sei', vago) somam "
        f"~{pct_pt(cat5_afro)} afro e ~{pct_pt(cat5_branca)} brancas — "
        f"refletem dificuldade de articular conceitualmente a função institucional. "
    )
    for d in find_discrepancies(xt):
        commentary += (
            f"Diferença ≥10pp em **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q12", "Função do sindicato", "Texto livre categorizado em 5 buckets",
                     commentary, out_png, xt))

    # ============================================================
    # WRITE REPORT
    # ============================================================
    report_path = OUT_DIR / "report.md"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("# Pesquisa A STDMSP — análise por raça\n\n")
        f.write("**Fonte:** *Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx* — "
                "STDMSP, campo 2024 (n=242, auto-administrada via Google Forms).\n\n")
        f.write("**Recortes:**\n\n")
        f.write("- **Afro-descendentes** (pardas + pretas): n=140\n")
        f.write("- **Brancas**: n=93\n")
        f.write("- **Total race-known**: n=233 (exclui 2 Amarela/Indígena + 7 sem resposta de raça)\n\n")
        f.write("**Critério de discrepância:** diferença afro – brancas ≥ 10 pontos percentuais "
                "(em negrito na coluna Δ das tabelas).\n\n")
        f.write("**Referências 2024 para o item 4 (salário):** R$ 1.412,00 = salário mínimo federal · "
                "R$ 1.476,75 = piso CC doméstica SP.\n\n")
        f.write("---\n\n")

        for sec_id, label, sub, body, png, xt in sections:
            f.write(f"## {sec_id} — {label}\n\n")
            f.write(f"*{sub}*\n\n")
            f.write(f"![{label}]({png.name})\n\n")
            if isinstance(xt, pd.DataFrame) and not xt.empty and "afro_n" in xt.columns:
                f.write(md_table(xt) + "\n\n")
            f.write(body + "\n\n")
            f.write("---\n\n")

        f.write("## Resumo dos achados\n\n")
        f.write("Os dados desta pesquisa **divergem em vários pontos do padrão "
                "PNADC BR-wide** — provavelmente por se tratar de amostra de conveniência "
                "no entorno do STDMSP, com auto-seleção sistemática.\n\n")
        f.write("**Demografia (Q1-Q3):**\n\n")
        f.write("1. **Idade — diferença racial inesperada**: afro concentram-se em 50-59 anos "
                "(37%), brancas em 30-39 (30%). Afro são **15-17pp mais velhas** que brancas "
                "neste recorte. Possível leitura: trajetórias raciais diferentes — afro "
                "permanecem mais tempo na categoria, brancas circulam para fora em fases mais "
                "jovens.\n")
        f.write("2. **Composição racial**: 60% afro (pardas + pretas), alinhado com a PNADC "
                "para SP.\n")
        f.write("3. **Diarista vs vínculo (Q6)**: divisão aproximadamente meio a meio em "
                "ambos os grupos. Sem hiato racial significativo na modalidade contratual.\n\n")
        f.write("**Remuneração (Q4-Q5):**\n\n")
        f.write("4. **Salário base (Q9) — gap racial inverso**: 18,5% afro vs **27,7% brancas** "
                "recebem abaixo do piso CC (R$ 1.476,75). Ou seja, **brancas estão mais abaixo "
                "do piso que afro** nesta amostra (-9,2pp). Contra-intuitivo dado o padrão BR. "
                "Pode refletir o efeito-idade (Q1) — brancas mais jovens, talvez em arranjos "
                "menos estruturados. **Validação contra PNADC SP × raça × idade é necessária "
                "antes de qualquer leitura política.**\n")
        f.write("5. **Diária (Q16A) — sem hiato racial na mediana** (R$ 180 em ambos os "
                "grupos). Diferente do hiato BR-wide de 84,3%/hora no diarismo. Sugere "
                "homogeneização do mercado paulista no raio STDMSP, ou pequeno n=73.\n\n")
        f.write("**Direitos e descumprimento (Q6-Q7):**\n\n")
        f.write("6. **Horas extras (Q8) — descumprimento estrutural**: 88% não recebem horas "
                "extras (85% afro, 92% brancas). LC 150 ignorada em larga escala.\n")
        f.write("7. **Dia da Trabalhadora (Q15)**: ~77% trabalharam sem dia em dobro — "
                "descumprimento generalizado da regra de feriado, ambos os grupos.\n\n")
        f.write("**Conhecimento e organização (Q8-Q12):**\n\n")
        f.write("8. **Conhecimento de CC (Q10/Q11) — gargalo organizativo**: apenas ~24% "
                "sabem o que é uma Convenção Coletiva, e apenas ~33% sabem que existe uma "
                "CC paulista da categoria. **Maior lacuna informacional da pesquisa.**\n")
        f.write("9. **CC trouxe benefício (Q13)**: 36% reportam benefício direto. Afro **+9pp** "
                "vs brancas (40% vs 31%). Curioso — afro reportam benefício mais frequentemente "
                "apesar de baixo conhecimento formal.\n")
        f.write("10. **Confiança no sindicato (Q17) — alta em ambos**: ~83% acreditam que o "
                "sindicato pode ajudar. **Confiança política alta apesar do baixo conhecimento "
                "técnico** — combinação típica de organização de base.\n")
        f.write("11. **Função do sindicato (Q18)**: 'Defesa de direitos' lidera (21%). Mas "
                "**brancas dão mais respostas vagas/residuais** (64% vs 52% afro, gap -12,3pp). "
                "Afro articulam funções mais concretas — sinal de maior engajamento com a "
                "missão da categoria.\n\n")
        f.write("**Implicação política:** três descumprimentos generalizados (piso, horas "
                "extras, feriado) cruzados com baixo conhecimento institucional sugerem que o "
                "primeiro passo da campanha STDMSP é informacional — fazer a categoria "
                "*saber* que tem direitos antes de cobrá-los.\n")

    print(f"\nReport: {report_path}")
    print(f"Charts saved to: {OUT_DIR}")

    # ============================================================
    # ALSO WRITE LONG-FORM CSV
    # ============================================================
    csv_path = OUT_DIR / "data.csv"
    csv_rows = []
    for sec_id, label, sub, body, png, xt in sections:
        if not isinstance(xt, pd.DataFrame) or xt.empty:
            continue
        for _, r in xt.iterrows():
            csv_rows.append({
                "question": sec_id,
                "question_label": label,
                "category": r["category"],
                "afro_n": r.get("afro_n", None),
                "afro_pct": r.get("afro_pct", None),
                "branca_n": r.get("branca_n", None),
                "branca_pct": r.get("branca_pct", None),
                "total_n": r.get("total_race_known_n", None),
                "total_pct": r.get("total_race_known_pct", None),
            })
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
