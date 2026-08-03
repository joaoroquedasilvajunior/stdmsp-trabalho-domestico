"""
categorize_q18.py — Apply 5 categories to Q18 of Survey A
===========================================================

Q18: "Na sua opinião, qual é a função mais importante do Sindicato?"
(open text, n=215 valid responses out of 242)

Five categories applied:
  1 — Defesa dos direitos trabalhistas
  2 — Orientação sobre direitos
  3 — Apoio jurídico e cobrança dos patrões
  4 — Cuidado, proteção e acolhimento
  5 — Todas / não sabe / sem resposta clara

The classification dict below was built by reading each response and
assigning the dominant theme. For responses mixing two categories,
preference goes to the FIRST action verb the respondent named
("defender e orientar" → category 1 = defesa, "orientar e defender"
→ category 2 = orientação). For responses listing only union
departments ("atendimento", "portaria", "jurídico"), only the explicit
"jurídico" maps to category 3; the others fall to category 5.

OUTPUTS (in chapter/survey_harmonized/)
---------------------------------------
  - q18_categorized.csv     respondent_anon_id, raw_text, categoria_num, categoria_label
  - q18_summary.md          distribution table + sample answers per category
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
FILE_A = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT_DIR = ROOT / "chapter" / "survey_harmonized"
OUT_DIR.mkdir(parents=True, exist_ok=True)


CATEGORIES = {
    1: "Defesa dos direitos trabalhistas",
    2: "Orientação sobre direitos",
    3: "Apoio jurídico e cobrança dos patrões",
    4: "Cuidado, proteção e acolhimento",
    5: "Todas / não sabe / sem resposta clara",
}

# Sub-categorias dentro da categoria 5 (desagregação fina).
# Mantém o esquema de 5 categorias como camada superior; adiciona 5a-5e
# como leitura mais granular do que está dentro de "5". Para as categorias
# substantivas (1-4) a sub-categoria é o mesmo número.
SUB_CATEGORIES = {
    "1":  "Defesa dos direitos trabalhistas",
    "2":  "Orientação sobre direitos",
    "3":  "Apoio jurídico e cobrança dos patrões",
    "4":  "Cuidado, proteção e acolhimento",
    "5a": "\"Todas\" / tudo é importante",
    "5b": "Listou setores físicos do sindicato sem articular função",
    "5c": "Explicitamente \"não sabe\"",
    "5d": "\"Ainda vou descobrir / conhecer\"",
    "5e": "Vago, genérico ou off-topic",
}

# Atribuição respondente_id → sub-categoria dentro de 5.
# Inferida pela leitura textual das 85 respostas classificadas como
# categoria 5 (sem resposta clara). Substantivas (1-4) usam o número
# direto como sub-categoria.
SUB_CLASSIFICATION_CAT5 = {
    # ---------- 5a — "Todas" ----------
    "A-007": "5a", "A-064": "5a", "A-065": "5a", "A-067": "5a", "A-070": "5a",
    "A-071": "5a", "A-074": "5a", "A-079": "5a", "A-080": "5a", "A-084": "5a",
    "A-085": "5a", "A-087": "5a", "A-088": "5a", "A-089": "5a", "A-090": "5a",
    "A-091": "5a", "A-092": "5a", "A-093": "5a", "A-094": "5a", "A-095": "5a",
    "A-096": "5a", "A-097": "5a", "A-100": "5a", "A-102": "5a", "A-104": "5a",
    "A-105": "5a", "A-106": "5a", "A-129": "5a", "A-164": "5a", "A-165": "5a",
    "A-197": "5a", "A-207": "5a", "A-224": "5a",

    # ---------- 5b — Listou setores físicos do sindicato ----------
    "A-058": "5b", "A-059": "5b", "A-061": "5b", "A-063": "5b", "A-066": "5b",
    "A-068": "5b", "A-069": "5b", "A-072": "5b", "A-075": "5b", "A-076": "5b",
    "A-081": "5b", "A-082": "5b", "A-083": "5b", "A-086": "5b", "A-099": "5b",
    "A-103": "5b", "A-107": "5b", "A-185": "5b", "A-186": "5b", "A-187": "5b",
    "A-188": "5b", "A-189": "5b", "A-191": "5b",

    # ---------- 5c — Explicitamente "não sabe" ----------
    "A-031": "5c", "A-044": "5c", "A-054": "5c", "A-057": "5c", "A-078": "5c",
    "A-138": "5c", "A-140": "5c", "A-179": "5c", "A-180": "5c", "A-192": "5c",

    # ---------- 5d — "Vou descobrir / vou conhecer" ----------
    "A-119": "5d", "A-132": "5d", "A-133": "5d", "A-135": "5d", "A-142": "5d",
    "A-146": "5d", "A-220": "5d", "A-227": "5d",

    # ---------- 5e — Vago, genérico ou off-topic ----------
    "A-018": "5e", "A-041": "5e", "A-077": "5e", "A-098": "5e", "A-159": "5e",
    "A-160": "5e", "A-162": "5e", "A-166": "5e", "A-171": "5e", "A-195": "5e",
    "A-209": "5e",
}


# Mapping: respondent_anon_id → category number.
# Built by manually reading all 215 valid Q18 responses on 2026-06-12.
CLASSIFICATION = {
    # ---------- Category 1: Defesa dos direitos trabalhistas ----------
    "A-001": 1, "A-003": 1, "A-006": 1, "A-009": 1, "A-016": 1, "A-019": 1,
    "A-022": 1, "A-024": 1, "A-026": 1, "A-036": 1, "A-052": 1, "A-055": 1,
    "A-108": 1, "A-109": 1, "A-111": 1, "A-112": 1, "A-113": 1, "A-114": 1,
    "A-115": 1, "A-116": 1, "A-120": 1, "A-121": 1, "A-122": 1, "A-123": 1,
    "A-124": 1, "A-125": 1, "A-126": 1, "A-127": 1, "A-128": 1, "A-130": 1,
    "A-131": 1, "A-134": 1, "A-136": 1, "A-137": 1, "A-139": 1, "A-141": 1,
    "A-143": 1, "A-145": 1, "A-147": 1, "A-149": 1, "A-150": 1, "A-153": 1,
    "A-156": 1, "A-157": 1, "A-161": 1, "A-177": 1, "A-181": 1, "A-183": 1,
    "A-204": 1, "A-205": 1, "A-206": 1, "A-208": 1, "A-210": 1, "A-211": 1,
    "A-213": 1, "A-216": 1, "A-219": 1, "A-223": 1, "A-228": 1, "A-231": 1,
    "A-236": 1, "A-237": 1, "A-238": 1, "A-239": 1,

    # ---------- Category 2: Orientação sobre direitos ----------
    "A-002": 2, "A-004": 2, "A-014": 2, "A-020": 2, "A-029": 2, "A-030": 2,
    "A-034": 2, "A-035": 2, "A-037": 2, "A-040": 2, "A-048": 2, "A-117": 2,
    "A-148": 2, "A-154": 2, "A-158": 2, "A-172": 2, "A-173": 2, "A-174": 2,
    "A-182": 2, "A-196": 2, "A-198": 2, "A-199": 2, "A-200": 2, "A-201": 2,
    "A-212": 2, "A-218": 2, "A-225": 2, "A-240": 2, "A-241": 2, "A-242": 2,

    # ---------- Category 3: Apoio jurídico e cobrança dos patrões ----------
    "A-023": 3, "A-049": 3, "A-050": 3, "A-053": 3, "A-056": 3, "A-060": 3,
    "A-062": 3, "A-073": 3, "A-118": 3, "A-144": 3, "A-184": 3, "A-190": 3,
    "A-194": 3, "A-217": 3, "A-221": 3, "A-222": 3, "A-226": 3, "A-229": 3,
    "A-230": 3, "A-232": 3, "A-233": 3, "A-234": 3, "A-235": 3,

    # ---------- Category 4: Cuidado, proteção e acolhimento ----------
    "A-011": 4, "A-012": 4, "A-015": 4, "A-017": 4, "A-021": 4, "A-047": 4,
    "A-110": 4, "A-151": 4, "A-152": 4, "A-155": 4, "A-203": 4, "A-214": 4,
    "A-215": 4,

    # ---------- Category 5: Todas / não sabe / sem resposta clara ----------
    "A-007": 5, "A-018": 5, "A-031": 5, "A-041": 5, "A-044": 5, "A-054": 5,
    "A-057": 5, "A-058": 5, "A-059": 5, "A-061": 5, "A-063": 5, "A-064": 5,
    "A-065": 5, "A-066": 5, "A-067": 5, "A-068": 5, "A-069": 5, "A-070": 5,
    "A-071": 5, "A-072": 5, "A-074": 5, "A-075": 5, "A-076": 5, "A-077": 5,
    "A-078": 5, "A-079": 5, "A-080": 5, "A-081": 5, "A-082": 5, "A-083": 5,
    "A-084": 5, "A-085": 5, "A-086": 5, "A-087": 5, "A-088": 5, "A-089": 5,
    "A-090": 5, "A-091": 5, "A-092": 5, "A-093": 5, "A-094": 5, "A-095": 5,
    "A-096": 5, "A-097": 5, "A-098": 5, "A-099": 5, "A-100": 5, "A-102": 5,
    "A-103": 5, "A-104": 5, "A-105": 5, "A-106": 5, "A-107": 5, "A-119": 5,
    "A-129": 5, "A-132": 5, "A-133": 5, "A-135": 5, "A-138": 5, "A-140": 5,
    "A-142": 5, "A-146": 5, "A-159": 5, "A-160": 5, "A-162": 5, "A-164": 5,
    "A-165": 5, "A-166": 5, "A-171": 5, "A-179": 5, "A-180": 5, "A-185": 5,
    "A-186": 5, "A-187": 5, "A-188": 5, "A-189": 5, "A-191": 5, "A-192": 5,
    "A-195": 5, "A-197": 5, "A-207": 5, "A-209": 5, "A-220": 5, "A-224": 5,
    "A-227": 5,
}


def main():
    df = pd.read_excel(FILE_A)
    q18_col = df.columns[29]   # "18 - Na sua opinião, qual é a função mais importante do Sindicato?"

    rows = []
    for i, val in enumerate(df[q18_col], start=1):
        anon_id = f"A-{i:03d}"
        if pd.isna(val) or not str(val).strip():
            continue
        text = " ".join(str(val).split())
        cat_num = CLASSIFICATION.get(anon_id)
        cat_label = CATEGORIES.get(cat_num) if cat_num else "NÃO CLASSIFICADO"
        # Sub-categoria: para 1-4 é o próprio número como string; para 5
        # vem da SUB_CLASSIFICATION_CAT5.
        if cat_num is None:
            sub_code = None
        elif cat_num == 5:
            sub_code = SUB_CLASSIFICATION_CAT5.get(anon_id)
        else:
            sub_code = str(cat_num)
        sub_label = SUB_CATEGORIES.get(sub_code) if sub_code else None
        rows.append({
            "respondent_anon_id": anon_id,
            "raw_text": text,
            "categoria_num": cat_num,
            "categoria_label": cat_label,
            "categoria_sub": sub_code,
            "categoria_sub_label": sub_label,
        })

    out_df = pd.DataFrame(rows)
    csv_path = OUT_DIR / "q18_categorized.csv"
    out_df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Wrote {csv_path}  ({len(out_df)} rows)")

    # Sanity: any unclassified?
    unclassified = out_df[out_df["categoria_num"].isna()]
    if len(unclassified):
        print(f"WARNING: {len(unclassified)} unclassified responses:")
        print(unclassified[["respondent_anon_id", "raw_text"]].to_string())

    # Distribution summary
    print("\n=== Distribution (top-level) ===")
    total = len(out_df)
    summary_lines = [
        "# Q18 — Categorização das respostas",
        "",
        f"**Pergunta:** \"{q18_col}\"",
        "",
        f"**Total de respostas válidas classificadas:** {total} de 242 (88,8% de cobertura)",
        "",
        "## 1. Distribuição (5 categorias)",
        "",
        "| # | Categoria | n | % |",
        "|---|---|---:|---:|",
    ]
    for cat_num in sorted(CATEGORIES.keys()):
        n = (out_df["categoria_num"] == cat_num).sum()
        pct = 100 * n / total
        label = CATEGORIES[cat_num]
        summary_lines.append(f"| {cat_num} | {label} | {n} | {pct:.1f}% |")
        print(f"  Cat {cat_num} ({label}): {n} ({pct:.1f}%)")

    print("\n=== Distribution (disaggregated) ===")
    summary_lines.extend([
        "",
        "## 2. Distribuição desagregada (9 sub-categorias)",
        "",
        "A categoria 5 do esquema original é heterogênea — agrupa cinco padrões qualitativamente distintos de não-resposta articulada. A desagregação abaixo mantém as categorias 1-4 inalteradas e divide a categoria 5 em cinco sub-buckets.",
        "",
        "| Sub-código | Sub-categoria | n | % |",
        "|---|---|---:|---:|",
    ])
    sub_order = ["1", "2", "3", "4", "5a", "5b", "5c", "5d", "5e"]
    for sub_code in sub_order:
        n = (out_df["categoria_sub"] == sub_code).sum()
        pct = 100 * n / total
        label = SUB_CATEGORIES[sub_code]
        summary_lines.append(f"| {sub_code} | {label} | {n} | {pct:.1f}% |")
        print(f"  {sub_code} ({label}): {n} ({pct:.1f}%)")

    # Sample answers per sub-category for the README
    summary_lines.append("\n## 3. Exemplos de respostas por sub-categoria\n")
    for sub_code in sub_order:
        label = SUB_CATEGORIES[sub_code]
        samples = out_df[out_df["categoria_sub"] == sub_code].head(8)
        summary_lines.append(f"### {sub_code}. {label}\n")
        for _, r in samples.iterrows():
            summary_lines.append(f"- **{r['respondent_anon_id']}**: _{r['raw_text']}_")
        summary_lines.append("")

    # Notes on the coding decisions
    summary_lines.extend([
        "## Notas de codificação",
        "",
        "- **Respostas mistas (duas categorias):** quando a resposta nomeia dois temas, prevalece o **primeiro verbo** mencionado. Ex.: \"defender e orientar\" → categoria 1; \"orientar e defender\" → categoria 2.",
        "- **\"Cuidar\":** quando o objeto é a **trabalhadora** (\"cuidar das domésticas\", \"cuidar de nós\") → categoria 4 (acolhimento). Quando o objeto são os **direitos** (\"cuidar dos direitos\", \"cuidar das causas trabalhistas\") → categoria 1 (defesa, sentido figurado).",
        "- **Departamentos do sindicato como resposta:** quando a resposta nomeia apenas o departamento — \"atendimento\", \"portaria\" — sem articular a função, classifico como categoria 5 (sem resposta clara). O único departamento com função explícita é \"jurídico\" (ou \"departamento jurídico\"), que vai para categoria 3.",
        "- **\"Patrão\" / \"patroa\" / \"contra os patrões\":** respostas que mencionam explicitamente a cobrança ou enfrentamento de empregadores (\"fazer patrão pagar\", \"contra os patrões\", \"botar a patroa no pau\", \"em cima dos patrões\") → categoria 3.",
        "- **\"Defender na justiça\" / \"advogado\" / \"cálculos\":** referência específica ao instrumento jurídico → categoria 3 (não categoria 1).",
        "- **Categoria 5 inclui também respostas confusas ou off-topic** (\"serviços domésticos\", \"sim\", \"é muito importante\"), respostas sobre não conhecer o sindicato (\"ainda vou descobrir\", \"nem sabia que existia\"), e respostas que listam três ou mais funções sem hierarquizar.",
    ])

    md_path = OUT_DIR / "q18_summary.md"
    md_path.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
