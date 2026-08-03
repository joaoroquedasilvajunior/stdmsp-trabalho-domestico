"""
analyze_q14_by_race.py
======================

Cross Q14 (benefits of the CC received) with Q3 (race).

Universe:
  - Everyone who answered Q14 with a parseable benefit AND race is
    afro-descendente (pardas + pretas) or branca.
  - n=36 (23 afro + 13 brancas).

Motivation:
  Complementa a decomposição de Q13 (Q13_gap_decomposition.png).  Testa se
  o gap de RECONHECIMENTO da CC em Q13 (afro 40% × brancas 31%) espelha
  um gap de RECEBIMENTO material dos benefícios do CC — ou se as duas
  medidas divergem.

Achado:
  * As duas medidas DIVERGEM.  Brancas recebem levemente MAIS benefícios
    por pessoa (1,31 vs 1,22 média) e taxas ligeiramente maiores para
    Cesta Básica, BEM +Familiar e Bem Brasil.  Só Auxílio Creche é
    exclusivamente afro (2 vs 0).
  * Mas em Q13 afro atribuem MAIS benefício à CC (40% vs 31%).
  * O gap não é de recebimento — é de RECONHECIMENTO / ATRIBUIÇÃO.
  * Além disso: 12 de 38 (32%) das trabalhadoras que detalham benefícios
    da CC em Q14 disseram NÃO em Q13 (a CC NÃO me trouxe benefício).
    Recebem cesta / cartão / auxílio da CC mas não atribuem à CC.

Output:
  chapter/survey_a_analysis/Q14_by_race.png  (+ .pdf)
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams

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
COL_MUTED  = '#94a3b8'
COL_ACCENT = '#a16207'   # ochre for the callout box

ROOT = Path(__file__).parent.parent
SRC = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT = ROOT / "chapter" / "survey_a_analysis" / "Q14_by_race.png"

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

q3  = col('3 -')
q13 = col('13 -')
q14 = col('14 -')
df['race'] = df[q3].apply(race)

def parse_benefits(v):
    if pd.isna(v): return []
    s = str(v).lower()
    out = []
    if "cesta bás" in s or "cesta bas" in s: out.append("Cesta Básica")
    if "bem +familiar" in s or "bem+familiar" in s: out.append("BEM +Familiar")
    if "bem brasil" in s: out.append("Bem Brasil")
    if "auxílio creche" in s or "auxilio creche" in s: out.append("Auxílio Creche")
    return out

# Universe
have_q14 = df[df[q14].notna()].copy()
have_q14["benefits"] = have_q14[q14].apply(parse_benefits)
have_q14 = have_q14[have_q14["benefits"].apply(len) > 0]

# Recognition paradox: how many of Q14 respondents said Q13=Não
n_q14_total = len(have_q14)
n_q14_disagree = (have_q14[q13] == "Não").sum()
n_q14_agree    = (have_q14[q13] == "Sim").sum()

# Race sample
d = have_q14[have_q14["race"].isin(["afro","branca"])].copy()
n_afro   = int((d["race"] == "afro").sum())
n_branca = int((d["race"] == "branca").sum())

# Cross-tab
d_expl = d.explode("benefits")
ct = pd.crosstab(d_expl["benefits"], d_expl["race"])
benefit_order = ["Cesta Básica","BEM +Familiar","Bem Brasil","Auxílio Creche"]
ct = ct.reindex(index=benefit_order, columns=["afro","branca"], fill_value=0)

# % within race
pct_afro   = 100 * ct["afro"]   / n_afro
pct_branca = 100 * ct["branca"] / n_branca

# Mean benefits per respondent
mean_afro   = d[d["race"] == "afro"]["benefits"].apply(len).mean()
mean_branca = d[d["race"] == "branca"]["benefits"].apply(len).mean()

# ---------- Figure ----------
fig = plt.figure(figsize=(13.5, 7.2))
gs  = fig.add_gridspec(1, 2, width_ratios=[3.0, 1.3], wspace=0.28)
ax  = fig.add_subplot(gs[0])
axr = fig.add_subplot(gs[1])

# ----- LEFT PANEL: horizontal grouped bar (benefit × race) -----
y = np.arange(len(benefit_order))
bar_h = 0.36

afro_vals = pct_afro.values
branca_vals = pct_branca.values

# Bars
ax.barh(y - bar_h/2, afro_vals, bar_h, color=COL_AFRO,
        edgecolor='white', linewidth=0.8, zorder=3,
        label=f"Afro (n={n_afro})")
ax.barh(y + bar_h/2, branca_vals, bar_h, color=COL_BRANCA,
        edgecolor='white', linewidth=0.8, zorder=3,
        label=f"Brancas (n={n_branca})")

# Value labels: "% (n)" at bar end
for yi, (v, count) in enumerate(zip(afro_vals, ct["afro"].values)):
    ax.text(v + 1.5, yi - bar_h/2, f"{v:.0f}% ({int(count)})",
            va='center', fontsize=10, fontweight='bold', color=COL_AFRO)
for yi, (v, count) in enumerate(zip(branca_vals, ct["branca"].values)):
    ax.text(v + 1.5, yi + bar_h/2, f"{v:.0f}% ({int(count)})",
            va='center', fontsize=10, fontweight='bold', color=COL_BRANCA)

# Delta annotations
for yi, (a, b) in enumerate(zip(afro_vals, branca_vals)):
    delta = a - b
    if abs(delta) < 3:
        continue
    color = COL_AFRO if delta > 0 else COL_BRANCA
    sign = "+" if delta > 0 else ""
    ax.annotate(f"Δ {sign}{delta:.0f}pp",
                xy=(max(a, b) + 12, yi),
                fontsize=9, fontweight='bold', color='white',
                va='center', ha='center',
                bbox=dict(boxstyle='round,pad=0.32',
                          facecolor=color, edgecolor='none'),
                zorder=6)

ax.set_yticks(y)
ax.set_yticklabels(benefit_order, fontsize=11)
ax.invert_yaxis()
ax.set_xlim(0, 100)
ax.set_xticks(range(0, 101, 20))
ax.set_xticklabels([f"{t}%" for t in range(0, 101, 20)], fontsize=9.5)
ax.set_xlabel("% das respondentes de Q14 dentro do grupo racial que recebem esse benefício",
              fontsize=10.5, labelpad=10)
ax.grid(axis='x', linestyle=':', linewidth=0.5, color='#dddddd', zorder=0)
ax.set_axisbelow(True)

ax.legend(loc='lower right', fontsize=10, framealpha=0.95,
          edgecolor='#cccccc', handlelength=1.4)

ax.set_title(
    "Recebimento material dos benefícios da CC — Q14 × Q3",
    fontsize=12.5, fontweight='bold', color='#1a252f',
    loc='left', pad=14
)

# ----- RIGHT PANEL: interpretive callout showing the paradox -----
axr.axis('off')

# Header
axr.text(0, 0.98, "O paradoxo:\nrecebimento ≠ reconhecimento",
         fontsize=12, fontweight='bold', color='#1a252f',
         transform=axr.transAxes, va='top')

# Line 1 — média de benefícios por pessoa
axr.text(0, 0.86,
         "Média de benefícios por respondente",
         fontsize=10, color='#4b5563',
         transform=axr.transAxes, va='top')
axr.text(0.05, 0.81,
         f"Afro     {mean_afro:.2f}",
         fontsize=11.5, fontweight='bold', color=COL_AFRO,
         transform=axr.transAxes, va='top')
axr.text(0.05, 0.76,
         f"Brancas  {mean_branca:.2f}",
         fontsize=11.5, fontweight='bold', color=COL_BRANCA,
         transform=axr.transAxes, va='top')

axr.text(0, 0.69,
         "→ Brancas recebem, em média,\n"
         "   mais benefícios por pessoa,\n"
         "   mas em Q13 afirmam MENOS\n"
         "   que a CC trouxe benefício.",
         fontsize=9.5, color='#1a252f',
         transform=axr.transAxes, va='top', style='italic')

# Divider line
axr.plot([0, 1], [0.55, 0.55], color='#dddddd', linewidth=0.6,
         transform=axr.transAxes)

# The recognition-vs-receipt paradox — global (not race)
axr.text(0, 0.52,
         "Dessas 38 trabalhadoras\n"
         "que detalham QUAIS benefícios\n"
         "recebem em Q14…",
         fontsize=10, color='#4b5563',
         transform=axr.transAxes, va='top')

# Big number 32%
axr.text(0.5, 0.30, f"{100*n_q14_disagree/n_q14_total:.0f}%",
         fontsize=32, fontweight='bold', color=COL_ACCENT,
         transform=axr.transAxes, ha='center', va='center')

axr.text(0.5, 0.16,
         f"disseram em Q13\n"
         f"que a CC NÃO lhes\n"
         f"trouxe benefício\n"
         f"({n_q14_disagree} de {n_q14_total})",
         fontsize=9.5, color='#1a252f',
         transform=axr.transAxes, ha='center', va='top', style='italic')

# Enclose the right panel in a soft box
from matplotlib.patches import Rectangle
box = Rectangle((-0.05, -0.02), 1.10, 1.02, transform=axr.transAxes,
                facecolor='#fef3c7', edgecolor='#fbbf24', linewidth=0.8,
                alpha=0.4, zorder=0)
axr.add_patch(box)

# ---------- suptitle / subtitle ----------
fig.text(0.5, 1.03,
         "O gap racial em Q13 é de reconhecimento, não de recebimento.",
         ha='center', fontsize=14, fontweight='bold', color='#1a252f')
fig.text(0.5, 0.99,
         "Q14 × raça (n=36): brancas recebem quase os mesmos benefícios da CC — "
         "e ligeiramente mais em média — mas em Q13 atribuem menos à CC (31% vs 40%).",
         ha='center', fontsize=10.3, color='#4b5563', style='italic')

# Footer note
fig.text(0.5, -0.03,
         "Universo do painel esquerdo: quem respondeu Q14 com pelo menos um "
         "benefício mapeado e tem raça declarada (n=36 · 23 afro + 13 brancas). "
         "Universo do painel direito: as 38 trabalhadoras que detalharam Q14 "
         "(inclui 2 sem raça declarada).",
         ha='center', fontsize=8.5, color=COL_MUTED, style='italic')

plt.subplots_adjust(top=0.88, bottom=0.12, left=0.10, right=0.98)
plt.savefig(OUT, dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig(OUT.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved: {OUT}")
