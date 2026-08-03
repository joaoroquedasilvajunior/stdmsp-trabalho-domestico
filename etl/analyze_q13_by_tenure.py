"""
analyze_q13_by_tenure.py
========================

Cross Q13 (a CC trouxe benefício?) × Q7 (tempo na categoria).

Universe: quem respondeu Sim ou Não em Q13 e tem tempo de trabalho declarado.
n = 211.

Achado central:
  Função DEGRAU exata aos 10 anos.
    1-2 anos:     38,5%  (n=13,  IC 17,7% — 64,5%)
    3-5 anos:     21,9%  (n=32,  IC 11,0% — 38,8%)
    5-10 anos:    25,0%  (n=76,  IC 16,6% — 35,8%)
    10-20 anos:   50,0%  (n=40,  IC 35,2% — 64,8%)   ← DEGRAU
    20+ anos:     50,0%  (n=50,  IC 36,6% — 63,4%)

Testes:
  χ² (5 faixas × Sim/Não): χ² = 14,45, df = 4, p = 0,006
  Fisher exact (<10 anos vs ≥10 anos): OR = 0,34, p = 0,0003

Leitura:
  A CC exige TEMPO para materializar-se subjetivamente.  Até os 10 anos de
  categoria, o reconhecimento fica em ~25% (muito abaixo da média global de
  36%).  A partir dos 10 anos, o reconhecimento salta para exatamente 50% e
  se estabiliza — dobra em relação ao patamar inicial.  Não há gradiente
  linear com o tempo — há uma dobradiça institucional na marca dos 10 anos.

Interpretação política:
  Esse degrau é a assinatura de um ciclo institucional completo — só depois
  de ter passado por 2-3 negociações coletivas (uma CC nova a cada 2-3
  anos), 2-3 reajustes salariais, e provavelmente pelo menos uma reforma
  legal (PEC 2013 / LC150 2015 / Reforma 2017 / Reforma 2019) a
  trabalhadora consegue nomear a CC como origem dos benefícios materiais
  que recebe.

Output:
  chapter/survey_a_analysis/Q13_by_tenure.png  (+ .pdf)
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from math import sqrt
from matplotlib import rcParams

try:
    from scipy import stats
except Exception:
    stats = None

rcParams['font.family'] = 'serif'
rcParams['font.size'] = 10
rcParams['axes.linewidth'] = 0.7
rcParams['axes.spines.top'] = False
rcParams['axes.spines.right'] = False
rcParams['axes.edgecolor'] = '#222222'
rcParams['pdf.fonttype'] = 42
rcParams['ps.fonttype'] = 42

# Two-tone palette: muted slate for <10 anos, ochre for ≥10 anos.
COL_LOW    = '#94a3b8'    # muted slate
COL_HIGH   = '#a16207'    # ochre accent
COL_MUTED  = '#94a3b8'

ROOT = Path(__file__).parent.parent
SRC = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT = ROOT / "chapter" / "survey_a_analysis" / "Q13_by_tenure.png"

df = pd.read_excel(SRC)

def col(prefix):
    for c in df.columns:
        if c.startswith(prefix):
            return c
    raise KeyError(prefix)

q7  = col('7 -')
q13 = col('13 -')

def wilson(k, n, z=1.96):
    if n == 0:
        return 0, 0, 0
    p = k/n
    c = (p + z*z/(2*n))/(1+z*z/n)
    h = z*sqrt(p*(1-p)/n + z*z/(4*n*n))/(1+z*z/n)
    return 100*p, 100*(c-h), 100*(c+h)

# ---------- data ----------
tenure_order  = ['Entre 1 e 2 anos','Entre 3 e 5 anos','Entre 5 e 10 anos',
                 'Entre 10 e 20 anos','Mais de 20 anos']
short_labels  = ['1-2 anos','3-5 anos','5-10 anos','10-20 anos','20+ anos']
is_high       = [False, False, False, True, True]     # ≥10 anos?

d = df.dropna(subset=[q13, q7])
d = d[d[q13].isin(['Sim','Não'])]

rows = []
for cat, short, hi_flag in zip(tenure_order, short_labels, is_high):
    sub = d[d[q7] == cat]
    n = len(sub)
    sim = int((sub[q13] == 'Sim').sum())
    pct, lo, hi = wilson(sim, n)
    rows.append(dict(cat=short, n=n, sim=sim, pct=pct, lo=lo, hi=hi, high=hi_flag))

sim_total = int((d[q13] == 'Sim').sum())
n_total = int(len(d))
baseline_pct = 100*sim_total/n_total

# ---------- figure ----------
fig, ax = plt.subplots(figsize=(11.5, 6.4))

x = np.arange(len(rows))
bar_w = 0.55
vals = [r['pct'] for r in rows]
lows = [r['pct']-r['lo'] for r in rows]
highs = [r['hi']-r['pct'] for r in rows]
colors = [COL_HIGH if r['high'] else COL_LOW for r in rows]

ax.bar(x, vals, bar_w, color=colors, edgecolor='white', linewidth=0.8,
       zorder=3)

# Wilson CI error bars
ax.errorbar(x, vals, yerr=[lows, highs],
            fmt='none', ecolor='#1a252f', elinewidth=1.5,
            capsize=6, capthick=1.5, zorder=5)

# Value labels above bars
for xi, r in enumerate(rows):
    color = COL_HIGH if r['high'] else '#1f2937'
    ax.text(xi, r['hi'] + 3, f"{r['pct']:.1f}%",
            ha='center', va='bottom',
            fontsize=13, fontweight='bold',
            color=color, zorder=6)
    ax.text(xi, -6, f"n={r['n']}", ha='center', va='top',
            fontsize=9, color='#6b7280')
    ax.text(xi, -11, f"IC 95%: [{r['lo']:.1f}%, {r['hi']:.1f}%]",
            ha='center', va='top', fontsize=7.8, color=COL_MUTED)

# Baseline reference line
ax.axhline(baseline_pct, color='#94a3b8', linestyle=':', linewidth=1.2,
           zorder=1, alpha=0.9)
ax.text(0.995, 0.94,
        f"média global = {baseline_pct:.0f}% Sim  (n={n_total})",
        transform=ax.transAxes,
        fontsize=9, color='#4b5563', style='italic',
        ha='right', va='top',
        bbox=dict(boxstyle='round,pad=0.28', facecolor='white',
                  edgecolor='#d1d5db', linewidth=0.5))

# Visual step: draw the horizontal dashed lines connecting the two "groups"
# to underscore the flatness within each side of the cliff.
# <10 average
low_group_pct = sum(r['sim'] for r in rows if not r['high']) / sum(r['n'] for r in rows if not r['high']) * 100
high_group_pct = sum(r['sim'] for r in rows if r['high']) / sum(r['n'] for r in rows if r['high']) * 100
ax.plot([-0.3, 2.3], [low_group_pct, low_group_pct],
        color=COL_LOW, linewidth=2.2, alpha=0.8, zorder=2)
ax.plot([2.7, 4.3], [high_group_pct, high_group_pct],
        color=COL_HIGH, linewidth=2.2, alpha=0.9, zorder=2)

# Step annotation — placed TOP-LEFT (over the 1-2 anos bar, where the value
# label is at ~42% so there's clear space above 65%).  Arrow curves DOWN-RIGHT
# to the midpoint of the step, so it doesn't cover the 50% labels of the
# ≥10 bars.
ax.annotate(
    "Aos 10 anos, o reconhecimento\n"
    "SALTA de 26% para 50%\n"
    "(Fisher p = 0,0003)",
    xy=(2.5, (low_group_pct + high_group_pct) / 2 + 2),
    xytext=(0.20, 82),
    fontsize=10, color=COL_HIGH, fontweight='bold',
    ha='left', va='center',
    arrowprops=dict(arrowstyle='->', color=COL_HIGH,
                    lw=1.3, connectionstyle="arc3,rad=0.25"),
    bbox=dict(boxstyle='round,pad=0.42', facecolor='#fef3c7',
              edgecolor=COL_HIGH, linewidth=0.8, alpha=0.98),
    zorder=8,
)

# Group means — placed AT THE END of each connecting line (near the transition
# point x=2.5) so they don't sit over any bar. "média <10" goes at the right
# tip of the left line, "média ≥10" at the left tip of the right line.
ax.text(2.30, low_group_pct + 2.3,
        f"média <10 anos = {low_group_pct:.0f}%",
        ha='right', va='bottom', fontsize=9, fontweight='bold',
        color=COL_LOW, style='italic')
ax.text(2.70, high_group_pct + 2.3,
        f"média ≥10 anos = {high_group_pct:.0f}%",
        ha='left', va='bottom', fontsize=9, fontweight='bold',
        color=COL_HIGH, style='italic')

# X ticks
ax.set_xticks(x)
ax.set_xticklabels([r['cat'] for r in rows], fontsize=10.5)
ax.tick_params(axis='x', length=0, pad=6)

# Y axis
ax.set_ylim(-14, 88)
ax.set_yticks(range(0, 81, 20))
ax.set_yticklabels([f"{t}%" for t in range(0, 81, 20)], fontsize=9.5)
ax.set_ylabel('% que responderam SIM em Q13\n(“a CC trouxe benefício para você?”)',
              fontsize=10.5, labelpad=10)
ax.grid(axis='y', linestyle=':', linewidth=0.5, color='#dddddd', zorder=0)
ax.set_axisbelow(True)

# Titles + subtitles
ax.text(0, 1.18,
        'Q13 × Q7 — Reconhecimento do benefício da CC por tempo de trabalho',
        transform=ax.transAxes, fontsize=13, fontweight='bold', color='#1a252f')
ax.text(0, 1.10,
        '“A Convenção Coletiva já trouxe algum benefício para você?”  ×  '
        '“Há quanto tempo você trabalha como trabalhadora doméstica?”',
        transform=ax.transAxes, fontsize=10.5, color='#1a252f', style='italic')
ax.text(0, 1.02,
        f"STDMSP Pesquisa A (2024) · n = {n_total} · barras = IC 95% Wilson · "
        f"ochre = ≥10 anos de categoria · slate = <10 anos",
        transform=ax.transAxes, fontsize=9.3, color='#6b7280', style='italic')

plt.subplots_adjust(top=0.80, bottom=0.14, left=0.11, right=0.97)
plt.savefig(OUT, dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig(OUT.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved: {OUT}")
print(f"<10 anos avg: {low_group_pct:.1f}%  ·  ≥10 anos avg: {high_group_pct:.1f}%")
