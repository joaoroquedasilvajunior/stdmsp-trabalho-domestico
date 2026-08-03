"""
generate_chapter_chart.py — Print-ready figure for the book chapter
====================================================================

Generates a 2-bar horizontal chart of the within-contract hourly racial
wage gap (1T 2026), formatted for a Brazilian academic book chapter.
Outputs both PDF (vector, for the publisher) and PNG (raster, 300 DPI
for Word/Google Docs preview embedding).

Source: dashboard/data/wage_contract_snapshot.json (probed from PNADC
microdata 1T 2026 by etl/probe_wage_contract.py).
"""

import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import rcParams


# Academic typography — serif throughout, modest line weights
rcParams['font.family'] = 'serif'
rcParams['font.size'] = 10
rcParams['axes.linewidth'] = 0.7
rcParams['axes.spines.top'] = False
rcParams['axes.spines.right'] = False
rcParams['axes.edgecolor'] = '#222222'
rcParams['xtick.color'] = '#222222'
rcParams['ytick.color'] = '#222222'
rcParams['pdf.fonttype'] = 42   # embed fonts as TrueType (publisher-safe)
rcParams['ps.fonttype'] = 42

ROOT = Path(__file__).parent.parent
data_path = ROOT / 'dashboard' / 'data' / 'wage_contract_snapshot.json'
snap = json.loads(data_path.read_text(encoding='utf-8'))

# Headline finding: hourly gap by contract (collapsed across formality)
mensalismo_gap = snap['by_contract']['mensalista']['hourly_gap_pct']
diarismo_gap   = snap['by_contract']['diarista']['hourly_gap_pct']
m_n_negras   = snap['by_contract']['mensalista']['n_negras']
m_n_nao      = snap['by_contract']['mensalista']['n_nao_negras']
d_n_negras   = snap['by_contract']['diarista']['n_negras']
d_n_nao      = snap['by_contract']['diarista']['n_nao_negras']

# Portuguese decimal formatting helper
def pct_pt(v):
    return f"{v:.1f}%".replace(".", ",")

categories = ['Mensalismo', 'Diarismo']
values = [mensalismo_gap, diarismo_gap]
value_labels = [pct_pt(v) for v in values]

# Figure sized for a standard book column (~14 cm wide × 7 cm tall)
fig, ax = plt.subplots(figsize=(6.4, 3.3))

# Bars — single charcoal accent, prints clean in B&W
BAR_COLOR = '#2c3e50'
y_pos = [0, 1]
bars = ax.barh(y_pos, values, color=BAR_COLOR, height=0.5,
               edgecolor='#1a252f', linewidth=0.4)

# Parity reference line at 100% — dashed light gray
ax.axvline(x=100, color='#7a7a7a', linestyle='--', linewidth=1, zorder=1)
ax.text(100.4, -0.65, 'Paridade (100%)',
        fontsize=8.5, color='#555555', va='center', style='italic')

# Numeric labels at the end of each bar
for i, label in enumerate(value_labels):
    ax.text(values[i] + 0.8, i, label,
            va='center', fontsize=11, fontweight='bold', color='#1a252f')

# Y-axis: contract type labels
ax.set_yticks(y_pos)
ax.set_yticklabels(categories, fontsize=11.5)
ax.invert_yaxis()   # Mensalismo on top so it reads first

# X-axis: % parity
ax.set_xlim(70, 110)
ax.set_xticks([70, 75, 80, 85, 90, 95, 100, 105])
ax.set_xticklabels(['70%', '75%', '80%', '85%', '90%', '95%', '100%', '105%'],
                   fontsize=9)
ax.set_xlabel('Remuneração por hora — trabalhadora negra ÷ trabalhadora não-negra × 100',
              fontsize=10, labelpad=10)

# Subtle x-grid only
ax.grid(axis='x', linestyle=':', linewidth=0.4, color='#bbbbbb', alpha=0.6)
ax.set_axisbelow(True)

# Title above
ax.set_title('Hiato salarial por hora dentro do contrato (1T 2026)',
             fontsize=12, pad=12, loc='left', color='#1a252f')

plt.tight_layout()

# Output to chapter/ folder in the workspace
out_dir = ROOT / 'chapter'
out_dir.mkdir(parents=True, exist_ok=True)
pdf_path = out_dir / 'grafico_hiato_diarismo.pdf'
png_path = out_dir / 'grafico_hiato_diarismo.png'

plt.savefig(pdf_path, bbox_inches='tight', facecolor='white')
plt.savefig(png_path, dpi=300, bbox_inches='tight', facecolor='white')

print(f"PDF:  {pdf_path}")
print(f"PNG:  {png_path}")
print(f"Mensalismo: {pct_pt(mensalismo_gap)} (n={m_n_negras + m_n_nao})")
print(f"Diarismo:   {pct_pt(diarismo_gap)} (n={d_n_negras + d_n_nao})")
