"""
audit_q18_categorization.py
===========================

Audit / prova de bancada da categorização de Q18 (função mais importante do
sindicato).  Para cada resposta livre, mostra:

  1. o texto BRUTO exato como digitado pela trabalhadora
  2. a categoria atribuída (1-5)
  3. QUAL palavra-chave disparou a atribuição (a primeira que casou)
  4. faixa de raça (afro / branca / outras / nan), pra fins de auditoria

Motivação: JF Mayer levantou uma dúvida sobre 30 hits de "cuida"/"cuidado" na
Cat 4.  Este arquivo permite auditar cada uma dessas 30 respostas — checar se
o keyword realmente CAPTA o sentido, se caberia melhor em outra categoria,
se há falsos positivos etc.

Output:
  chapter/survey_a_analysis/Q18_audit.md
  chapter/survey_a_analysis/Q18_audit.csv   (para importar em planilha)
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
SRC = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
OUT_MD  = ROOT / "chapter" / "survey_a_analysis" / "Q18_audit.md"
OUT_CSV = ROOT / "chapter" / "survey_a_analysis" / "Q18_audit.csv"

Q18_BUCKETS = {
    "1": "1. Defesa dos direitos trabalhistas",
    "2": "2. Orientação sobre direitos",
    "3": "3. Apoio jurídico e cobrança dos patrões",
    "4": "4. Cuidado, proteção e acolhimento",
    "5": "5. Todas / não sabe / vago",
}

# Priority ordered — the FIRST list to match wins.
# NB: usamos RADICAIS quando possível (cuid, proteg, acolh, ampar, defend,
# orient, inform, esclarec, divulg, conscientiz, jurídic, fiscaliz, cobr)
# para capturar todas as flexões verbais (cuidar, cuidando, cuidado, cuidam,
# proteger, protegendo, proteção, protegido…).  Correção pós-auditoria
# 2026-07-03 (JF Mayer notou que "cuidar" ficava no residual).
KEYWORDS = {
    "1": ["defend", "defesa", "direitos trabalh", "lutar pelo bem",
          "lutar pelos direitos", "garantir o que o trabalho",
          "garantia dos direitos", "garantir o direito",
          "buscar direitos", "buscar os direitos"],
    "2": ["orient", "inform", "esclarec",
          "esclaresc", "divulg", "conscientiz",
          "instruir", "ensinar", "valoriza"],
    "3": ["jurídic", "advogad", "processo", "lei ", "leis",
          "judicial", "fiscaliz", "cobr", "patrão",
          "patrões", "empregador"],
    "4": ["cuid", "proteg", "acolh",
          "ampar", "apoio", "apoiar", "suporte", "ajudar todos",
          "ajudar nas necessidades", "ajudar quem precis"],
}


def categorize_with_trace(s):
    """Return (bucket_code, matched_keyword_or_None).

    Mirrors categorize_q18 in analyze_survey_a.py but ALSO returns the first
    keyword that matched — so we can audit which trigger fired."""
    if s is None or pd.isna(s):
        return None, None
    text = str(s).strip().lower()
    if not text:
        return None, None
    for cat, kws in KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return cat, kw
    return "5", None   # residual bucket


def race(v):
    if pd.isna(v): return None
    s = str(v).strip().lower()
    if s in ('pardo','parda','preto','preta'): return 'afro'
    if s in ('branco','branca'): return 'branca'
    if s in ('amarelo','amarela','indígena','indigena'): return 'outras'
    return 'outras'


def main():
    df = pd.read_excel(SRC)
    q18_col = [c for c in df.columns if c.startswith("18 -")][0]
    q3_col  = [c for c in df.columns if c.startswith("3 -")][0]

    df["race"] = df[q3_col].apply(race)

    rows = []
    for _, r in df.iterrows():
        raw = r[q18_col]
        cat, kw = categorize_with_trace(raw)
        rows.append({
            "raw": raw,
            "cat_code": cat,
            "cat_label": Q18_BUCKETS.get(cat, ""),
            "trigger_kw": kw,
            "race": r["race"],
        })
    out = pd.DataFrame(rows)

    # Filter to rows with a non-empty raw response
    out_valid = out[out["raw"].notna() & (out["raw"].astype(str).str.strip() != "")]
    n_valid = len(out_valid)

    # ---------- CSV ----------
    out_valid[["cat_code","cat_label","trigger_kw","race","raw"]].to_csv(
        OUT_CSV, index=False, encoding="utf-8-sig")

    # ---------- Markdown ----------
    lines = []
    lines.append("# Q18 — auditoria completa da categorização")
    lines.append("")
    lines.append(f"**Fonte:** STDMSP Pesquisa A (2024), pergunta Q18 "
                 "*\"Na sua opinião, qual é a função mais importante do Sindicato?\"*")
    lines.append("")
    lines.append(f"**Total de respostas válidas:** {n_valid} (de {len(df)} formulários)")
    lines.append("")
    lines.append("**Método:** heurística keyword-first, com prioridade "
                 "**Cat 1 → 2 → 3 → 4 → 5 (residual)**. "
                 "A primeira lista de palavras-chave que casar com o texto "
                 "cru (após lowercase e strip) define a categoria. Não há "
                 "sobreposição — cada resposta cai em UMA categoria só. "
                 "Coluna `trigger_kw` mostra QUAL palavra-chave disparou a "
                 "atribuição.")
    lines.append("")
    lines.append("**Distribuição:**")
    lines.append("")
    lines.append("| Código | Categoria | n | % |")
    lines.append("|:---:|---|---:|---:|")
    total_cats = out_valid["cat_code"].value_counts()
    for code, label in Q18_BUCKETS.items():
        n = int(total_cats.get(code, 0))
        pct = 100*n/n_valid if n_valid else 0
        lines.append(f"| {code} | {label} | {n} | {pct:.1f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # For each bucket, list every response with trigger
    for code, label in Q18_BUCKETS.items():
        subset = out_valid[out_valid["cat_code"] == code].copy()
        lines.append(f"## Categoria {label}   ({len(subset)} respostas)")
        lines.append("")

        if code != "5":
            # For 1-4 show trigger keyword counts first
            kw_counts = subset["trigger_kw"].value_counts()
            lines.append(f"**Distribuição das palavras-chave que dispararam a atribuição:**")
            lines.append("")
            lines.append("| Palavra-chave | n |")
            lines.append("|---|---:|")
            for kw, n in kw_counts.items():
                lines.append(f"| `{kw}` | {n} |")
            lines.append("")

        lines.append("**Respostas (texto bruto, em ordem alfabética):**")
        lines.append("")
        lines.append("| # | Raça | Trigger | Texto |")
        lines.append("|---:|:---:|:---:|---|")
        subset_sorted = subset.sort_values("raw", key=lambda s: s.astype(str).str.lower())
        for i, (_, row) in enumerate(subset_sorted.iterrows(), start=1):
            raw = str(row["raw"]).replace("|", "\\|").replace("\n", " ").strip()
            race_label = row["race"] or "—"
            trigger = f"`{row['trigger_kw']}`" if row["trigger_kw"] else "—"
            lines.append(f"| {i} | {race_label} | {trigger} | {raw} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved markdown: {OUT_MD}")
    print(f"Saved CSV:      {OUT_CSV}")
    print()
    print(f"Total válidas: {n_valid}")
    print(out_valid["cat_code"].value_counts().sort_index())
    print()
    print("Palavras-chave mais acionadas na Cat 4 (cuidado/proteção/acolhimento):")
    cat4 = out_valid[out_valid["cat_code"]=="4"]
    print(cat4["trigger_kw"].value_counts())


if __name__ == "__main__":
    main()
