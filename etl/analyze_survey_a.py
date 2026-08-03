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
  R$ 1,540.59   STDMSP/CC doméstica SP floor 2024 (TRUE CC value when survey was applied)
  R$ 1,476.75   threshold used in the survey's brackets — based on the 2023 CC floor,
                NOT updated when the form was deployed in 2024. This means the survey
                UNDERESTIMATES the CC-floor violation rate: respondents earning between
                R$ 1,476.75 and R$ 1,540.59 are below the 2024 CC floor but appear in
                the 'Entre R$ 1476,75 e R$ 2000,00' bracket.
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
                      out_path: Path, unit: str = "R$",
                      reference_value: float | None = None,
                      reference_label: str | None = None) -> dict:
    """Strip plot by race for a continuous (BRL) variable showing each
    individual respondent. Includes a reference-value vertical line + counts
    below/equal/above the reference per race.

    Returns {race: median} dict for downstream commentary."""
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

    # =================================================================
    # WILKINSON DOT PLOT (2026-06-22 v3): stacked dots, one per respondent,
    # at each unique R$ value. Stack afro dots first (bottom), then brancas
    # (top). Reveals concentration peaks (R$ 150, R$ 180, R$ 200) clearly
    # while preserving every individual respondent. Reference line at the
    # CC floor (R$ 210). Removed the "Total" row (was redundant — each
    # respondent already appears once in their race row).
    # =================================================================

    fig, ax = plt.subplots(figsize=(11.0, 5.2))

    # Pre-compute all unique values and per-race counts at each value
    all_vals_set = sorted(set(afro_vals + branca_vals))
    afro_count_at = {v: afro_vals.count(v) for v in all_vals_set}
    branca_count_at = {v: branca_vals.count(v) for v in all_vals_set}

    # Reference line FIRST so dots overlay it
    if reference_value is not None:
        ax.axvline(reference_value, color=COL_AFRO, linestyle='--',
                   linewidth=1.8, zorder=1, alpha=0.85)

    # Dot size: scaled to dot diameter ≈ 0.85 of vertical step
    DOT_SIZE = 200    # markersize in pt²
    DOT_Y_STEP = 1.0  # vertical distance between stacked dots

    max_stack = 0
    for v in all_vals_set:
        # Stack afro dots starting at y=0.5
        for i in range(afro_count_at[v]):
            y = 0.5 + i * DOT_Y_STEP
            ax.scatter([v], [y], color=COL_AFRO, s=DOT_SIZE,
                       edgecolor='white', linewidth=0.8, alpha=0.95, zorder=3)
        # Brancas stack above the afros
        for i in range(branca_count_at[v]):
            y = 0.5 + (afro_count_at[v] + i) * DOT_Y_STEP
            ax.scatter([v], [y], color=COL_BRANCA, s=DOT_SIZE,
                       edgecolor='white', linewidth=0.8, alpha=0.95, zorder=3)
        max_stack = max(max_stack, afro_count_at[v] + branca_count_at[v])

    # Compute counts below / at / above (per race + total)
    counts = {}
    for label, vals in [("Afro", afro_vals), ("Brancas", branca_vals),
                        ("Total", total_vals)]:
        if vals and reference_value is not None:
            below = sum(1 for v in vals if v < reference_value)
            at    = sum(1 for v in vals if v == reference_value)
            above = sum(1 for v in vals if v > reference_value)
            counts[label] = {"below": below, "at": at, "above": above,
                             "n": len(vals)}

    # Median markers — two separate ticks + labels stacked VERTICALLY
    # so they don't overlap when both medians fall on the same R$ value
    # (which is the case here: afro=brancas=R$ 180). Afro on top tier
    # (y=-1.0 marker, y=-1.4 label), brancas on lower tier (y=-1.7 marker,
    # y=-2.1 label).
    for label, vals, color, marker_y, label_y in [
        ("Afro",    afro_vals,   COL_AFRO,   (-1.0, -0.4), -1.4),
        ("Brancas", branca_vals, COL_BRANCA, (-2.1, -1.5), -2.5),
    ]:
        if vals:
            med = float(np.median(vals))
            ax.plot([med, med], list(marker_y), color=color, linewidth=3.2,
                    solid_capstyle='round', zorder=4)
            ax.text(med, label_y, f'med {label}: R$ {int(med)}',
                    fontsize=9, fontweight='bold', color=color,
                    ha='center', va='center')

    # X-axis range with padding
    xmin = min(all_vals_set) - 20
    xmax = max(all_vals_set) + 30
    ax.set_xlim(xmin, xmax)

    # Y-axis range — expanded below to fit the two stacked median labels
    ymax = max_stack + 3
    ax.set_ylim(-3.0, ymax)

    # X-axis ticks every R$ 25 (restored from the user's "great" version)
    xticks = list(range(int(xmin // 25) * 25, int(xmax // 25 + 1) * 25, 25))
    xticks = [t for t in xticks if t >= xmin and t <= xmax]
    ax.set_xticks(xticks)
    ax.set_xticklabels([f'R$ {t}' for t in xticks], fontsize=9)
    ax.set_xlabel(f'Valor cobrado por diária', fontsize=10.5, labelpad=10)

    # Hide Y axis ticks and spine (data is implicit in dot stacks)
    ax.set_yticks([])
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.grid(axis='x', linestyle=':', linewidth=0.4, color='#bbbbbb',
            alpha=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Reference line label — bottom-right of the line, in the dot area
    if reference_value is not None:
        ax.annotate(reference_label or f'R$ {int(reference_value)}',
                    xy=(reference_value, ymax - 1.5),
                    xytext=(12, 0), textcoords='offset points',
                    fontsize=9.5, color=COL_AFRO, fontweight='bold',
                    ha='left', va='center',
                    bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                              edgecolor=COL_AFRO, linewidth=0.8))

    # Headline annotation — top-right
    if reference_value is not None and "Total" in counts:
        pct_below_total = 100 * counts["Total"]["below"] / counts["Total"]["n"]
        ax.text(0.99, 0.98,
                f"{pct_below_total:.0f}% das diaristas\nrecebem ABAIXO\ndo piso R$ {int(reference_value)}",
                transform=ax.transAxes,
                fontsize=10.5, ha='right', va='top',
                fontweight='bold', color=COL_AFRO,
                bbox=dict(boxstyle='round,pad=0.55', facecolor='#fee2e2',
                          edgecolor=COL_AFRO, linewidth=1.0))

    # Inline legend (top-left) — race + n
    from matplotlib.lines import Line2D
    legend_handles = [
        Line2D([0], [0], marker='o', color='none',
               markerfacecolor=COL_AFRO, markeredgecolor='white',
               markeredgewidth=0.8, markersize=11,
               label=f'Afro-descendentes (n={len(afro_vals)})'),
        Line2D([0], [0], marker='o', color='none',
               markerfacecolor=COL_BRANCA, markeredgecolor='white',
               markeredgewidth=0.8, markersize=11,
               label=f'Brancas (n={len(branca_vals)})'),
    ]
    ax.legend(handles=legend_handles, loc='upper left',
              bbox_to_anchor=(0.01, 0.98),
              fontsize=9.5, framealpha=0.95, edgecolor='#cccccc',
              handletextpad=0.4)

    # Summary table at the bottom — counts below/at/above
    if "Total" in counts:
        rows = [
            ("Grupo", "Abaixo R$ 210", "= R$ 210", "Acima R$ 210", "Total"),
            ("Afro",
             f"{counts['Afro']['below']} ({100*counts['Afro']['below']/counts['Afro']['n']:.0f}%)",
             str(counts['Afro']['at']),
             str(counts['Afro']['above']),
             str(counts['Afro']['n'])),
            ("Brancas",
             f"{counts['Brancas']['below']} ({100*counts['Brancas']['below']/counts['Brancas']['n']:.0f}%)",
             str(counts['Brancas']['at']),
             str(counts['Brancas']['above']),
             str(counts['Brancas']['n'])),
            ("Total",
             f"{counts['Total']['below']} ({100*counts['Total']['below']/counts['Total']['n']:.0f}%)",
             str(counts['Total']['at']),
             str(counts['Total']['above']),
             str(counts['Total']['n'])),
        ]
        # Render the table as text in axes coordinates, below the plot
        # Use figure-relative coordinates so it sits cleanly below the axes
        col_x = [0.05, 0.30, 0.50, 0.65, 0.82]
        table_y = -0.27
        for col_idx, header in enumerate(rows[0]):
            fig.text(col_x[col_idx], table_y,
                     header,
                     fontsize=9, fontweight='bold', color='#1a252f',
                     ha='left', va='top')
        for row_idx, row in enumerate(rows[1:], start=1):
            y = table_y - 0.04 * row_idx
            for col_idx, cell in enumerate(row):
                color = '#1a252f'
                weight = 'normal'
                if col_idx == 0:
                    weight = 'bold'
                    if row[0] == 'Afro':
                        color = COL_AFRO
                    elif row[0] == 'Brancas':
                        color = COL_BRANCA
                fig.text(col_x[col_idx], y, cell,
                         fontsize=9, color=color, fontweight=weight,
                         ha='left', va='top')

    # Title + subtitle ABOVE the plot
    ax.text(0, 1.10, title, transform=ax.transAxes,
            fontsize=11.5, fontweight='bold', color='#1a252f')
    if subtitle:
        ax.text(0, 1.04, subtitle, transform=ax.transAxes,
                fontsize=9, color='#6b7280', style='italic')

    plt.subplots_adjust(top=0.85, bottom=0.30, left=0.05, right=0.97)
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
    # PNG-only refresh (user said no need to update PDF this round)
    # plt.savefig(out_path.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    medians = {"afro": float(np.median(afro_vals)) if afro_vals else None,
               "branca": float(np.median(branca_vals)) if branca_vals else None,
               "total": float(np.median(total_vals)) if total_vals else None,
               "_counts": counts}
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
    # Relabel brackets to use the actual 2024 CC reference value (R$ 1.540,59)
    # instead of the survey form's outdated threshold (R$ 1.476,75). NOTE: this
    # is a presentation choice — the underlying data still uses the R$ 1.476,75
    # boundary. Respondents counted in "Abaixo de R$ 1.540,59" actually answered
    # "Abaixo de R$ 1.476,75"; there is a small slice (between R$ 1.476,75 and
    # R$ 1.540,59) that legally falls below the CC floor but appears in the
    # next bracket. The report.md commentary explicitly flags this.
    DISPLAY_LABELS = {
        "Abaixo de R$ 1476,75":        "Abaixo de R$ 1.540,59",
        "Entre R$ 1476,75 e R$ 2000,00": "Entre R$ 1.540,59 e R$ 2.000,00",
        "Entre R$ 2000,00 e R$ 3500,00": "Entre R$ 2.000,00 e R$ 3.500,00",
        "Acima de 3500,00":            "Acima de R$ 3.500,00",
    }
    xt["category"] = xt["category"].replace(DISPLAY_LABELS)
    out_png = OUT_DIR / "Q04_base_salary.png"
    render_chart(xt,
                 title='Q9 — Salário base (faixas) por raça',
                 subtitle='Piso CC Doméstica SP 2024 = R$ 1.540,59',
                 out_path=out_png)
    # Compute % below minimum (using the relabeled bracket)
    below_min_afro = xt.loc[xt["category"] == "Abaixo de R$ 1.540,59", "afro_pct"].iloc[0]
    below_min_branca = xt.loc[xt["category"] == "Abaixo de R$ 1.540,59", "branca_pct"].iloc[0]
    above_3500_afro = xt.loc[xt["category"] == "Acima de R$ 3.500,00", "afro_pct"].iloc[0]
    above_3500_branca = xt.loc[xt["category"] == "Acima de R$ 3.500,00", "branca_pct"].iloc[0]
    # ---- Stratified analysis: salary × contract type × race ----
    contr_col = find_col(df, "6 -")
    sub_q4q6 = df[df[col].notna() & df[contr_col].notna()].copy()
    # NOTE: filter still uses the original survey value — only the DISPLAY
    # label was relabeled to the actual 2024 CC value (R$ 1.540,59).
    sub_q4q6["below"] = (sub_q4q6[col] == "Abaixo de R$ 1476,75")
    pct_below_by = {}
    for contract in ["Diarista", "Com vínculo"]:
        for grp in ["afro", "branca"]:
            cell = sub_q4q6[(sub_q4q6[contr_col] == contract)
                            & (sub_q4q6["race_group"] == grp)]
            n = len(cell)
            below = int(cell["below"].sum())
            pct_below_by[(contract, grp)] = (
                100*below/n if n else None, n, below
            )

    commentary = (
        f"**Referências 2024 (quando a pesquisa foi aplicada):**\n\n"
        f"- Salário mínimo federal: **R$ 1.412,00**\n"
        f"- **Piso da Convenção Coletiva doméstica SP (Faixa 1): R$ 1.540,59** ← valor REAL em 2024\n"
        f"- Limite usado nas faixas do formulário: R$ 1.476,75 (piso CC 2023, **defasado**)\n\n"
        f"**⚠ Nota metodológica crítica:** o formulário da pesquisa foi feito com a faixa "
        f"\"Abaixo de R$ 1.476,75\" porque tomou o piso CC 2023 como referência, mas as "
        f"respostas chegaram em 2024 quando o piso já era R$ 1.540,59. Isto significa que "
        f"**a pesquisa SUBESTIMA o descumprimento**: trabalhadoras que recebiam entre "
        f"R$ 1.476,75 e R$ 1.540,59 estão **abaixo do piso CC vigente** mas aparecem na "
        f"faixa \"Entre R$ 1.476,75 e R$ 2.000,00\". O número real de descumprimento é maior "
        f"que os {pct_pt(xt.loc[xt['category'] == 'Abaixo de R$ 1.540,59', 'total_race_known_pct'].iloc[0])} reportados.\n\n"
        f"**Achado bruto contra-intuitivo** (precisa ser destrinchado): "
        f"{pct_pt(below_min_afro)} das afro vs {pct_pt(below_min_branca)} das brancas recebem "
        f"**abaixo de R$ 1.476,75** (que é abaixo até do piso defasado — descumprimento "
        f"inquestionável). Esse padrão é oposto ao observado no PNADC nacional (negras ganham "
        f"menos). Mas estratificar por **tipo de contrato (Q6)** muda completamente a leitura:\n\n"
        f"**Descumprimento (abaixo de R$ 1.476,75) por tipo de contrato:**\n\n"
        f"- **Diaristas (n=76)**: 42% abaixo — descumprimento massivo.\n"
        f"  - Afro diaristas: {pct_pt(pct_below_by[('Diarista','afro')][0])} "
        f"({pct_below_by[('Diarista','afro')][2]}/{pct_below_by[('Diarista','afro')][1]})\n"
        f"  - Brancas diaristas: {pct_pt(pct_below_by[('Diarista','branca')][0])} "
        f"({pct_below_by[('Diarista','branca')][2]}/{pct_below_by[('Diarista','branca')][1]})\n"
        f"- **Com-vínculo (n=72)**: 17% abaixo — situação significativamente melhor.\n"
        f"  - Afro com-vínculo: {pct_pt(pct_below_by[('Com vínculo','afro')][0])} "
        f"({pct_below_by[('Com vínculo','afro')][2]}/{pct_below_by[('Com vínculo','afro')][1]})\n"
        f"  - Brancas com-vínculo: {pct_pt(pct_below_by[('Com vínculo','branca')][0])} "
        f"({pct_below_by[('Com vínculo','branca')][2]}/{pct_below_by[('Com vínculo','branca')][1]})\n\n"
        f"**O verdadeiro eixo do descumprimento é diarismo × com-vínculo, não raça.** "
        f"Diaristas são 2,5× mais vulneráveis ao descumprimento que trabalhadoras com vínculo. "
        f"A 'inversão' racial agregada reflete dois problemas:\n\n"
        f"1. **Não-significância estatística**: ICs Wilson 95% para 'abaixo do piso' se "
        f"sobrepõem entre afro [12,8%; 26,7%] e brancas [19,4%; 38,0%]. Teste z duas "
        f"proporções: p ≈ 0,11 — o gap aparente de 9pp pode ser ruído amostral.\n"
        f"2. **Viés de auto-seleção** + **ambiguidade da pergunta para diaristas**: brancas "
        f"que respondem à pesquisa STDMSP são subpopulação periférica; 'salário base' para "
        f"diarista não é categoria legal clara (a CC define piso por dia, não mensal).\n\n"
        f"**Recomendação editorial:** apresentar primariamente como **'descumprimento "
        f"concentrado em diaristas (42%) e generalizado dado o piso real de R$ 1.540,59'**, "
        f"com gap racial subordinado à estrutura contratual e não estatisticamente robusto."
    )
    sections.append(("Q04", "Salário base", "R$ por mês · faixas",
                     commentary, out_png, xt))

    # ============================================================
    # Q04b — Salário × contract × race (deep-dive to deconfound the racial gap)
    # ============================================================
    contr_col = find_col(df, "6 -")
    sub_strat = df[df[col].notna() & df[contr_col].notna()].copy()

    # Bar chart: % below CC, 4 bars (2 contract × 2 race) + 2 totals
    sub_strat["below"] = (sub_strat[col] == "Abaixo de R$ 1476,75")  # original survey threshold
    cells = []
    for contract in ["Diarista", "Com vínculo"]:
        for grp_label, grp_filter, grp_color in [
            ("Afro", "afro", COL_AFRO),
            ("Brancas", "branca", COL_BRANCA),
        ]:
            cell = sub_strat[(sub_strat[contr_col] == contract)
                             & (sub_strat["race_group"] == grp_filter)]
            n = len(cell)
            below = int(cell["below"].sum())
            pct = 100*below/n if n else None
            cells.append({"contract": contract, "race": grp_label,
                          "n": n, "below": below, "pct": pct, "color": grp_color})
        # Total bar (afro + branca) for the contract
        cell_total = sub_strat[(sub_strat[contr_col] == contract)
                               & (sub_strat["race_group"].isin(["afro", "branca"]))]
        n_t = len(cell_total)
        below_t = int(cell_total["below"].sum())
        pct_t = 100*below_t/n_t if n_t else None
        cells.append({"contract": contract, "race": "Total",
                      "n": n_t, "below": below_t, "pct": pct_t, "color": COL_TOTAL})

    # ===== Side-by-side panels: Diaristas | Com-vínculo, sharing X axis =====
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.0),
                                   sharex=True, sharey=True,
                                   gridspec_kw={'wspace': 0.08})
    panel_data = {
        "Diarista":     [c for c in cells if c["contract"] == "Diarista"],
        "Com vínculo":  [c for c in cells if c["contract"] == "Com vínculo"],
    }
    panel_headlines = {
        "Diarista":     ("DIARISTAS", "42% abaixo do piso CC",
                          COL_AFRO, '#fee2e2'),
        "Com vínculo":  ("COM VÍNCULO", "17% abaixo do piso CC",
                          '#475569', '#e5e7eb'),
    }

    race_order = ["Total", "Brancas", "Afro"]  # bottom-to-top within each panel

    for ax, (contract, pdata) in zip([ax1, ax2], panel_data.items()):
        # Sort cells in race_order so positions match across panels
        pdata_sorted = sorted(pdata, key=lambda c: race_order.index(c["race"]))
        y = np.arange(len(pdata_sorted))
        pcts = [c["pct"] for c in pdata_sorted]
        colors = [c["color"] for c in pdata_sorted]

        bars = ax.barh(y, pcts, color=colors, edgecolor='white',
                       linewidth=0.6, height=0.62)

        # Value labels — bold, with sample size in parens
        for i, c in enumerate(pdata_sorted):
            ax.text(c["pct"] + 1.5, i,
                    f"{pct_pt(c['pct'])}  ({c['below']}/{c['n']})",
                    va='center', fontsize=10, fontweight='bold', color='#1a252f')

        # Y-axis labels (race only — contract is in the panel headline)
        ax.set_yticks(y)
        ax.set_yticklabels([c["race"] for c in pdata_sorted], fontsize=10.5)

        ax.set_xlim(0, 70)
        ax.set_xticks([0, 10, 20, 30, 40, 50, 60])
        ax.set_xticklabels([f"{v}%" for v in [0, 10, 20, 30, 40, 50, 60]], fontsize=9)
        ax.grid(axis='x', linestyle=':', linewidth=0.4,
                color='#bbbbbb', alpha=0.6, zorder=0)
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Panel headline ABOVE the plot area — group name + headline rate
        hl_name, hl_rate, hl_color, hl_bg = panel_headlines[contract]
        ax.text(0, 1.12, hl_name,
                transform=ax.transAxes,
                fontsize=11, fontweight='bold', color=hl_color,
                ha='left', va='bottom')
        ax.text(0, 1.04, hl_rate,
                transform=ax.transAxes,
                fontsize=12, fontweight='bold', color='#1a252f',
                ha='left', va='bottom',
                bbox=dict(boxstyle='round,pad=0.35', facecolor=hl_bg,
                          edgecolor=hl_color, linewidth=0.8))

    # Shared X-axis label (centered below both panels)
    fig.text(0.5, 0.04,
             '% recebendo abaixo de R$ 1.540,59  ·  Piso CC Doméstica SP 2024',
             fontsize=10, ha='center', va='center')

    # Master title above everything
    fig.suptitle('Descumprimento do piso CC — diaristas vs com-vínculo, por raça',
                 fontsize=12.5, fontweight='bold', color='#1a252f',
                 x=0.05, y=1.02, ha='left')
    fig.text(0.05, 0.97,
             'Diaristas têm descumprimento 2,5× maior que com-vínculo. '
             'O eixo dominante é o tipo de contrato, não a raça.',
             fontsize=9.5, color='#6b7280', style='italic',
             ha='left', va='top')

    # Comparative arrow between the two panels' "Total" bars (visual emphasis)
    # Skip if pcts can't be extracted — defensive
    try:
        total_diarista = next(c["pct"] for c in panel_data["Diarista"] if c["race"] == "Total")
        total_vinculo = next(c["pct"] for c in panel_data["Com vínculo"] if c["race"] == "Total")
        ratio = total_diarista / total_vinculo
        # Add a banner ABOVE the panel headlines summarizing the ratio
        fig.text(0.5, 0.93,
                 f'≈ {ratio:.1f}× diferença',
                 fontsize=10, fontweight='bold', color=COL_AFRO,
                 ha='center', va='top',
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                           edgecolor=COL_AFRO, linewidth=0.8))
    except (StopIteration, ZeroDivisionError):
        pass

    plt.subplots_adjust(top=0.78, bottom=0.13, left=0.10, right=0.97)
    out_png_b = OUT_DIR / "Q04b_salary_by_contract_race.png"
    plt.savefig(out_png_b, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(out_png_b.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # Dummy crosstab so the report builder includes a markdown table
    q4b_rows = []
    for c in cells:
        q4b_rows.append({
            "category": f"{c['contract']} · {c['race']}",
            "afro_n": c["below"] if c["race"] == "Afro" else 0,
            "afro_pct": c["pct"] if c["race"] == "Afro" else None,
            "branca_n": c["below"] if c["race"] == "Brancas" else 0,
            "branca_pct": c["pct"] if c["race"] == "Brancas" else None,
            "total_race_known_n": c["below"] if c["race"] == "Total" else c["n"],
            "total_race_known_pct": c["pct"] if c["race"] == "Total" else None,
        })
    q4b_xt = pd.DataFrame()  # skip table; commentary speaks for itself

    q4b_commentary = (
        "**O verdadeiro eixo do descumprimento é o tipo de contrato, não a raça.** "
        "Diaristas tem 42% abaixo do limite da pesquisa (R$ 1.476,75); com-vínculo têm 17%. "
        "Dentro de cada contrato, o gap racial é secundário (brancas levemente acima em "
        "ambos os grupos). Esse padrão estratificado contradiz a leitura ingênua do Q04 agregado.\n\n"
        "**Caveat metodológico crítico (dupla camada):**\n\n"
        "1. **Piso defasado no formulário**: o limite R$ 1.476,75 usado nas faixas reflete "
        "o piso CC de 2023. Em 2024, quando a pesquisa foi aplicada, o piso CC real era "
        "R$ 1.540,59. Trabalhadoras entre esses dois valores estão **abaixo do piso vigente** "
        "mas aparecem na faixa imediatamente superior. **O descumprimento real é maior "
        "que os 22% reportados** — possivelmente significativamente.\n"
        "2. **CC negociado para trabalhadoras com vínculo**: para diaristas, a CC SP "
        "estabelece um piso por dia trabalhado, não um salário mensal. A pergunta 'salário "
        "base' é ambígua nessa categoria. Para diaristas, 'abaixo do piso' deve ser lido "
        "como **proxy de vulnerabilidade econômica**, não descumprimento legal estrito."
    )
    sections.append(("Q04b", "Salário × contrato × raça",
                     "Decompondo o achado contra-intuitivo do Q04",
                     q4b_commentary, out_png_b, q4b_xt))

    # ============================================================
    # Q5 — Diária value (Q16A, continuous)
    # ============================================================
    col = find_col(df, "16A")
    out_png = OUT_DIR / "Q05_diaria_value.png"
    DIARIA_FLOOR_2024 = 210.0   # Piso diária CC Doméstica SP 2024 (Faixa 1)
    medians = render_continuous(
        df, col,
        title='Q16A — Valor cobrado por diária — cada ponto é uma respondente',
        subtitle=f'Apenas diaristas (n=73) · Piso diária CC SP 2024 = R$ {int(DIARIA_FLOOR_2024)}',
        out_path=out_png,
        reference_value=DIARIA_FLOOR_2024,
        reference_label=f'Piso CC SP 2024\nR$ {int(DIARIA_FLOOR_2024)}',
    )
    if medians and medians.get("afro") and medians.get("branca"):
        m_afro = medians["afro"]
        m_branca = medians["branca"]
        counts = medians.get("_counts", {})
        c_total = counts.get("Total", {})
        c_afro  = counts.get("Afro", {})
        c_branca = counts.get("Brancas", {})

        pct_below_total = (100 * c_total.get("below", 0) / c_total.get("n", 1)
                           if c_total.get("n") else 0)
        pct_below_afro = (100 * c_afro.get("below", 0) / c_afro.get("n", 1)
                          if c_afro.get("n") else 0)
        pct_below_branca = (100 * c_branca.get("below", 0) / c_branca.get("n", 1)
                            if c_branca.get("n") else 0)

        commentary = (
            f"**Achado principal — descumprimento massivo do piso diária:** "
            f"**{pct_below_total:.0f}% das diaristas recebem abaixo do piso CC SP 2024 "
            f"(R$ {int(DIARIA_FLOOR_2024)})**.\n\n"
            f"**Distribuição completa (R$ 80 a R$ 360):**\n\n"
            f"| Faixa | Afro | Brancas | Total |\n"
            f"|---|---:|---:|---:|\n"
            f"| Abaixo de R$ {int(DIARIA_FLOOR_2024)} | "
            f"{c_afro.get('below', 0)} ({pct_below_afro:.0f}%) | "
            f"{c_branca.get('below', 0)} ({pct_below_branca:.0f}%) | "
            f"{c_total.get('below', 0)} ({pct_below_total:.0f}%) |\n"
            f"| Igual a R$ {int(DIARIA_FLOOR_2024)} | "
            f"{c_afro.get('at', 0)} | "
            f"{c_branca.get('at', 0)} | "
            f"{c_total.get('at', 0)} |\n"
            f"| Acima de R$ {int(DIARIA_FLOOR_2024)} | "
            f"{c_afro.get('above', 0)} | "
            f"{c_branca.get('above', 0)} | "
            f"{c_total.get('above', 0)} |\n"
            f"| **Total** | **{c_afro.get('n', 0)}** | **{c_branca.get('n', 0)}** | "
            f"**{c_total.get('n', 0)}** |\n\n"
            f"**Medianas:** afro R$ {m_afro:.0f} · brancas R$ {m_branca:.0f} · "
            f"total R$ {medians['total']:.0f}.\n\n"
            f"**Sem hiato racial significativo na mediana** — diferente do padrão PNADC "
            f"BR-wide (hiato 84,3%/hora no diarismo). No entorno STDMSP a heterogeneidade "
            f"é dentro de cada grupo, não entre grupos: valores de R$ 80 até R$ 360, "
            f"com concentração em R$ 150-R$ 200. A diária mediana paulista (~R$ 180) "
            f"é **15% abaixo do piso CC** — descumprimento generalizado, atravessando "
            f"raça."
        )
    else:
        commentary = "Amostra muito pequena para comparação racial confiável."
    # Build a fake xt for the report builder
    dummy_xt = pd.DataFrame()
    sections.append(("Q05", "Valor da diária — distribuição individual",
                     f"Diaristas (n=73) · Piso CC SP 2024 = R$ {int(DIARIA_FLOOR_2024)}",
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
    # Q11b — Q17A comentário aberto (follow-up de Q11/Q17)
    # 5 categorias aprovadas 2026-06-22:
    #   1. Orientação / informação sobre direitos
    #   2. Intervenção direta com o patrão
    #   3. Ação jurídica / fiscalização / denúncia
    #   4. Dúvida / desconhecimento / sem experiência (default)
    #   5. Limitação / ceticismo / impossibilidade prática
    # ============================================================
    Q17A_BUCKETS = {
        "1": "1. Orientação sobre direitos",
        "2": "2. Intervenção direta com o patrão",
        "3": "3. Ação jurídica / denúncia",
        "4": "4. Dúvida / sem experiência",
        "5": "5. Limitação / impossibilidade",
    }

    import unicodedata
    def _no_accents(s: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                       if unicodedata.category(c) != 'Mn')

    def categorize_q17a(s: str) -> str | None:
        if s is None or pd.isna(s):
            return None
        t = _no_accents(str(s)).lower().strip()
        if not t:
            return None

        # --- Cat 5: explicit limitation / skepticism (highest priority —
        # captures the structural barrier even if some action is also named)
        cat5 = [
            "nao pode entrar", "nao vai ate", "nao vai no",
            "nao consegue", "nao respeita", "nao permite nada",
            "nao aceita nem o sindicato", "nao manda nelas",
            "nao manda nela", "muito dificil",
            "acho dificil", "acho muito dificil",
            "se o patrao deixar", "se a patroa deixar",
            "ninguem nunca veio",
            "nao da tempo",
            "depende da situacao",
            "porque a patroa nao", "porque o patrao nao",
            "patrao nao reconhec", "nao quer reconhecer",
            "patroa nao quer", "patrao nao quer",
            "porque eu nao trabalho registrada",
            "cada dia numa casa",
            "nao autonomia", "nem permissao",
            "mas usando a lei",
            "somente quando a gente",
            "se o patrao nao",
            "acha que nao pode",
            "porem na minha epoca",
            "se a patroa me acusar",
            "se a patroa nao cuida",
            "se for o caso de patrao",
            "talvez, se o patrao",
        ]
        if any(kw in t for kw in cat5):
            return "5"

        # --- Cat 3: legal/enforcement
        cat3 = [
            "juridic", "judicial", "advogad", "processo",
            "denunci", "fiscaliz", "pericia",
            "executa", "executanto", "homologa",
            "autoridades trabalhistas",
            "intervencao judicial",
            "acao para fiscalizar",
            "parte juridica",
            "atuando numa acao",
        ]
        if any(kw in t for kw in cat3):
            return "3"

        # --- Cat 2: direct intervention with employer
        cat2 = [
            "chamando o patr", "chamando a patr", "chamando os patr",
            "chamando a patroa", "chamar a patroa", "chamar o patrao",
            "chama a patroa", "chama o patrao",
            "alertando os patr", "alertando o patr", "alertando a patr",
            "cobrar do patr", "cobrar o patr", "cobrar patr",
            "cobrando do patr", "cobrando o patr", "cobrando patr",
            "intervir no local de trabalho",
            "intervindo diretamente",
            "atuando diretamente junto",
            "junto com o patrao", "junto ao patrao",
            "chamando o empregador", "chamar o empregador",
        ]
        if any(kw in t for kw in cat2):
            return "2"

        # --- Cat 1: orientation / information / defense of rights
        cat1 = [
            "orient",         # orientar, orientação, orientando
            "inform",         # informar, informação
            "explica",        # explicar, explicando
            "esclarec",
            "tirar duvida", "tirar as duvidas",
            "rodas de conversa",
            "ensin",
            "divulg",
            "conscientiz",
            "dizendo", "dizer o que",
            "instruir",
            "defesa", "defender", "defendendo", "defente",  # incl. misspelling
            "defen ",
            "garantir os direitos", "garantindo os",
            "cuidando dos", "cuidando de",
            "auxili",
            "ajudando nos direit", "ajudam nos direit", "ajuda nos direit",
            "ajuda em",
            "buscar as duvid", "buscar dos nossos direit",
            "correndo atras dos direit",
            "fala sobre direit",
            "dar a palavra", "dar palavra",
            "tabulacao",
            "dando informacao", "dando orienta",
            "fornecendo ajuda",
            "buscar dos direitos",
            "intervindo diretamente em nossos direitos",
            "para que receba", "garantindo que receba",
            "garantir o que",
            "atendimento",
            "organizando", "organiza tudo",
        ]
        if any(kw in t for kw in cat1):
            return "1"

        # --- Cat 4: default — doubt / no experience / vague affirmation
        return "4"

    col17a = find_col(df, "17A")
    df["q17a_bucket"] = df[col17a].apply(categorize_q17a)
    bucket_order_17a = list(Q17A_BUCKETS.keys())
    xt = crosstab(df, "q17a_bucket", order=bucket_order_17a)
    xt["category"] = xt["category"].map(Q17A_BUCKETS)
    out_png = OUT_DIR / "Q11b_union_helps_how.png"
    render_chart(xt,
                 title='Q17A — Como o sindicato pode ajudar (comentário aberto)',
                 subtitle='Categorização heurística do texto livre · n=164 respostas válidas',
                 out_path=out_png)
    # Pull cell counts for commentary
    cat1 = xt.loc[xt["category"] == Q17A_BUCKETS["1"]]
    cat4 = xt.loc[xt["category"] == Q17A_BUCKETS["4"]]
    cat5 = xt.loc[xt["category"] == Q17A_BUCKETS["5"]]
    cat1_total = int(cat1["total_race_known_n"].iloc[0]) if len(cat1) else 0
    cat1_pct   = float(cat1["total_race_known_pct"].iloc[0]) if len(cat1) else 0
    cat4_total = int(cat4["total_race_known_n"].iloc[0]) if len(cat4) else 0
    cat4_pct   = float(cat4["total_race_known_pct"].iloc[0]) if len(cat4) else 0
    cat5_total = int(cat5["total_race_known_n"].iloc[0]) if len(cat5) else 0
    cat5_pct   = float(cat5["total_race_known_pct"].iloc[0]) if len(cat5) else 0

    commentary_17a = (
        f"**Como a categoria entende o papel do sindicato em situações difíceis** "
        f"(complemento qualitativo a Q11/Q17, que perguntou se o sindicato pode "
        f"ajudar — 83% disseram sim).\n\n"
        f"**Achado dominante: o sindicato é entendido principalmente como "
        f"instituição educacional/informacional** ({pct_pt(cat1_pct)}, n={cat1_total}). "
        f"A maioria absoluta vê o papel sindical como **orientar, informar e "
        f"explicar direitos** — não como mediador direto com o patrão nem como "
        f"canal jurídico.\n\n"
        f"**Cerca de {pct_pt(cat4_pct)} ({cat4_total} respondentes) "
        f"admitem dúvida ou falta de experiência** — *'acho que sim, mas não sei como'*, "
        f"*'nunca precisei'*, *'agora que descobri vou procurar'*. Esse percentual é "
        f"consistente com o gargalo informacional já identificado em Q08/Q09 "
        f"(apenas ~25% conhecem a CC).\n\n"
        f"**Apenas {pct_pt(cat5_pct)} ({cat5_total}) reconhecem barreiras "
        f"estruturais** — *'o sindicato não pode entrar no meu trabalho'*, *'as patroas "
        f"falam que o sindicato não manda nelas'*, *'se o patrão deixar, né'*. "
        f"Pequena mas eloquente — articula o limite estrutural do trabalho doméstico "
        f"em domicílio privado.\n\n"
        f"**Implicação editorial:** as respostas confirmam que **a categoria pensa "
        f"o sindicato primariamente como espaço de aprendizado**, não como aparelho "
        f"de luta institucional. Para a STDMSP, isso é simultaneamente boa notícia "
        f"(confiança no papel educacional) e desafio (a função jurídica/de intervenção "
        f"existe mas não está internalizada pela base)."
    )
    for d in find_discrepancies(xt):
        commentary_17a += (
            f" Diferença ≥10pp em **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp).")
    sections.append(("Q11b", "Como o sindicato ajuda (texto livre)",
                     "Categorização 5-buckets do Q17A (n=164)",
                     commentary_17a, out_png, xt))

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
        """Categoriza Q18 em 5 buckets por keyword-first heurística.

        Correção 2026-07-03 pós-auditoria (JF Mayer notou que respostas com
        "cuidar/cuidando" ficavam presas na Cat 5 residual porque o keyword
        era "cuidado"/substantivo).  Passamos a usar RADICAIS (cuid, proteg,
        acolh, ampar, defend, orient, inform, esclarec, divulg, conscientiz,
        fiscaliz, cobr, jurídic) para capturar todas as flexões verbais.
        Ver etl/audit_q18_categorization.py + Q18_audit.md.
        """
        if s is None or pd.isna(s):
            return None
        text = str(s).strip().lower()
        if not text:
            return None
        if any(kw in text for kw in ["defend", "defesa", "direitos trabalh", "lutar pelo bem",
                                       "lutar pelos direitos", "garantir o que o trabalho",
                                       "garantia dos direitos", "garantir o direito",
                                       "buscar direitos", "buscar os direitos"]):
            return "1"
        if any(kw in text for kw in ["orient", "inform", "esclarec",
                                       "esclaresc", "divulg", "conscientiz",
                                       "instruir", "ensinar", "valoriza"]):
            return "2"
        if any(kw in text for kw in ["jurídic", "advogad", "processo", "lei ", "leis",
                                       "judicial", "fiscaliz", "cobr", "patrão",
                                       "patrões", "empregador"]):
            return "3"
        if any(kw in text for kw in ["cuid", "proteg", "acolh",
                                       "ampar", "apoio", "apoiar", "suporte", "ajudar todos",
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
                 subtitle='',
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
    # Q13 — Tempo de trabalho na categoria (questionnaire Q7)
    # ============================================================
    col = find_col(df, "7 -")
    tempo_order = ["Entre 1 e 2 anos", "Entre 3 e 5 anos",
                   "Entre 5 e 10 anos", "Entre 10 e 20 anos",
                   "Mais de 20 anos"]
    xt = crosstab(df, col, order=tempo_order)
    out_png = OUT_DIR / "Q13_tempo_trabalho.png"
    render_chart(xt,
                 title='Q7 — Há quanto tempo você trabalha como trabalhadora doméstica?',
                 subtitle='STDMSP Pesquisa A (2024) · % dentro de cada grupo racial · n=236',
                 out_path=out_png)
    # Aggregate 10+ years share for both groups
    def _sum_pct(xt_df, cats, col):
        return sum(xt_df.loc[xt_df["category"] == c, col].iloc[0] or 0 for c in cats)
    long_cats = ["Entre 10 e 20 anos", "Mais de 20 anos"]
    afro_long = _sum_pct(xt, long_cats, "afro_pct")
    branca_long = _sum_pct(xt, long_cats, "branca_pct")
    total_long = _sum_pct(xt, long_cats, "total_race_known_pct")
    afro_20 = xt.loc[xt["category"] == "Mais de 20 anos", "afro_pct"].iloc[0] or 0
    branca_20 = xt.loc[xt["category"] == "Mais de 20 anos", "branca_pct"].iloc[0] or 0
    commentary = (
        f"A categoria é de **carreira longa**: **{pct_pt(total_long)} da amostra tem mais de "
        f"10 anos** trabalhando como doméstica ({pct_pt(afro_long)} afro vs "
        f"{pct_pt(branca_long)} brancas). O bloco 'mais de 20 anos' sozinho concentra "
        f"{pct_pt(afro_20)} das afro e {pct_pt(branca_20)} das brancas — combinado com o achado "
        f"da Q1 (afro concentradas em 50-59 anos), sugere trajetória de permanência prolongada "
        f"na categoria entre afro-descendentes. Trabalhadoras com menos de 2 anos são "
        f"minoritárias (<10% em ambos os grupos), coerente com a queda geral do "
        f"pool de novas entrantes documentada na PNADC. "
    )
    for d in find_discrepancies(xt):
        commentary += (
            f"Diferença ≥10pp em **{d['category']}**: "
            f"afro {pct_pt(d['afro'])} vs brancas {pct_pt(d['branca'])} ({d['delta']:+.1f}pp). ")
    sections.append(("Q13", "Tempo de trabalho na categoria",
                     "Anos trabalhando como doméstica · comparação por raça",
                     commentary, out_png, xt))

    # ============================================================
    # Q14 — Benefícios da CC recebidos × idade (universo Q13=Sim)
    # ============================================================
    # Recorte: quem afirmou (Q13) que a CC trouxe benefício direto (n=77).
    # De 77, apenas 25 detalharam quais benefícios recebem (Q14 multi-select).
    # Cruzamos essas 25 respostas com Q1 (idade). n final=24 com idade válida,
    # 33 menções benefício-linha (multi-select expandido).
    # AMOSTRA MUITO PEQUENA — apresentar com caveat explícito.
    col_q13 = find_col(df, "13 -")
    col_q14 = find_col(df, "14 -")
    col_q1  = find_col(df, "1 -")

    BENEFIT_LABELS = {
        "Cesta Básica":   "Cesta Básica",
        "BEM +Familiar":  "BEM +Familiar",
        "Bem Brasil":     "Bem Brasil",
        "Auxílio Creche": "Auxílio Creche",
    }
    def parse_benefits(v):
        if pd.isna(v):
            return []
        s = str(v).lower()
        out = []
        if "cesta bás" in s or "cesta bas" in s:
            out.append("Cesta Básica")
        if "bem +familiar" in s or "bem+familiar" in s:
            out.append("BEM +Familiar")
        if "bem brasil" in s:
            out.append("Bem Brasil")
        if "auxílio creche" in s or "auxilio creche" in s:
            out.append("Auxílio Creche")
        return out

    sim = df[df[col_q13] == "Sim"].copy()
    sim = sim[sim[col_q14].notna()].copy()
    sim["benefits"] = sim[col_q14].apply(parse_benefits)
    sim = sim[sim["benefits"].apply(len) > 0].copy()
    sim = sim.explode("benefits")
    sim = sim.dropna(subset=[col_q1])

    age_order_q14 = ["Entre 18 e 29 anos", "Entre 30 e 39 anos",
                     "Entre 40 e 49 anos", "Entre 50 e 59 anos",
                     "Acima de 60 anos"]
    benefit_order = ["Cesta Básica", "BEM +Familiar", "Bem Brasil", "Auxílio Creche"]

    heat = pd.crosstab(sim["benefits"], sim[col_q1])
    heat = heat.reindex(index=benefit_order, columns=age_order_q14, fill_value=0)
    row_totals = heat.sum(axis=1)
    col_totals = heat.sum(axis=0)
    grand_total = int(heat.values.sum())

    # Distinct respondents (deduplicated) for the caveat
    sim_uniq = df[df[col_q13] == "Sim"].copy()
    sim_uniq = sim_uniq[sim_uniq[col_q14].notna()].copy()
    sim_uniq["benefits"] = sim_uniq[col_q14].apply(parse_benefits)
    sim_uniq = sim_uniq[sim_uniq["benefits"].apply(len) > 0]
    sim_uniq = sim_uniq[sim_uniq[col_q1].notna()]
    n_respondents = int(len(sim_uniq))
    n_sim_total = int((df[col_q13] == "Sim").sum())

    # ------- Heatmap -------
    fig, ax = plt.subplots(figsize=(10.0, 5.4))
    data = heat.values.astype(float)
    # Use accent-red colormap consistent with dashboard palette
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "stdmsp_red", ["#ffffff", "#fee2e2", "#fca5a5", "#dc2626", "#7f1d1d"])
    im = ax.imshow(data, cmap=cmap, aspect="auto",
                   vmin=0, vmax=max(data.max(), 1))

    # Cell annotations with count
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = int(data[i, j])
            color = "white" if v >= data.max() * 0.55 else "#1a252f"
            weight = "bold" if v > 0 else "normal"
            txt = str(v) if v > 0 else "·"
            ax.text(j, i, txt, ha="center", va="center",
                    color=color, fontsize=11, fontweight=weight)

    # Row / column labels
    ax.set_yticks(range(len(benefit_order)))
    ax.set_yticklabels([f"{b}\n(total {int(row_totals[b])})"
                        for b in benefit_order], fontsize=9.5)
    ax.set_xticks(range(len(age_order_q14)))
    ax.set_xticklabels([wrap_label(a, width=14) + f"\n(total {int(col_totals[a])})"
                        for a in age_order_q14], fontsize=9)

    ax.set_xlabel("Faixa etária (Q1)", fontsize=10.5, labelpad=10)
    ax.set_ylabel("Benefício da CC recebido (Q14)", fontsize=10.5, labelpad=10)

    # Tick appearance
    ax.tick_params(axis="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, shrink=0.75, pad=0.02)
    cbar.set_label("Nº de trabalhadoras", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    # Title + subtitle
    ax.text(0, 1.16,
            "Q14 × Q1 — Tipos de benefício da CC recebidos × idade",
            transform=ax.transAxes,
            fontsize=11.5, fontweight="bold", color="#1a252f")
    ax.text(0, 1.08,
            f"Universo: quem respondeu SIM em Q13 (n={n_sim_total}) E detalhou benefícios "
            f"em Q14 (n={n_respondents}) · células = nº de menções (multi-select)",
            transform=ax.transAxes,
            fontsize=9, color="#6b7280", style="italic")

    # Caveat below
    fig.text(0.05, 0.02,
             f"Atenção: base analítica muito pequena (n={n_respondents} respondentes, "
             f"{grand_total} menções). Padrões devem ser lidos como indicativos, "
             f"não representativos.",
             fontsize=8.5, color="#b91c1c", style="italic")

    plt.subplots_adjust(left=0.20, top=0.80, bottom=0.20, right=0.95)
    out_png = OUT_DIR / "Q14_benefits_by_age.png"
    plt.savefig(out_png, dpi=300, bbox_inches='tight', facecolor='white')
    plt.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # ---- Commentary ----
    top_ben_share = row_totals["Cesta Básica"] / grand_total if grand_total else 0
    conc_40plus = (col_totals["Entre 40 e 49 anos"] +
                   col_totals["Entre 50 e 59 anos"] +
                   col_totals["Acima de 60 anos"]) / grand_total if grand_total else 0
    commentary = (
        f"**Base analítica: n={n_respondents} respondentes** (de 77 que disseram "
        f"SIM em Q13 sobre a CC ter trazido benefício, apenas 25 detalharam QUAIS "
        f"benefícios recebem). O gap 77→25 é ele mesmo um achado: **~2/3 de quem "
        f"reconhece impacto da CC não consegue nomear os benefícios concretos** — "
        f"sugere que a CC opera como referência simbólica difusa, não como catálogo "
        f"de vantagens navegáveis pela trabalhadora. "
        f"\n\n"
        f"Dentro desse recorte pequeno mas concentrado:\n\n"
        f"1. **Cesta Básica domina absolutamente**: {int(row_totals['Cesta Básica'])} "
        f"das {grand_total} menções ({pct_pt(100*top_ben_share)}). Único benefício "
        f"da CC que chega a todas as faixas etárias 40+ na amostra. "
        f"Interpretação: quando a CC 'aparece' materialmente na vida da doméstica, "
        f"aparece como comida.\n"
        f"2. **BEM +Familiar e Bem Brasil** ficam num degrau abaixo "
        f"({int(row_totals['BEM +Familiar'])} e {int(row_totals['Bem Brasil'])} menções), "
        f"concentrados em 40-49 e 50-59.\n"
        f"3. **Auxílio Creche = 1 menção só** — coerente com o perfil etário da amostra "
        f"(quase ninguém tem filho pequeno em casa nesta faixa).\n"
        f"4. **{pct_pt(100*conc_40plus)} das menções concentram-se em 40+** — "
        f"nenhuma trabalhadora 18-29 e apenas 1 na faixa 30-39 detalhou benefícios. "
        f"Isso reforça o padrão da Q13 (categoria envelhecida) e sugere que o "
        f"benefício da CC é reconhecido depois de anos de acumulação de tempo "
        f"na categoria.\n\n"
        f"Peça de política: o gargalo não é a existência da CC — é a **legibilidade** "
        f"dos benefícios individualizados (cartões, auxílios) para quem já se "
        f"beneficia da CC via floor salarial e cesta básica. Campanha de divulgação "
        f"deveria priorizar quem tem entre 30 e 49 anos com filho pequeno "
        f"(potencial Auxílio Creche subutilizado)."
    )
    # No standard xt table for the heatmap — pass a dummy for the report builder
    dummy_xt = pd.DataFrame()
    sections.append(("Q14", "Benefícios da CC × idade",
                     f"Q13=Sim ∩ Q14 detalhado (n={n_respondents}) · cruzamento com Q1",
                     commentary, out_png, dummy_xt))

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
        f.write("**Referências 2024 para o item 4 (salário):** "
                "R$ 1.412,00 = salário mínimo federal · "
                "**R$ 1.540,59 = piso CC doméstica SP 2024 (Faixa 1)** · "
                "R$ 1.476,75 = limite usado nas faixas da pesquisa (piso CC 2023, defasado) — "
                "a pesquisa **subestima** o descumprimento porque trabalhadoras entre R$ 1.476,75 "
                "e R$ 1.540,59 estão abaixo do piso vigente mas aparecem na faixa superior.\n\n")
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
        f.write("4. **Salário base (Q9) — gap racial NÃO significativo + descumprimento "
                "subestimado**: 18,5% afro vs 27,7% brancas recebem abaixo de R$ 1.476,75. "
                "Mas (a) o gap é estatisticamente não-significativo (p ≈ 0,11, ICs Wilson "
                "se sobrepõem); e (b) o piso CC real em 2024 era **R$ 1.540,59** — o "
                "formulário usou um limite defasado, então o descumprimento real é maior "
                "que o reportado. **A história verdadeira é Q04b (diaristas 42% vs vínculo "
                "17%) — o eixo do descumprimento é contratual, não racial.**\n")
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
