"""
generate_union_chart.py — Print-ready charts for the Mayer book chapter
========================================================================

Generates two academic figures suitable for the published chapter:

  1. grafico_filiacao_serie_temporal.{pdf,png}
     4-series line chart of % filiadas by race × formality, 2012-2024,
     with vertical policy annotations (PEC 2013, LC150 2015, Reforma 2017).

  2. grafico_filiacao_tres_escalas.{pdf,png}
     A horizontal bar chart showing the three-scale contrast:
     piso absoluto (negras × com_carteira 2024), baseline nacional 2024,
     STDMSP entorno (Pesquisa B Q32).

Both designed for B&W reproduction in a printed book — serif typography,
modest line weights, no color reliance.

Source: dashboard/data/fact_union_timeseries.csv (V4097 time series)
        + Pesquisa B Q32 figures from probe_survey_b_union.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.lines import Line2D
import pandas as pd


# Academic typography
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
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Style — designed for B&W reproduction. We rely on line style + marker shape
# to distinguish 4 series, not just color (color is the backup signal).
SERIES_STYLE = {
    "negras_sem_carteira":     dict(color="#1a252f", linestyle="-",  marker="o",
                                    label_pt="Negras × sem carteira",
                                    label_en="Black × no signed card"),
    "negras_com_carteira":     dict(color="#1a252f", linestyle="--", marker="s",
                                    label_pt="Negras × com carteira",
                                    label_en="Black × signed card"),
    "nao_negras_sem_carteira": dict(color="#6b7280", linestyle="-",  marker="^",
                                    label_pt="Não-negras × sem carteira",
                                    label_en="Non-Black × no signed card"),
    "nao_negras_com_carteira": dict(color="#6b7280", linestyle="--", marker="D",
                                    label_pt="Não-negras × com carteira",
                                    label_en="Non-Black × signed card"),
}

POLICY_LINES = [
    {"year": 2013, "label": "PEC 72\n(Direitos)", "y_offset": 0.05},
    {"year": 2015, "label": "LC 150\n(Regulamentação)", "y_offset": 0.05},
    {"year": 2017, "label": "Reforma\nTrabalhista", "y_offset": 0.05},
]


def pct_pt(v: float) -> str:
    """Brazilian decimal formatting."""
    return f"{v:.1f}%".replace(".", ",")


def fig1_time_series(df: pd.DataFrame):
    """4-series line chart over 2012-2024."""
    fig, ax = plt.subplots(figsize=(7.5, 4.6))

    df_rxf = df[df["cut"] == "race_x_formality"].copy()
    years_present = sorted(df_rxf["year"].unique())

    for group, style in SERIES_STYLE.items():
        sub = df_rxf[df_rxf["group"] == group].sort_values("year")
        if len(sub) == 0:
            continue
        ax.plot(sub["year"], sub["pct_filiadas"],
                color=style["color"], linestyle=style["linestyle"],
                marker=style["marker"], markersize=5.5,
                linewidth=1.4, label=style["label_pt"], zorder=3,
                markeredgecolor="white", markeredgewidth=0.6)

    # Policy reference lines (vertical)
    y_max = 5.0
    for ann in POLICY_LINES:
        ax.axvline(x=ann["year"], color="#aaaaaa", linestyle=":",
                   linewidth=0.8, zorder=1)
        ax.text(ann["year"], y_max - 0.05, ann["label"],
                fontsize=8, color="#555555", ha="center", va="top",
                rotation=0, style="italic")

    # COVID gap callout
    ax.axvspan(2019.5, 2021.5, color="#f5f5f0", alpha=0.7, zorder=0)
    ax.text(2020.5, 0.15, "PNADC-A\nsem campo\n(COVID)", fontsize=7.5,
            color="#777777", ha="center", va="bottom", style="italic")

    # Axes
    ax.set_xlim(2011.5, 2024.5)
    ax.set_xticks([2012, 2014, 2016, 2018, 2020, 2022, 2024])
    ax.set_xticklabels([str(y) for y in [2012, 2014, 2016, 2018, 2020, 2022, 2024]],
                       fontsize=9)
    ax.set_ylim(0, y_max)
    ax.set_yticks([0, 1, 2, 3, 4, 5])
    ax.set_yticklabels([f"{v}%" for v in [0, 1, 2, 3, 4, 5]], fontsize=9)
    ax.set_ylabel("% filiadas a sindicato (ponderado)", fontsize=10, labelpad=8)

    # Grid
    ax.grid(axis="y", linestyle=":", linewidth=0.4, color="#bbbbbb", alpha=0.6, zorder=1)
    ax.set_axisbelow(True)

    # Title
    ax.set_title(
        "Filiação sindical das trabalhadoras domésticas, 2012–2024\n"
        "por raça e formalidade (PNADC-A Visita 1, V4097)",
        fontsize=11.5, pad=10, loc="left", color="#1a252f"
    )

    # Legend — inside, top-right, framed
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.95,
              edgecolor="#cccccc", handlelength=2.4)

    plt.tight_layout()

    pdf = OUT_DIR / "grafico_filiacao_serie_temporal.pdf"
    png = OUT_DIR / "grafico_filiacao_serie_temporal.png"
    plt.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"PDF: {pdf}")
    print(f"PNG: {png}")


def fig2_three_scales(df: pd.DataFrame):
    """Horizontal bar chart of the three-scale contrast."""
    # Extract the figures
    df_overall = df[df["cut"] == "overall"]
    pct_2024 = float(df_overall.loc[df_overall["year"] == 2024, "pct_filiadas"].iloc[0])
    df_rxf = df[df["cut"] == "race_x_formality"]
    pct_floor = float(df_rxf.loc[
        (df_rxf["year"] == 2024) & (df_rxf["group"] == "negras_com_carteira"),
        "pct_filiadas"
    ].iloc[0])
    pct_entorno = 31.2  # Pesquisa B Q32

    bars = [
        {"label": "Negras com carteira\n(piso absoluto)", "value": pct_floor,
         "note": "n=1.645", "color": "#1a252f"},
        {"label": "Trabalhadoras domésticas\n(baseline nacional 2024)", "value": pct_2024,
         "note": "n=10.795", "color": "#475569"},
        {"label": "Entorno STDMSP\n(Pesquisa B Q32, 2021–23)", "value": pct_entorno,
         "note": "n=231", "color": "#2c3e50"},
    ]

    fig, ax = plt.subplots(figsize=(7.5, 3.4))

    y_pos = list(range(len(bars)))
    values = [b["value"] for b in bars]
    labels = [b["label"] for b in bars]
    colors = [b["color"] for b in bars]
    notes = [b["note"] for b in bars]

    ax.barh(y_pos, values, color=colors, height=0.55,
            edgecolor="#1a252f", linewidth=0.4)

    # Numeric labels at the end of each bar
    for i, (v, n) in enumerate(zip(values, notes)):
        ax.text(v + 0.6, i, f"{pct_pt(v)}  ({n})",
                va="center", fontsize=10, fontweight="bold", color="#1a252f")

    # Y-axis labels
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.invert_yaxis()

    # X-axis
    ax.set_xlim(0, 38)
    ax.set_xticks([0, 5, 10, 15, 20, 25, 30, 35])
    ax.set_xticklabels([f"{v}%" for v in [0, 5, 10, 15, 20, 25, 30, 35]], fontsize=9)
    ax.set_xlabel("% filiadas a sindicato", fontsize=10, labelpad=10)

    # Subtle x-grid
    ax.grid(axis="x", linestyle=":", linewidth=0.4, color="#bbbbbb", alpha=0.6)
    ax.set_axisbelow(True)

    # Compute & annotate the ratio
    ratio = round(pct_entorno / pct_floor, 1)
    ax.text(
        0.99, 0.04,
        f"Razão piso → teto = {str(ratio).replace('.', ',')}×",
        transform=ax.transAxes,
        fontsize=9.5, ha="right", va="bottom",
        style="italic", color="#1a252f",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#cccccc", linewidth=0.5)
    )

    ax.set_title(
        "As três escalas da filiação sindical\n"
        "do piso estrutural ao entorno organizado",
        fontsize=11.5, pad=10, loc="left", color="#1a252f"
    )

    plt.tight_layout()

    pdf = OUT_DIR / "grafico_filiacao_tres_escalas.pdf"
    png = OUT_DIR / "grafico_filiacao_tres_escalas.png"
    plt.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"PDF: {pdf}")
    print(f"PNG: {png}")


def main():
    df = pd.read_csv(SRC)
    fig1_time_series(df)
    fig2_three_scales(df)


if __name__ == "__main__":
    main()
