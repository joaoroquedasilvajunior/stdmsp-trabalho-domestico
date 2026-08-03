"""
build_survey_charts.py — Demo: plotnine + ninejs equivalent of the Chart.js mockup
=====================================================================================

Rebuilds the carteira × race panel from chapter/survey_page_mockup.html using
the Python plotnine + ninejs toolchain. The output is a standalone HTML file
with hover tooltips and (optionally) click/grouping events.

Saved to chapter/survey_charts/ — same folder convention as the Chart.js mockup
so the comparison is direct.

Once we agree this is the right toolchain, the same pattern extends to the
other 4 panels (salário histogram, migração origem, CCT knowledge stacks).
"""

from pathlib import Path
import pandas as pd
from plotnine import (
    ggplot, aes, geom_col, coord_flip, scale_fill_manual,
    labs, theme_minimal, theme, element_text, element_blank, element_rect,
    scale_x_discrete, scale_y_continuous,
)
from ninejs import interactive, save, css


ROOT = Path(__file__).parent.parent
DATA = ROOT / "chapter" / "survey_harmonized" / "survey_consolidated.csv"
OUT_DIR = ROOT / "chapter" / "survey_charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def panel_carteira():
    """Carteira × raça (Survey B only). Reproduces Panel 2 of the mockup."""
    df = pd.read_csv(DATA)

    # Filter to Survey B with valid race and carteira
    b = df[
        (df["survey_id"] == "B")
        & df["raca_grupo"].notna()
        & df["tem_carteira"].notna()
    ].copy()

    # Group and compute percentages within each race
    grouped = (
        b.groupby(["raca_grupo", "tem_carteira"])
        .size()
        .reset_index(name="n")
    )
    totals = grouped.groupby("raca_grupo")["n"].transform("sum")
    grouped["pct"] = 100 * grouped["n"] / totals

    # Friendly Portuguese labels
    grouped["raca_label"] = grouped["raca_grupo"].map({
        "negras": "Negras\n(pretas + pardas)",
        "nao_negras": "Não-negras",
    })
    grouped["carteira_label"] = grouped["tem_carteira"].map({
        "Sim": "Com carteira",
        "Nao": "Sem carteira",
    })

    # Tooltip text — shows in HTML on hover
    grouped["tooltip"] = grouped.apply(
        lambda r: f"{r['raca_label'].replace(chr(10), ' ')} · {r['carteira_label']}: "
                  f"{r['n']} trabalhadoras ({r['pct']:.1f}%)",
        axis=1
    )

    # Color palette mirroring the dashboard / Chart.js mockup
    COLORS = {
        "Com carteira": "#b91c1c",   # accent red
        "Sem carteira": "#cbd5e1",   # muted gray
    }

    gg = (
        ggplot(
            grouped,
            aes(
                x="raca_label", y="pct", fill="carteira_label",
                tooltip="tooltip",
                data_id="carteira_label",   # ninejs hover-group key
            )
        )
        + geom_col(width=0.6)
        + coord_flip()
        + scale_fill_manual(values=COLORS, name="")
        + scale_y_continuous(
            breaks=[0, 25, 50, 75, 100],
            labels=["0%", "25%", "50%", "75%", "100%"],
            limits=[0, 101],
        )
        + labs(
            x="",
            y="% das respondentes",
            title="Carteira assinada × raça",
            subtitle="Em São Paulo, trabalhadoras negras reportam carteira com mais frequência que as não-negras",
            caption="Pesquisa B · 2021–23 · STDMSP · n=231 respondentes",
        )
        + theme_minimal()
        + theme(
            figure_size=(8, 4),
            text=element_text(family="serif", size=11),
            plot_title=element_text(size=14, weight="bold"),
            plot_subtitle=element_text(size=11, color="#444"),
            plot_caption=element_text(size=9, color="#888", style="italic"),
            axis_text=element_text(size=10),
            legend_position="bottom",
            panel_grid_major_y=element_blank(),
            panel_background=element_rect(fill="white", color="white"),
        )
    )

    # Add interactivity: tooltips on hover; hover-grouping on the carteira series
    out_path = OUT_DIR / "panel_carteira.html"
    (
        interactive(gg)
        + css(from_dict={
            ".tooltip": {
                "font-family": "Inter, system-ui, sans-serif",
                "font-size": "13px",
                "padding": "6px 10px",
                "background": "#1a252f",
                "color": "white",
                "border-radius": "4px",
                "box-shadow": "0 2px 6px rgba(0,0,0,0.15)",
            },
        })
        + save(str(out_path))
    )
    print(f"Wrote {out_path}")
    return out_path


if __name__ == "__main__":
    panel_carteira()
