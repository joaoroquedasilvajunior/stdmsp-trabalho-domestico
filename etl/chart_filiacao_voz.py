"""
chart_filiacao_voz.py — A substituição voz↔fé por filiação sindical
====================================================================

Gráfico-âncora do achado do capítulo: entre as filiadas ao sindicato, a VOZ é
o registro de resistência dominante; entre as não-filiadas, é a ESPIRITUALIDADE.
As duas células são imagens espelhadas — assinatura de uma substituição
(Hirschman: o sindicato converte enfrentamento privado/transcendente em voz
coletiva).

Dados = distribuição do registro DOMINANTE por filiação (agregados, não-sensíveis),
produzidos por analyze_resistance_by_demographics.py (Pesquisa B, n=231 com
filiação declarada). Testes de intensidade (Mann-Whitney, row-centered):
  Voz  Δ=+0,09  p=0,002   ·   Espiritualidade  Δ=−0,06  p=0,037

Saída: chapter/survey_b_resistance/filiacao_voz_substitution.png (+ .pdf)
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams

rcParams['font.family'] = 'serif'
rcParams['font.size'] = 10
rcParams['axes.linewidth'] = 0.7
rcParams['axes.spines.top'] = False
rcParams['axes.spines.right'] = False
rcParams['axes.edgecolor'] = '#222222'
rcParams['pdf.fonttype'] = 42
rcParams['ps.fonttype'] = 42

COL_FIL = '#b91c1c'     # accent red — filiadas
COL_NAO = '#475569'     # slate — não filiadas
COL_HI = '#a16207'      # ochre — destaque das células significativas

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "chapter" / "survey_b_resistance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "filiacao_voz_substitution.png"

# Registro dominante (%) por filiação — colado da saída real
REGS = ["Saída", "Voz", "Evitação", "Lealdade", "Espiritualidade", "Solidariedade"]
FIL = {"Saída": 12, "Voz": 31, "Evitação": 17, "Lealdade": 12, "Espiritualidade": 11, "Solidariedade": 17}
NAO = {"Saída": 13, "Voz": 12, "Evitação": 15, "Lealdade": 19, "Espiritualidade": 26, "Solidariedade": 15}
N_FIL, N_NAO = 72, 159
# células com diferença de intensidade significativa (Mann-Whitney, row-centered)
SIG = {"Voz": "p=0,002", "Espiritualidade": "p=0,037"}

# ordena para contar a história: Voz no topo, Espiritualidade logo abaixo,
# depois o resto por magnitude do gap
order = ["Voz", "Espiritualidade", "Lealdade", "Evitação", "Solidariedade", "Saída"]

fig, ax = plt.subplots(figsize=(10.2, 6.2))
y = np.arange(len(order))
bar_h = 0.38

fil_vals = [FIL[r] for r in order]
nao_vals = [NAO[r] for r in order]

b1 = ax.barh(y + bar_h/2, fil_vals, bar_h, color=COL_FIL,
             edgecolor='white', linewidth=0.8, zorder=3,
             label=f'Filiadas ao sindicato (n={N_FIL})')
b2 = ax.barh(y - bar_h/2, nao_vals, bar_h, color=COL_NAO,
             edgecolor='white', linewidth=0.8, zorder=3,
             label=f'Não filiadas (n={N_NAO})')

# rótulos de valor
for yi, r in enumerate(order):
    ax.text(FIL[r] + 0.7, yi + bar_h/2, f"{FIL[r]}%", va='center',
            fontsize=10.5, fontweight='bold', color=COL_FIL)
    ax.text(NAO[r] + 0.7, yi - bar_h/2, f"{NAO[r]}%", va='center',
            fontsize=10.5, fontweight='bold', color=COL_NAO)
    # pílula de significância nas células espelhadas
    if r in SIG:
        gap = FIL[r] - NAO[r]
        ax.annotate(f"Δ {gap:+d}pp · {SIG[r]}",
                    xy=(max(FIL[r], NAO[r]) + 6.5, yi),
                    fontsize=9, fontweight='bold', color='white',
                    va='center', ha='center',
                    bbox=dict(boxstyle='round,pad=0.34', facecolor=COL_HI,
                              edgecolor='none'), zorder=6)

ax.set_yticks(y)
ax.set_yticklabels(order, fontsize=12)
ax.invert_yaxis()
ax.set_xlim(0, 42)
ax.set_xticks(range(0, 41, 10))
ax.set_xticklabels([f"{t}%" for t in range(0, 41, 10)], fontsize=9.5)
ax.set_xlabel("% das respondentes com este registro como dominante",
              fontsize=10.5, labelpad=10)
ax.grid(axis='x', linestyle=':', linewidth=0.5, color='#dddddd', zorder=0)
ax.set_axisbelow(True)
ax.legend(loc='lower right', fontsize=10.5, framealpha=0.96,
          edgecolor='#cccccc', handlelength=1.4)

# título + subtítulo
ax.text(0, 1.16, "O sindicato converte fé em voz",
        transform=ax.transAxes, fontsize=15, fontweight='bold', color='#1a252f')
ax.text(0, 1.09,
        "Registro de resistência dominante, por filiação sindical — Pesquisa B (STDMSP)",
        transform=ax.transAxes, fontsize=11, color='#1a252f', style='italic')
ax.text(0, 1.03,
        "Entre filiadas a Voz dobra e a Espiritualidade cai pela metade — imagens espelhadas de uma substituição.",
        transform=ax.transAxes, fontsize=9.5, color='#6b7280', style='italic')

# nota de rodapé
fig.text(0.5, -0.02,
         "Repertório: embeddings semânticos de 5.099 passagens abertas · registro dominante = maior intensidade média por respondente · "
         "significância na intensidade row-centered (Mann-Whitney). Exploratório; associação, não causa.",
         ha='center', fontsize=8.3, color='#94a3b8', style='italic')

plt.subplots_adjust(top=0.80, bottom=0.13, left=0.16, right=0.97)
plt.savefig(OUT, dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig(OUT.with_suffix('.pdf'), bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved: {OUT}")
