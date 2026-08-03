"""
analyze_q13_gap_explanation.py  (v2 — readability pass)
=======================================================

Purpose: explain why Q13 shows a +9pp gap (afro 40% vs brancas 31% saying the CC
brought benefit).

Approach: decompose the gap by conditioning on three plausible mediators
(tempo, salário, conhecimento da CC) and check if the gap survives.

Finding: gap PERSISTS and often AMPLIFIES within the sub-groups where the CC
would be materially most relevant (long tenure, mid-upper salary, CC-aware).
The pattern is not compositional — it is that the CC materializes DIFFERENTLY
for afro and branca workers, favoring afro in the strata where it matters.

Layout choices (v2):
- Panel headers ABOVE each subplot with mediator name in bold.
- Single-line "afro n / branca n" caption below x-tick labels with in-line
  color-coded numbers (via two adjacent text calls) → no more stacked ns.
- Delta pill annotations on bar pairs where |Δ| ≥ 10pp, highlighting the
  strata where the gap AMPLIFIES.
- Reference lines with in-plot value labels at the right edge of each panel.
- Suptitle + subtitle + legend stacked with generous vertical budget so
  nothing collides.

Output: chapter/survey_a_analysis/Q13_gap_decomposition.png (+ .pdf)
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch

rcParams['font.family'] = 'serif'
rcParams['font.size'] = 10
rcParams['axes.linewidth'] = 0.7
rcParams['axes.spines.top'] = False
rcParams['axes.spines.right'] = False
rcParams['axes.edgecolor'] = '#222222'
rcParams['pdf.fonttype'] = 42
rcParams['ps.fonttype'] = 42

COL_AFRO   = '#b91c1c'
COL_BRANCA = '#475569'
COL_GRID   = '#dddddd'
COL_MUTED  = '#94a3b8'

ROOT = Path(__file__).parent.parent
SRC = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT = ROOT / "chapter" / "survey_a_analysis" / "Q13_gap_decomposition.png"

df = pd.read_excel(SRC)

def race(v):
    if pd.isna(v): return None
    s = str(v).strip().lower()
    if s in ('pardo','parda','preto','preta'): return 'afro'
    if s in ('branco','branca'): return 'branca'
    return 'outras'

def col(prefix):
    for c in df.columns:
        if c.startswith(prefix):
            return c
    raise KeyError(prefix)

q3 = col('3 -')
df['race'] = df[q3].apply(race)
q7  = col('7 -')   # tempo
q9  = col('9 -')   # salary
q11 = col('11-')   # sabe o que é CC
q13 = col('13 -')  # Q13 CC trouxe benefício

d = df[df['race'].isin(['afro','branca'])].copy()

def pct_sim(sub, colname, order):
    sub = sub.dropna(subset=[q13, colname])
    sub = sub[sub[q13].isin(['Sim','Não'])]
    out = {}
    for cat in order:
        s = sub[sub[colname]==cat]
        n = len(s)
        sim = (s[q13]=='Sim').sum()
        out[cat] = (100*sim/n if n else None, n)
    return out

# ---------- panels ----------
panels = [
    ("Tempo na categoria", q7,
     ["Entre 1 e 2 anos","Entre 3 e 5 anos","Entre 5 e 10 anos",
      "Entre 10 e 20 anos","Mais de 20 anos"],
     ["1-2 anos","3-5 anos","5-10 anos","10-20 anos","20+ anos"]),
    ("Faixa salarial (base)", q9,
     ["Abaixo de R$ 1476,75","Entre R$ 1476,75 e R$ 2000,00",
      "Entre R$ 2000,00 e R$ 3500,00","Acima de 3500,00"],
     ["< R$ 1.476","R$ 1.476\n– 2.000","R$ 2.000\n– 3.500","> R$ 3.500"]),
    ("Conhecimento da CC (Q11)", q11,
     ["Não","Sim"],
     ["Não sabe\no que é","Sabe\no que é"]),
]

# Baseline
base_afro = 100 * (d[d['race']=='afro'][q13]=='Sim').sum() / \
            d[d['race']=='afro'][q13].isin(['Sim','Não']).sum()
base_branca = 100 * (d[d['race']=='branca'][q13]=='Sim').sum() / \
              d[d['race']=='branca'][q13].isin(['Sim','Não']).sum()

# ---------- figure ----------
# Use gridspec to give the salary panel more room (4 categories vs 5)
fig, axes = plt.subplots(1, 3, figsize=(16.5, 6.4),
                         gridspec_kw={'width_ratios': [5, 4, 2.4]},
                         sharey=True)

for ax_i, (title, colname, order, short_labels) in enumerate(panels):
    ax = axes[ax_i]
    afro_stats   = pct_sim(d[d['race']=='afro'], colname, order)
    branca_stats = pct_sim(d[d['race']=='branca'], colname, order)

    x = np.arange(len(order))
    width = 0.36

    afro_pcts = [afro_stats[o][0] or 0 for o in order]
    branca_pcts = [branca_stats[o][0] or 0 for o in order]
    afro_ns = [afro_stats[o][1] for o in order]
    branca_ns = [branca_stats[o][1] for o in order]

    # ---- Baseline reference lines (draw BEFORE bars so bars overlay) ----
    ax.axhline(base_afro, color=COL_AFRO, linestyle=':', linewidth=1.1,
               alpha=0.55, zorder=1)
    ax.axhline(base_branca, color=COL_BRANCA, linestyle=':', linewidth=1.1,
               alpha=0.55, zorder=1)

    # ---- Bars ----
    ax.bar(x - width/2, afro_pcts, width, color=COL_AFRO,
           edgecolor='white', linewidth=0.8, zorder=3)
    ax.bar(x + width/2, branca_pcts, width, color=COL_BRANCA,
           edgecolor='white', linewidth=0.8, zorder=3)

    # ---- Percentage labels above bars ----
    for xi, (v, n) in enumerate(zip(afro_pcts, afro_ns)):
        if n >= 3:
            ax.text(xi - width/2, v + 2.6, f"{v:.0f}%",
                    ha='center', fontsize=10.5, fontweight='bold',
                    color=COL_AFRO, zorder=5)
    for xi, (v, n) in enumerate(zip(branca_pcts, branca_ns)):
        if n >= 3:
            ax.text(xi + width/2, v + 2.6, f"{v:.0f}%",
                    ha='center', fontsize=10.5, fontweight='bold',
                    color=COL_BRANCA, zorder=5)

    # ---- Delta pill annotations where |Δ| ≥ 10pp ----
    for xi, (a, b, na, nb) in enumerate(
            zip(afro_pcts, branca_pcts, afro_ns, branca_ns)):
        if na < 3 or nb < 3:
            continue
        delta = a - b
        if abs(delta) < 10:
            continue
        y_top = max(a, b) + 12
        color = COL_AFRO if delta > 0 else COL_BRANCA
        sign = "+" if delta > 0 else ""
        ax.annotate(
            f"Δ {sign}{delta:.0f}pp",
            xy=(xi, y_top), ha='center', va='center',
            fontsize=9.5, fontweight='bold', color='white',
            bbox=dict(boxstyle='round,pad=0.35',
                      facecolor=color, edgecolor='none'),
            zorder=6,
        )

    # ---- n= caption (single line per x-tick, color-coded) ----
    # Place afro n and branca n on the same row using two text calls
    for xi, (na, nb) in enumerate(zip(afro_ns, branca_ns)):
        ax.text(xi - 0.02, -9, f"n={na}", ha='right', va='top',
                fontsize=8.5, color=COL_AFRO)
        ax.text(xi + 0.02, -9, f" · n={nb}", ha='left', va='top',
                fontsize=8.5, color=COL_BRANCA)

    # ---- X ticks ----
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, fontsize=9.5)
    ax.tick_params(axis='x', length=0, pad=6)

    # ---- Panel title (mediator name) ----
    ax.set_title(title, fontsize=11.5, fontweight='bold',
                 color='#1a252f', pad=12, loc='left')

    # ---- Y axis ----
    ax.set_ylim(-16, 108)
    ax.set_yticks(range(0, 101, 20))
    ax.set_yticklabels([f"{t}%" for t in range(0, 101, 20)], fontsize=9)
    ax.grid(axis='y', linestyle=':', linewidth=0.5, color=COL_GRID, zorder=0)
    ax.set_axisbelow(True)

    if ax_i == 0:
        ax.set_ylabel("% que responderam SIM em Q13\n"
                      "(“a CC trouxe benefício para você?”)",
                      fontsize=10.5, labelpad=10)

    # ---- Right-edge labels for reference lines (only rightmost panel) ----
    if ax_i == len(panels) - 1:
        ax.text(len(order) - 0.5 + 0.15, base_afro,
                f" Baseline afro\n {base_afro:.0f}%",
                fontsize=8.5, color=COL_AFRO, va='center',
                fontweight='bold')
        ax.text(len(order) - 0.5 + 0.15, base_branca - 2,
                f" Baseline brancas\n {base_branca:.0f}%",
                fontsize=8.5, color=COL_BRANCA, va='center',
                fontweight='bold')

# ---------- suptitle / subtitle / legend stack ----------
fig.text(0.5, 1.03,
         "Por que afro-descendentes reportam mais benefício da CC do que brancas?",
         ha='center', fontsize=14, fontweight='bold', color='#1a252f')
fig.text(0.5, 0.985,
         "Baseline: afro 40% × brancas 31% (Δ = +9pp).  O gap NÃO é compositional — "
         "sobrevive dentro de cada mediador e AMPLIFICA nos estratos em que a CC "
         "seria materialmente mais relevante.",
         ha='center', fontsize=10.3, color='#4b5563', style='italic')

# Legend below subtitle, above panels
legend_handles = [
    plt.Rectangle((0,0),1,1, color=COL_AFRO,   label='Afro-descendentes'),
    plt.Rectangle((0,0),1,1, color=COL_BRANCA, label='Brancas'),
    plt.Line2D([0],[0], color=COL_AFRO,   linestyle=':', linewidth=1.8,
               label='···  Baseline afro (40%)'),
    plt.Line2D([0],[0], color=COL_BRANCA, linestyle=':', linewidth=1.8,
               label='···  Baseline brancas (31%)'),
]
fig.legend(handles=legend_handles, loc='upper center',
           bbox_to_anchor=(0.5, 0.945), ncol=4,
           fontsize=10, framealpha=0, handlelength=1.4,
           columnspacing=2.2, handletextpad=0.6)

# Footer caption on n= convention
fig.text(0.5, -0.02,
         "Rótulos abaixo de cada barra: n de respondentes por raça na sub-célula.  "
         "Pílulas Δ marcam pares com diferença ≥ 10pp.",
         ha='center', fontsize=8.5, color=COL_MUTED, style='italic')

plt.subplots_adjust(top=0.86, bottom=0.14, left=0.06, right=0.98, wspace=0.10)
plt.savefig(OUT, dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig(OUT.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved: {OUT}")
