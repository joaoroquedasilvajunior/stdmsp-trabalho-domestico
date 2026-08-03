"""
analyze_q13_by_race.py
======================

Standalone cross of Q13 (a CC trouxe benefício?) × Q3 (raça).
The BASELINE chart on which the decomposition (Q13_gap_decomposition.png)
and the recognition-vs-receipt reading (Q14_by_race.png) rest.

Honest reporting: n=125 afro / n=81 brancas.  Point estimates show
Sim% = 40,0% (afro) vs 30,9% (brancas), Δ = +9,1pp.
Fisher exact test: OR = 1,49, p = 0,236.
Wilson 95% CI: afro [31,8%, 48,8%] · brancas [21,9%, 41,6%] — INTERVALS OVERLAP.

Reading: point estimate consistent with a real racial gap in institutional
recognition of the CC, but this survey alone does not reach conventional
statistical significance.  The signal must be triangulated with the
within-strata pattern (Q13_gap_decomposition), where individual Δ pills
have their own n's to check.

Output:
  chapter/survey_a_analysis/Q13_by_race.png  (+ .pdf)
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

COL_AFRO   = '#b91c1c'
COL_BRANCA = '#475569'
COL_NA     = '#e5e7eb'
COL_NAO    = '#9ca3af'
COL_MUTED  = '#94a3b8'

ROOT = Path(__file__).parent.parent
SRC = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT = ROOT / "chapter" / "survey_a_analysis" / "Q13_by_race.png"

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
df['race'] = df[q3].apply(race)

# ---------- data ----------
def bucket(sub):
    total = len(sub)
    sim = int((sub[q13] == 'Sim').sum())
    nao = int((sub[q13] == 'Não').sum())
    na  = int(sub[q13].isna().sum())
    n_ans = sim + nao
    return dict(total=total, sim=sim, nao=nao, na=na, n_ans=n_ans)

afro_all   = bucket(df[df['race'] == 'afro'])
branca_all = bucket(df[df['race'] == 'branca'])

# Wilson 95% CI
def wilson(k, n, z=1.96):
    p = k/n
    center = (p + z*z/(2*n))/(1+z*z/n)
    half = z*sqrt(p*(1-p)/n + z*z/(4*n*n))/(1+z*z/n)
    return 100*center, 100*half, 100*(center-half), 100*(center+half)

afro_p_center, afro_half, afro_lo, afro_hi = wilson(afro_all['sim'], afro_all['n_ans'])
branca_p_center, branca_half, branca_lo, branca_hi = wilson(branca_all['sim'], branca_all['n_ans'])
afro_point = 100 * afro_all['sim']/afro_all['n_ans']
branca_point = 100 * branca_all['sim']/branca_all['n_ans']
delta_pp = afro_point - branca_point

# Significance test
if stats is not None:
    tab = [[afro_all['sim'], afro_all['nao']],
           [branca_all['sim'], branca_all['nao']]]
    chi2, p_chi2, _, _ = stats.chi2_contingency(tab)
    odds, p_fisher = stats.fisher_exact(tab)
else:
    chi2, p_chi2, odds, p_fisher = None, None, None, None

# ---------- figure ----------
fig = plt.figure(figsize=(13.8, 7.4))
gs  = fig.add_gridspec(1, 2, width_ratios=[2.4, 1.6], wspace=0.30)
ax  = fig.add_subplot(gs[0])
axr = fig.add_subplot(gs[1])

# ================== LEFT: Sim% by race with Wilson 95% CI ==================
y_positions = np.arange(2)
bar_h = 0.44

vals = [afro_point, branca_point]
lows = [afro_point - afro_lo, branca_point - branca_lo]
highs = [afro_hi - afro_point, branca_hi - branca_point]

ax.barh(y_positions, vals, bar_h,
        color=[COL_AFRO, COL_BRANCA],
        edgecolor='white', linewidth=0.8, zorder=3)

# Error bars (Wilson CI)
ax.errorbar(vals, y_positions,
            xerr=[lows, highs],
            fmt='none', ecolor='#1a252f', elinewidth=1.5,
            capsize=6, capthick=1.5, zorder=5)

# Value labels
for i, (v, lo, hi) in enumerate(zip(vals,
                                    [afro_lo, branca_lo],
                                    [afro_hi, branca_hi])):
    color = COL_AFRO if i == 0 else COL_BRANCA
    ax.text(v + 2.5, i - 0.02, f"{v:.1f}%",
            va='center', fontsize=15, fontweight='bold', color=color,
            zorder=6)
    ax.text(v + 2.5, i + 0.20,
            f"IC 95%: [{lo:.1f}%, {hi:.1f}%]",
            va='center', fontsize=8.8, color='#4b5563')

# Y ticks with race + n
labels = [
    f"Afro-descendentes\n(pardas + pretas)\nn={afro_all['n_ans']} respondentes",
    f"Brancas\nn={branca_all['n_ans']} respondentes",
]
ax.set_yticks(y_positions)
ax.set_yticklabels(labels, fontsize=10.5)
ax.invert_yaxis()

# X axis
ax.set_xlim(0, 68)
ax.set_xticks(range(0, 66, 10))
ax.set_xticklabels([f"{t}%" for t in range(0, 66, 10)], fontsize=9.5)
ax.set_xlabel("% que responderam SIM em Q13 (dentre quem respondeu)",
              fontsize=10.5, labelpad=10)
ax.grid(axis='x', linestyle=':', linewidth=0.5, color='#dddddd', zorder=0)
ax.set_axisbelow(True)

ax.set_title(
    'Q13 — “A Convenção Coletiva já trouxe algum benefício para você?”',
    fontsize=12, fontweight='bold', color='#1a252f',
    loc='left', pad=14
)

# Gap annotation between bars
gap_x = min(afro_point, branca_point) - 3
ax.annotate('', xy=(afro_point, 0.05), xytext=(branca_point, 0.95),
            arrowprops=dict(arrowstyle='-', linewidth=0.8,
                            linestyle='--', color='#6b7280'),
            zorder=4)
ax.text(min(afro_point, branca_point) + abs(delta_pp)/2, 0.5,
        f'Δ = +{delta_pp:.1f}pp',
        ha='center', va='center', fontsize=11.5, fontweight='bold',
        color='white',
        bbox=dict(boxstyle='round,pad=0.42',
                  facecolor='#a16207', edgecolor='none'),
        zorder=7)

# ================== RIGHT: Full breakdown + significance ==================
axr.axis('off')

# Header
axr.text(0, 1.00,
         "Distribuição completa\nna sub-amostra",
         fontsize=12, fontweight='bold', color='#1a252f',
         transform=axr.transAxes, va='top')

# Stacked bar chart-lite
bars_y = [0.79, 0.55]
race_labels = ['Afro', 'Brancas']
buckets = [afro_all, branca_all]
colors = [COL_AFRO, COL_BRANCA]

for yi, (r_label, bkt, base_col) in enumerate(zip(race_labels, buckets, colors)):
    y = bars_y[yi]
    total = bkt['total']
    sim = bkt['sim']
    nao = bkt['nao']
    na  = bkt['na']
    # Percentages of total subamostra
    p_sim = 100*sim/total
    p_nao = 100*nao/total
    p_na  = 100*na/total

    axr.text(0.02, y + 0.075, f"{r_label} (n={total})",
             fontsize=10.5, fontweight='bold', color=base_col,
             transform=axr.transAxes)

    # Stacked bar (normalized to 100% of subamostra)
    bar_left = 0.02
    bar_width = 0.90
    x0 = bar_left
    for share, seg_color, seg_label in [
        (p_sim/100, base_col, f"Sim {p_sim:.0f}%"),
        (p_nao/100, COL_NAO,  f"Não {p_nao:.0f}%"),
        (p_na/100,  COL_NA,   f"NA {p_na:.0f}%"),
    ]:
        axr.add_patch(plt.Rectangle(
            (x0, y - 0.02), bar_width * share, 0.05,
            facecolor=seg_color, edgecolor='white',
            linewidth=0.7, transform=axr.transAxes))
        # In-bar label if segment ≥ 12% width
        if share >= 0.12:
            text_color = 'white' if seg_color != COL_NA else '#4b5563'
            axr.text(x0 + bar_width*share/2, y + 0.005,
                     seg_label, fontsize=8.5,
                     color=text_color, ha='center', va='center',
                     fontweight='bold',
                     transform=axr.transAxes)
        x0 += bar_width * share

# Divider
axr.plot([0, 1], [0.44, 0.44], color='#dddddd', linewidth=0.6,
         transform=axr.transAxes)

# Statistical significance section
axr.text(0, 0.40,
         "Diferença é estatisticamente significativa?",
         fontsize=11, fontweight='bold', color='#1a252f',
         transform=axr.transAxes, va='top')

test_lines = [
    ("Fisher exact", f"OR = {odds:.2f}", f"p = {p_fisher:.3f}"),
    ("χ² Pearson",   f"χ² = {chi2:.2f}",  f"p = {p_chi2:.3f}"),
]
y_line = 0.32
for name, stat_txt, p_txt in test_lines:
    axr.text(0.02, y_line, name, fontsize=10, color='#4b5563',
             transform=axr.transAxes, va='top')
    axr.text(0.35, y_line, stat_txt, fontsize=10, color='#1a252f',
             transform=axr.transAxes, va='top')
    axr.text(0.70, y_line, p_txt, fontsize=10, color='#1a252f',
             transform=axr.transAxes, va='top', fontweight='bold')
    y_line -= 0.05

# Verdict
sig = "NÃO significativo (p > 0,05)"
verdict_color = "#a16207"
axr.text(0, 0.17,
         "Verdict:",
         fontsize=10, color='#4b5563',
         transform=axr.transAxes, va='top')
axr.text(0.15, 0.17,
         sig,
         fontsize=10.5, fontweight='bold', color=verdict_color,
         transform=axr.transAxes, va='top')

axr.text(0, 0.09,
         "Os IC 95% se sobrepõem — a amostra é\n"
         "compatível com um gap racial real de +9pp,\n"
         "mas não o confirma isoladamente.  Ver\n"
         "decomposição por tempo/salário/conhecimento.",
         fontsize=9, color='#1a252f', style='italic',
         transform=axr.transAxes, va='top')

# Box around right panel
from matplotlib.patches import Rectangle
box = Rectangle((-0.04, -0.03), 1.08, 1.06, transform=axr.transAxes,
                facecolor='#fef3c7', edgecolor='#fbbf24', linewidth=0.8,
                alpha=0.35, zorder=0)
axr.add_patch(box)

# ---------- suptitle ----------
fig.text(0.5, 1.02,
         "Q13 × Q3 — Reconhecimento do benefício da CC por raça",
         ha='center', fontsize=14, fontweight='bold', color='#1a252f')
fig.text(0.5, 0.98,
         "STDMSP Pesquisa A (2024) · autoavaliação subjetiva · sub-amostra afro n=140 · brancas n=93",
         ha='center', fontsize=10.3, color='#4b5563', style='italic')

fig.text(0.5, -0.03,
         "Denominador do gráfico da esquerda: quem respondeu Sim ou Não.  "
         "As NAs (afro 15/140 = 10,7% · brancas 12/93 = 12,9%) estão "
         "aproximadamente balanceadas entre grupos — o gap não pode ser explicado por "
         "diferença de taxa de resposta.",
         ha='center', fontsize=8.6, color=COL_MUTED, style='italic')

plt.subplots_adjust(top=0.87, bottom=0.12, left=0.14, right=0.98)
plt.savefig(OUT, dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig(OUT.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved: {OUT}")
print(f"Baseline: afro {afro_point:.1f}% [{afro_lo:.1f}%, {afro_hi:.1f}%]  "
      f"vs brancas {branca_point:.1f}% [{branca_lo:.1f}%, {branca_hi:.1f}%]")
print(f"Δ = +{delta_pp:.1f}pp  ·  Fisher p={p_fisher:.3f}  ·  χ² p={p_chi2:.3f}")

# ============================================================
# CLEAN VERSION — same chart, no right-side board.
# All the signal (Δ pill, IC 95%, sample sizes, significance note)
# is folded into the bar-chart itself.
# ============================================================
OUT_CLEAN = ROOT / "chapter" / "survey_a_analysis" / "Q13_by_race_clean.png"

fig, ax = plt.subplots(figsize=(10.8, 5.8))

y_positions = np.arange(2)
bar_h = 0.44
vals = [afro_point, branca_point]
lows = [afro_point - afro_lo, branca_point - branca_lo]
highs = [afro_hi - afro_point, branca_hi - branca_point]

ax.barh(y_positions, vals, bar_h,
        color=[COL_AFRO, COL_BRANCA],
        edgecolor='white', linewidth=0.8, zorder=3)

# Wilson CI error bars
ax.errorbar(vals, y_positions,
            xerr=[lows, highs],
            fmt='none', ecolor='#1a252f', elinewidth=1.5,
            capsize=6, capthick=1.5, zorder=5)

# Value labels — big % + IC 95% ABOVE the value (offset -0.22)
# so they never collide with the significance note in the figure footer.
for i, (v, lo, hi) in enumerate(zip(vals,
                                    [afro_lo, branca_lo],
                                    [afro_hi, branca_hi])):
    color = COL_AFRO if i == 0 else COL_BRANCA
    ax.text(v + 2.5, i - 0.02, f"{v:.1f}%",
            va='center', fontsize=15, fontweight='bold', color=color,
            zorder=6)
    ax.text(v + 2.5, i - 0.22,
            f"IC 95%: [{lo:.1f}%, {hi:.1f}%]",
            va='center', fontsize=9, color='#4b5563')

# Y ticks with race + n
labels = [
    f"Afro-descendentes\n(pardas + pretas)\nn={afro_all['n_ans']} respondentes",
    f"Brancas\nn={branca_all['n_ans']} respondentes",
]
ax.set_yticks(y_positions)
ax.set_yticklabels(labels, fontsize=10.5)
ax.invert_yaxis()

# X axis
ax.set_xlim(0, 68)
ax.set_xticks(range(0, 66, 10))
ax.set_xticklabels([f"{t}%" for t in range(0, 66, 10)], fontsize=9.5)
ax.set_xlabel("% que responderam SIM em Q13 (dentre quem respondeu)",
              fontsize=10.5, labelpad=10)
ax.grid(axis='x', linestyle=':', linewidth=0.5, color='#dddddd', zorder=0)
ax.set_axisbelow(True)

# Gap dashed line + Δ pill in the middle
ax.annotate('', xy=(afro_point, 0.05), xytext=(branca_point, 0.95),
            arrowprops=dict(arrowstyle='-', linewidth=0.8,
                            linestyle='--', color='#6b7280'),
            zorder=4)
ax.text(min(afro_point, branca_point) + abs(delta_pp)/2, 0.5,
        f'Δ = +{delta_pp:.1f}pp',
        ha='center', va='center', fontsize=12, fontweight='bold',
        color='white',
        bbox=dict(boxstyle='round,pad=0.42',
                  facecolor='#a16207', edgecolor='none'),
        zorder=7)

# Title + subtitle stacked above
ax.text(0, 1.22,
        'Q13 × Q3 — Reconhecimento do benefício da CC por raça',
        transform=ax.transAxes, fontsize=13, fontweight='bold', color='#1a252f')
ax.text(0, 1.14,
        '“A Convenção Coletiva já trouxe algum benefício para você?”',
        transform=ax.transAxes, fontsize=10.5, color='#1a252f', style='italic')
ax.text(0, 1.06,
        'STDMSP Pesquisa A (2024) · sub-amostra afro n=140 · brancas n=93 · '
        'barras de erro = IC 95% Wilson',
        transform=ax.transAxes, fontsize=9.3, color='#6b7280', style='italic')

# Significance note OUTSIDE the axes (below the x-label) — no overlap risk.
fig.text(0.5, -0.02,
         f"Fisher exact: OR = {odds:.2f}, p = {p_fisher:.3f}  ·  "
         f"gap não é estatisticamente significativo ao nível 0,05",
         ha='center', fontsize=9.5, color='#a16207', style='italic',
         bbox=dict(boxstyle='round,pad=0.42', facecolor='#fef3c7',
                   edgecolor='#fbbf24', linewidth=0.6, alpha=0.9))

plt.subplots_adjust(top=0.78, bottom=0.20, left=0.20, right=0.97)
plt.savefig(OUT_CLEAN, dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig(OUT_CLEAN.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved (clean): {OUT_CLEAN}")
