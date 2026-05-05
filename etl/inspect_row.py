"""Print the first row of the PNADC microdata in 50-char chunks.

Use this to hand-locate column positions when the dictionary-derived
COLUMN_SPECS in pnadc_microdata.py produce garbage during validation.
"""

from pathlib import Path

TXT = Path(__file__).parent / "raw" / "pnadc" / "PNADC_042024.txt"

with open(TXT) as f:
    row = f.readline().rstrip("\n")

print(f"Total length: {len(row)}")
print()
for start in range(0, min(len(row), 850), 50):
    print(f"Pos {start+1:3}-{start+50:3}: {row[start:start+50]!r}")
