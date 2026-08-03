"""
analyze_q13_by_age.py
=====================

Cross Q13 (a CC trouxe benefício?) × Q1 (idade).

Universe: quem respondeu Sim ou Não em Q13 e tem idade declarada.  n = 207.

Achado central:
  Padrão em U com queda dramática entre 30-39 anos.
    18-29   40,0%  (n=5,   IC 11,8% — 76,9%)
    30-39    9,8%  (n=41,  IC  3,9% — 22,5%)   ← DIP
    40-49   37,5%  (n=64,  IC 26,7% — 49,7%)
    50-59   41,9%  (n=62,  IC 30,5% — 54,3%)
    60+     48,6%  (n=35,  IC 33,0% — 64,4%)

Testes:
  χ² (5 faixas × Sim/Não): χ² = 15,80, df = 4, p = 0,0033  ← significativo
  Fisher (30-39 vs resto): OR = 0,15, p = 0,000094         ← MUITO significativo

Leitura:
  A geração 30-39 (cohort atingida pelos primeiros anos da Reforma Trabalhista
  de 2017 e pela pandemia com carreira ainda em formação) NÃO reconhece
  benefício da CC — enquanto as trabalhadoras 40+ (com trajetória pré-reforma
  consolidada) reconhecem em 40-49% dos casos.  Achado se combina com Q7
  (carreira longa) e sugere que a materialização subjetiva do benefício da CC
  depende de acumulação de tempo E de exposição a um ciclo institucional
  completo (piso, reajuste, cesta, cartões).

Output:
  chapter/survey_a_analysis/Q13_by_age.png  (+ .pdf)
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

COL_ACCENT_DIP = '#a16207'    # ochre — highlight the 30-39 dip
COL_BAR        = '#1f2937'    # near-black slate for the "normal" bars
COL_MUTED      = '#94a3b8'

ROOT = Path(__file__).parent.parent
SRC = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT = ROOT / "chapter" / "survey_a_analysis" / "Q13_by_age.png"

df = pd.read_excel(SRC)

def col(prefix):
    for c in df.columns:
        if c.startswith(prefix):
            return c
    raise KeyError(prefix)

q1  = col('1 -')
q13 = col('13 -')

def wilson(k, n, z=1.96):
    if n == 0:
        return 0, 0, 0
    p = k/n
    c = (p + z*z/(2*n))/(1+z*z/n)
    h = z*sqrt(p*(1-p)/n + z*z/(4*n*n))/(1+z*z/n)
    return 100*p, 100*(c-h), 100*(c+h)

# ---------- data ----------
age_order = ['Entre 18 e 29 anos','Entre 30 e 39 anos','Entre 40 e 49 anos',
             'Entre 50 e 59 anos','Acima de 60 anos']
short_labels = ['18-29 anos','30-39 anos','40-49 anos','50-59 anos','60+ anos']

d = df.dropna(subset=[q13, q1])
d = d[d[q13].isin(['Sim','Não'])]

rows = []
for cat, short in zip(age_order, short_labels):
    sub = d[d[q1] == cat]
    n = len(sub)
    sim = int((sub[q13] == 'Sim').sum())
    pct, lo, hi = wilson(sim, n)
    rows.append(dict(cat=short, n=n, sim=sim, pct=pct, lo=lo, hi=hi))

# χ² across all ages
tab = [[r['sim'], r['n']-r['sim']] for r in rows]
if stats is not None:
    chi2, p_chi2, dof, _ = stats.chi2_contingency(tab)
    # Fisher for 30-39 vs rest
    d30 = d[d[q1] == 'Entre 30 e 39 anos']
    d_rest = d[d[q1] != 'Entre 30 e 39 anos']
    tab2 = [[int((d30[q13]=='Sim').sum()), int((d30[q13]=='Não').sum())],
            [int((d_rest[q13]=='Sim').sum()), int((d_rest[q13]=='Não').sum())]]
    odds, p_fisher = stats.fisher_exact(tab2)
else:
    chi2 = p_chi2 = odds = p_fisher = None

# Global baseline
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

# Color: highlight 30-39 in ochre, others in slate.  The <30 bar is muted (small n).
def bar_color(r):
    if r['cat'] == '30-39 anos':
        return COL_ACCENT_DIP
    if r['cat'] == '18-29 anos':
        return COL_MUTED    # muted — n=5 too small
    return COL_BAR

colors = [bar_color(r) for r in rows]

ax.bar(x, vals, bar_w, color=colors, edgecolor='white', linewidth=0.8,
       zorder=3)

# Wilson CI error bars
ax.errorbar(x, vals, yerr=[lows, highs],
            fmt='none', ecolor='#1a252f', elinewidth=1.5,
            capsize=6, capthick=1.5, zorder=5)

# Value labels above bars
for xi, r in enumerate(rows):
    ax.text(xi, r['hi'] + 3, f"{r['pct']:.1f}%",
            ha='center', va='bottom',
            fontsize=13, fontweight='bold',
            color=colors[xi], zorder=6)
    # n= below x label
    ax.text(xi, -6, f"n={r['n']}", ha='center', va='top',
            fontsize=9, color='#6b7280')
    # CI text (small, under n=)
    ax.text(xi, -11, f"IC 95%: [{r['lo']:.1f}%, {r['hi']:.1f}%]",
            ha='center', va='top', fontsize=7.8, color=COL_MUTED)

# Baseline reference line — label placed at TOP-RIGHT of plot area
# so it doesn't sit inside/over the 50-59 or 60+ bars.
ax.axhline(baseline_pct, color='#94a3b8', linestyle=':', linewidth=1.2,
           zorder=1, alpha=0.9)
ax.text(0.995, 0.94,
        f"média global = {baseline_pct:.0f}% Sim  (n={n_total})",
        transform=ax.transAxes,
        fontsize=9, color='#4b5563', style='italic',
        ha='right', va='top',
        bbox=dict(boxstyle='round,pad=0.28', facecolor='white',
                  edgecolor='#d1d5db', linewidth=0.5))

# X ticks
ax.set_xticks(x)
ax.set_xticklabels([r['cat'] for r in rows], fontsize=10.5)
ax.tick_params(axis='x', length=0, pad=6)

# Y axis
ax.set_ylim(-14, 82)
ax.set_yticks(range(0, 81, 20))
ax.set_yticklabels([f"{t}%" for t in range(0, 81, 20)], fontsize=9.5)
ax.set_ylabel('% que responderam SIM em Q13\n(“a CC trouxe benefício para você?”)',
              fontsize=10.5, labelpad=10)
ax.grid(axis='y', linestyle=':', linewidth=0.5, color='#dddddd', zorder=0)
ax.set_axisbelow(True)

# Highlight the DIP with an annotation arrow to the 30-39 bar.
# Positioned in the top-left area (over the 18-29 muted bar) so it doesn't
# cover the value labels of the 40-49 or 50-59 bars.
dip_xi = 1
dip_top = rows[dip_xi]['hi']
ax.annotate(
    "A geração 30-39 não\n"
    "reconhece benefício da CC\n"
    "(10% vs 42% nas demais faixas)",
    xy=(dip_xi - 0.20, dip_top + 4),
    xytext=(-0.35, 60),
    fontsize=10, color=COL_ACCENT_DIP, fontweight='bold',
    ha='left', va='center',
    arrowprops=dict(arrowstyle='->', color=COL_ACCENT_DIP,
                    lw=1.3, connectionstyle="arc3,rad=0.25"),
    bbox=dict(boxstyle='round,pad=0.42', facecolor='#fef3c7',
              edgecolor=COL_ACCENT_DIP, linewidth=0.8, alpha=0.98),
    zorder=8,
)

# Titles + subtitles
ax.text(0, 1.18,
        'Q13 × Q1 — Reconhecimento do benefício da CC por faixa etária',
        transform=ax.transAxes, fontsize=13, fontweight='bold', color='#1a252f')
ax.text(0, 1.10,
        '“A Convenção Coletiva já trouxe algum benefício para você?”',
        transform=ax.transAxes, fontsize=10.5, color='#1a252f', style='italic')
ax.text(0, 1.02,
        f"STDMSP Pesquisa A (2024) · n = {n_total} · barras = IC 95% Wilson · "
        f"faixa 18-29 em cinza porque n=5 (não interpretável)",
        transform=ax.transAxes, fontsize=9.3, color='#6b7280', style='italic')

plt.subplots_adjust(top=0.80, bottom=0.14, left=0.11, right=0.97)
plt.savefig(OUT, dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig(OUT.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved: {OUT}")
