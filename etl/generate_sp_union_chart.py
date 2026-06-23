"""
generate_sp_union_chart.py — SP × BR union filiation chart for Mayer chapter
=============================================================================

Three print-ready figures:
  1. grafico_filiacao_sp_vs_br.{pdf,png}
     Time series 2012-2024 of SP vs BR overall filiation rates.
     Reveals SP's surprising under-performance vs national average.
  2. grafico_filiacao_uf_ranking_2024.{pdf,png}
     Horizontal bar chart ranking UFs by filiation in 2024 (top 20),
     SP highlighted in accent color. NE clusters at top, urban SE at bottom.
  3. grafico_filiacao_sp_three_scales.{pdf,png}
     SP-specific three-scale contrast: SP general (1.6%) × SP por
     raça/formalidade × STDMSP entorno (31.2% from Survey B Q32).

Source: dashboard/data/fact_union_timeseries.csv (post UF backfill).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams


# Academic typography (matches the existing chapter charts)
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


ROOT = Path(__file__).parent.parent
SRC = ROOT / "dashboard" / "data" / "fact_union_timeseries.csv"
OUT_DIR = ROOT / "chapter"


COL_SP   = '#b91c1c'       # accent red — SP highlighted
COL_BR   = '#1a252f'       # charcoal — national reference
COL_NE   = '#6b7280'       # gray — northeast cluster
COL_OTHER = '#d4d4d4'      # light gray


def pct_pt(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:.1f}%".replace(".", ",")


# ----- Figure 1: SP vs BR trajectory -----

def fig_sp_vs_br(df: pd.DataFrame):
    br = df[df["cut"] == "overall"].sort_values("year")
    sp = df[(df["cut"] == "uf_overall") & (df["group"] == "SP")].sort_values("year")

    years_br = br["year"].astype(int).tolist()
    pct_br = br["pct_filiadas"].astype(float).tolist()
    years_sp = sp["year"].astype(int).tolist()
    pct_sp = sp["pct_filiadas"].astype(float).tolist()

    fig, ax = plt.subplots(figsize=(8.4, 5.0))

    # Set ylim FIRST so policy labels can position relative to it
    Y_MAX = 36
    ax.set_ylim(0, Y_MAX)

    # Policy markers — text at top of plot area, lines through full height
    policy = [
        (2013, "PEC 72"),
        (2015, "LC 150"),
        (2017, "Reforma\n2017"),
    ]
    for yr, lbl in policy:
        ax.axvline(yr, color='#aaaaaa', linestyle=':', linewidth=0.8, zorder=1)
        ax.text(yr, Y_MAX * 0.97, lbl, fontsize=8, color='#555555',
                ha='center', va='top', style='italic',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                          edgecolor='none', alpha=0.85))

    # COVID gap — subtle band
    ax.axvspan(2019.5, 2021.5, color='#f5f5f0', alpha=0.6, zorder=0)
    ax.text(2020.5, 0.7, 'COVID\n(s/ campo)', fontsize=7.5,
            color='#888888', ha='center', va='bottom', style='italic')

    # Trajectories (drawn on top of background elements)
    ax.plot(years_br, pct_br,
            color=COL_BR, linestyle='-', marker='o', markersize=7,
            linewidth=2.2, label='Brasil',
            markeredgecolor='white', markeredgewidth=1.0, zorder=4)
    ax.plot(years_sp, pct_sp,
            color=COL_SP, linestyle='-', marker='s', markersize=7,
            linewidth=2.2, label='São Paulo',
            markeredgecolor='white', markeredgewidth=1.0, zorder=4)

    # STDMSP entorno star — centered on 2022, with annotation BELOW-LEFT
    ax.scatter([2022], [31.2], color=COL_SP, marker='*', s=380,
               edgecolor='#1a252f', linewidth=0.9, zorder=5,
               label='Entorno STDMSP (Pesq. B Q32, 2021–23)')
    ax.annotate('31,2%',
                xy=(2022, 31.2), xytext=(0, 12),
                textcoords='offset points',
                fontsize=10, fontweight='bold', color=COL_SP,
                ha='center')
    # Smaller caption near the star, below the line, not over the trajectories
    ax.annotate('entorno STDMSP\n(Pesquisa B, n=231)',
                xy=(2022, 31.2), xytext=(-58, -32),
                textcoords='offset points',
                fontsize=8, color='#6b7280', style='italic',
                ha='center',
                arrowprops=dict(arrowstyle='-', color='#bbbbbb',
                                linewidth=0.6, connectionstyle="arc3,rad=0.2"))

    # SP-specific 2023 callout (the floor)
    floor_2023 = float(sp[sp.year == 2023]["pct_filiadas"].iloc[0])
    ax.annotate(f'piso histórico\nSP 2023: {pct_pt(floor_2023)}',
                xy=(2023, floor_2023), xytext=(-44, 38),
                textcoords='offset points',
                fontsize=8, color=COL_SP, style='italic',
                ha='center',
                arrowprops=dict(arrowstyle='->', color=COL_SP,
                                linewidth=0.6))

    # Axes
    ax.set_xlim(2011.5, 2024.5)
    ax.set_xticks([2012, 2014, 2016, 2018, 2020, 2022, 2024])
    ax.set_xticklabels([str(y) for y in [2012, 2014, 2016, 2018, 2020, 2022, 2024]],
                       fontsize=9.5)
    ax.set_yticks([0, 5, 10, 15, 20, 25, 30, 35])
    ax.set_yticklabels([f"{v}%" for v in [0, 5, 10, 15, 20, 25, 30, 35]], fontsize=9.5)
    ax.set_ylabel('% filiadas a sindicato (ponderado)', fontsize=10.5, labelpad=10)

    ax.grid(axis='y', linestyle=':', linewidth=0.4, color='#bbbbbb', alpha=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Title + subtitle ABOVE plot area
    ax.text(0, 1.10,
            'SP × Brasil — filiação sindical das trabalhadoras domésticas, 2012–2024',
            transform=ax.transAxes, fontsize=11.5, fontweight='bold', color='#1a252f')
    ax.text(0, 1.04,
            'SP fica consistentemente abaixo da média nacional; '
            'STDMSP entorno é exceção dentro do estado',
            transform=ax.transAxes, fontsize=9, color='#6b7280', style='italic')

    # Legend pinned to the LEFT (free of the STDMSP star and right-side annotations)
    ax.legend(loc='upper left', bbox_to_anchor=(0.01, 0.86),
              fontsize=9, framealpha=0.95,
              edgecolor='#cccccc', handlelength=2.2)

    plt.subplots_adjust(top=0.85, bottom=0.10, left=0.10, right=0.97)
    pdf = OUT_DIR / "grafico_filiacao_sp_vs_br.pdf"
    png = OUT_DIR / "grafico_filiacao_sp_vs_br.png"
    plt.savefig(pdf, bbox_inches='tight', facecolor='white')
    plt.savefig(png, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  {pdf}")
    print(f"  {png}")


# ----- Figure 2: UF ranking 2024 -----

NE_UFS = {"PI", "MA", "PB", "CE", "RN", "AL", "PE", "BA", "SE"}

def fig_uf_ranking_2024(df: pd.DataFrame):
    latest = df.year.max()
    ufs = (df[(df.cut == "uf_overall") & (df.year == latest)]
           .sort_values("pct_filiadas", ascending=True)
           .copy())
    if len(ufs) > 20:
        ufs = ufs.tail(20).reset_index(drop=True)
    else:
        ufs = ufs.reset_index(drop=True)
    n_ufs = len(ufs)

    # Color SP in accent red; NE in dark gray; others in light gray
    colors = []
    for _, r in ufs.iterrows():
        if r["group"] == "SP":
            colors.append(COL_SP)
        elif r["group"] in NE_UFS:
            colors.append(COL_NE)
        else:
            colors.append(COL_OTHER)

    fig, ax = plt.subplots(figsize=(8.4, 0.38 * n_ufs + 2.0))
    y = np.arange(n_ufs)
    pcts = ufs["pct_filiadas"].astype(float).tolist()
    bars = ax.barh(y, pcts, color=colors, edgecolor='white', linewidth=0.6, height=0.72)

    # Value labels — bold for SP, regular for others; positioned with explicit gap
    max_pct = max(pcts)
    for i, (pct, n) in enumerate(zip(pcts, ufs["n"].astype(int))):
        label = f"{pct_pt(pct)}  (n={n})"
        is_sp = ufs.iloc[i]["group"] == "SP"
        ax.text(pct + max_pct * 0.012, i, label,
                va='center', fontsize=9,
                color=COL_SP if is_sp else '#1a252f',
                fontweight='bold' if is_sp else 'normal')

    ax.set_yticks(y)
    ax.set_yticklabels(ufs["group"].tolist(), fontsize=10)
    for tick_label, g in zip(ax.get_yticklabels(), ufs["group"]):
        if g == "SP":
            tick_label.set_fontweight('bold')
            tick_label.set_color(COL_SP)

    # National reference line — dashed, with label at top-right
    br_pct = float(df[(df.cut == "overall") & (df.year == latest)]["pct_filiadas"].iloc[0])
    ax.axvline(br_pct, color='#1a252f', linestyle='--', linewidth=1.1, zorder=2, alpha=0.7)
    ax.text(br_pct, n_ufs - 0.3,
            f' média BR\n  {pct_pt(br_pct)}',
            fontsize=8.5, color='#1a252f', style='italic',
            va='top', ha='left',
            bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                      edgecolor='#cccccc', linewidth=0.5))

    # X-axis with extra room for value labels (longest is ~"11,9%  (n=277)")
    ax.set_xlim(0, max_pct * 1.28)
    ax.set_xlabel('% trabalhadoras domésticas filiadas a sindicato',
                  fontsize=10.5, labelpad=10)
    ax.grid(axis='x', linestyle=':', linewidth=0.4, color='#bbbbbb', alpha=0.6, zorder=0)
    ax.set_axisbelow(True)

    # ===== LEGEND — explicit handles (top-right area) =====
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=COL_SP, label='SP (São Paulo)'),
        Patch(facecolor=COL_NE, label='Nordeste'),
        Patch(facecolor=COL_OTHER, label='Outros estados'),
    ]
    ax.legend(handles=legend_handles, loc='lower right',
              fontsize=9, framealpha=0.95,
              edgecolor='#cccccc', handlelength=1.4, handleheight=1.0)

    ax.text(0, 1.06,
            f'Ranking de UFs por filiação sindical doméstica — {int(latest)}',
            transform=ax.transAxes, fontsize=11.5, fontweight='bold', color='#1a252f')
    ax.text(0, 1.02,
            'Nordeste lidera, capitais do Sudeste no fundo · top 20 UFs',
            transform=ax.transAxes, fontsize=9, color='#6b7280', style='italic')

    plt.subplots_adjust(top=0.93, bottom=0.08, left=0.10, right=0.96)
    pdf = OUT_DIR / "grafico_filiacao_uf_ranking_2024.pdf"
    png = OUT_DIR / "grafico_filiacao_uf_ranking_2024.png"
    plt.savefig(pdf, bbox_inches='tight', facecolor='white')
    plt.savefig(png, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  {pdf}")
    print(f"  {png}")


# ----- Figure 3: SP three scales -----

def fig_sp_three_scales(df: pd.DataFrame):
    latest = df.year.max()
    sp_overall = float(df[(df.cut == "uf_overall") & (df.group == "SP") &
                           (df.year == latest)]["pct_filiadas"].iloc[0])
    # SP × race
    sp_negras = df[(df.cut == "sp_race") & (df.group == "negras") &
                   (df.year == latest)]
    sp_nao = df[(df.cut == "sp_race") & (df.group == "nao_negras") &
                (df.year == latest)]
    sp_negras_pct = float(sp_negras["pct_filiadas"].iloc[0]) if len(sp_negras) else None
    sp_nao_pct = float(sp_nao["pct_filiadas"].iloc[0]) if len(sp_nao) else None
    # SP × formality
    sp_com = df[(df.cut == "sp_formality") & (df.group == "com_carteira") &
                (df.year == latest)]
    sp_sem = df[(df.cut == "sp_formality") & (df.group == "sem_carteira") &
                (df.year == latest)]
    sp_com_pct = float(sp_com["pct_filiadas"].iloc[0]) if len(sp_com) else None
    sp_sem_pct = float(sp_sem["pct_filiadas"].iloc[0]) if len(sp_sem) else None

    entorno = 31.2

    br_pct = float(df[(df.cut == "overall") & (df.year == latest)]
                     ["pct_filiadas"].iloc[0])

    # Ordered from smallest to largest for visual ramp
    bars = [
        {"label": "SP × negras", "value": sp_negras_pct,
         "color": "#475569", "n_label": "(n=606)"},
        {"label": "SP geral", "value": sp_overall,
         "color": "#94a3b8", "n_label": "(n=1.087)"},
        {"label": "SP × com carteira", "value": sp_com_pct,
         "color": "#475569", "n_label": "(n=375)"},
        {"label": "Brasil geral",
         "value": br_pct, "color": "#1a252f", "n_label": "(n=10.795)"},
        {"label": "Entorno STDMSP\n(Pesq. B Q32)", "value": entorno,
         "color": COL_SP, "n_label": "(n=231)"},
    ]
    bars = [b for b in bars if b["value"] is not None]

    fig, ax = plt.subplots(figsize=(8.6, 4.0))
    y = np.arange(len(bars))
    vals = [b["value"] for b in bars]
    colors = [b["color"] for b in bars]
    labels = [b["label"] for b in bars]
    n_labels = [b["n_label"] for b in bars]

    ax.barh(y, vals, color=colors, edgecolor='white', linewidth=0.6, height=0.65)

    # Value labels + sample-size note, right of bars
    for i, (v, n) in enumerate(zip(vals, n_labels)):
        ax.text(v + max(vals) * 0.012, i,
                f'{pct_pt(v)}  {n}',
                va='center', fontsize=10, fontweight='bold', color='#1a252f')

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()

    # Highlight the STDMSP bar tick label in red
    for tick_label, b in zip(ax.get_yticklabels(), bars):
        if "STDMSP" in b["label"]:
            tick_label.set_fontweight('bold')
            tick_label.set_color(COL_SP)

    # Ratio annotation — top-right corner, free of bars
    ratio = entorno / sp_overall if sp_overall else None
    if ratio:
        ax.text(0.99, 0.96,
                f'STDMSP entorno\n÷ SP geral\n= {str(round(ratio, 1)).replace(".", ",")}×',
                transform=ax.transAxes, fontsize=10, ha='right', va='top',
                fontweight='bold', color=COL_SP,
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#fee2e2',
                          edgecolor=COL_SP, linewidth=0.8))

    ax.set_xlim(0, max(vals) * 1.30)
    ax.set_xlabel('% trabalhadoras filiadas a sindicato', fontsize=10.5, labelpad=10)
    ax.grid(axis='x', linestyle=':', linewidth=0.4, color='#bbbbbb', alpha=0.6)
    ax.set_axisbelow(True)

    ax.text(0, 1.10,
            f'Filiação sindical doméstica em São Paulo — {int(latest)}',
            transform=ax.transAxes, fontsize=11.5, fontweight='bold', color='#1a252f')
    ax.text(0, 1.04,
            'Cinco escalas: dentro de SP × Brasil × entorno STDMSP',
            transform=ax.transAxes, fontsize=9, color='#6b7280', style='italic')

    plt.subplots_adjust(top=0.85, bottom=0.14, left=0.24, right=0.97)
    pdf = OUT_DIR / "grafico_filiacao_sp_three_scales.pdf"
    png = OUT_DIR / "grafico_filiacao_sp_three_scales.png"
    plt.savefig(pdf, bbox_inches='tight', facecolor='white')
    plt.savefig(png, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  {pdf}")
    print(f"  {png}")


def main():
    df = pd.read_csv(SRC)
    print(f"Loaded {len(df)} rows · cuts: {sorted(df.cut.unique())}\n")
    print("Figures:")
    fig_sp_vs_br(df)
    fig_uf_ranking_2024(df)
    fig_sp_three_scales(df)


if __name__ == "__main__":
    main()
