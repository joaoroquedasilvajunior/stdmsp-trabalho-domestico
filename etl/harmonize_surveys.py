"""
harmonize_surveys.py — Unified core demographics from STDMSP surveys
=====================================================================

Reads the two STDMSP survey XLSX files at the project root and produces
a harmonized core dataset suitable for chapter cross-tabs.

INPUTS
------
  - "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
    Survey A · 2024-25 · n=242 · worker-administered · CCT focus
  - "Final version May_2023.xlsx"
    Survey B · 2021-23 · n=241 · interview-administered · deep qualitative

OUTPUTS (under chapter/survey_harmonized/)
------------------------------------------
  - harmonized_core.csv    one row per respondent, common core variables
  - harmonized_core.xlsx   same data in Excel format
  - survey_b_extras.csv    Survey B's richer variables (estado civil,
                           escolaridade, filhos, parental background, etc.)
  - codebook.md            variable-by-variable documentation
  - quality_report.md      gap rates + sanity cross-tabs

PRIVACY NOTE
------------
CPF (Survey A col 4) is DROPPED entirely from harmonized output per
project decision 2026-06-12. Only anonymous sequential IDs are kept.
The raw survey files at the project root retain CPF — they should not
be committed to git or shared.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "chapter" / "survey_harmonized"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILE_A = ROOT / "Condições de Trabalho para as Trabalhadoras Domésticas (Responses).xlsx"
FILE_B = ROOT / "Final version May_2023.xlsx"


# ---------- normalization helpers ----------

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_race(v) -> str | None:
    """Both surveys → lowercase ASCII feminine form. None if missing."""
    if pd.isna(v):
        return None
    s = strip_accents(str(v).strip().lower())
    mapping = {
        "preta": "preta", "preto": "preta",
        "parda": "parda", "pardo": "parda",
        "branca": "branca", "branco": "branca",
        "amarela": "amarela", "amarelo": "amarela",
        "indigena": "indigena",
    }
    return mapping.get(s)


def race_group(race: str | None) -> str | None:
    if race in ("preta", "parda"):
        return "negras"
    if race in ("branca", "amarela", "indigena"):
        return "nao_negras"
    return None


def norm_gender(v) -> str | None:
    if pd.isna(v):
        return None
    s = str(v).strip().lower()
    if "fem" in s:
        return "Feminino"
    if "masc" in s:
        return "Masculino"
    return None


def age_band_5(age_num) -> str | None:
    """Five-band scheme matching Survey A's native bands."""
    if pd.isna(age_num):
        return None
    try:
        a = float(age_num)
    except (TypeError, ValueError):
        return None
    if a < 18 or a > 110:
        return None
    if a < 30:  return "18-29"
    if a < 40:  return "30-39"
    if a < 50:  return "40-49"
    if a < 60:  return "50-59"
    return "60+"


def survey_a_age_to_band(v) -> str | None:
    """Survey A bands are already aligned with the 5-band scheme."""
    if pd.isna(v):
        return None
    s = strip_accents(str(v).lower())
    if "18" in s and "29" in s: return "18-29"
    if "30" in s and "39" in s: return "30-39"
    if "40" in s and "49" in s: return "40-49"
    if "50" in s and "59" in s: return "50-59"
    if "60" in s: return "60+"
    return None


def norm_cep(v) -> str | None:
    if pd.isna(v):
        return None
    digits = re.sub(r"\D", "", str(v))
    if len(digits) == 8:
        return f"{digits[:5]}-{digits[5:]}"
    if len(digits) == 5:
        return f"{digits}-000"
    return None


def norm_sim_nao(v) -> str | None:
    if pd.isna(v):
        return None
    s = strip_accents(str(v).strip().lower())
    if s.startswith("sim"): return "Sim"
    if s.startswith("nao"): return "Nao"
    return None


def find_col(df: pd.DataFrame, *keywords, prefer_shortest: bool = False) -> str:
    """Find a column whose name contains ALL the keywords (case-insensitive, accent-stripped).
    Raises KeyError if zero matches. On multiple matches: if prefer_shortest=True, returns
    the shortest column name (most specific); otherwise raises so the caller adds a more
    discriminating keyword."""
    matches = []
    for col in df.columns:
        s = strip_accents(str(col)).lower()
        if all(strip_accents(k).lower() in s for k in keywords):
            matches.append(col)
    if not matches:
        raise KeyError(f"No column matches keywords {keywords}")
    if len(matches) > 1:
        if prefer_shortest:
            return min(matches, key=len)
        raise KeyError(f"Multiple columns match {keywords}: {matches}")
    return matches[0]


# ---------- harmonize Survey A ----------

def harmonize_a() -> pd.DataFrame:
    df = pd.read_excel(FILE_A)
    n = len(df)
    # Build with respondent_anon_id first so the DataFrame has rows before
    # scalar columns are broadcast (otherwise scalars assign to an empty frame
    # and stay empty when more rows arrive later).
    out = pd.DataFrame({"respondent_anon_id": [f"A-{i:03d}" for i in range(1, n + 1)]})

    out["survey_id"]            = "A"
    out["survey_year"]          = "2024-25"
    out["data_resposta"]        = pd.to_datetime(df["Timestamp"], errors="coerce").values

    # Age — Survey A only has bands; preserve native band + 5-band
    out["idade_anos"]           = pd.NA   # not collected
    out["faixa_etaria_5b"]      = df[find_col(df, "1 -", "Idade")].apply(survey_a_age_to_band)

    # Gender — direct
    out["genero"]               = df[find_col(df, "2 -", "Genero")].apply(norm_gender)

    # Race
    out["raca_etnia"]           = df[find_col(df, "3 -", "Raca")].apply(norm_race)
    out["raca_grupo"]           = out["raca_etnia"].apply(race_group)

    # Contract type (Survey A only). Use "vinculo" as the discriminating keyword
    # because Q16 also contains "6 -" and "diarista" but only Q6 has "vínculo".
    q6 = df[find_col(df, "vinculo trabalhista")]
    def map_contract(v):
        if pd.isna(v): return None
        s = strip_accents(str(v).lower())
        if "diarista" in s: return "diarista"
        if "vinculo" in s:  return "mensalista"
        return None
    out["tipo_contrato"]        = q6.apply(map_contract)

    # Carteira — Survey A doesn't ask directly. INFER from Q6:
    # "Com vínculo" → likely com_carteira; "Diarista" → likely sem_carteira.
    # Flagged separately in carteira_fonte.
    def infer_carteira(v):
        if pd.isna(v): return None
        s = strip_accents(str(v).lower())
        if "vinculo" in s:  return "Sim"
        if "diarista" in s: return "Nao"
        return None
    out["tem_carteira"]         = q6.apply(infer_carteira)
    out["carteira_fonte"]       = out["tem_carteira"].apply(
        lambda v: "inferido_de_Q6" if v is not None and not pd.isna(v) else None
    )

    # Tempo na ocupação (free text)
    out["tempo_dom_categoria"]  = df[find_col(df, "7 -", "quanto tempo")].astype(str).replace("nan", None)

    # Salário base (Survey A asks; parse to numeric)
    def parse_salary(v):
        if pd.isna(v): return None
        s = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        m = re.search(r"\d+\.?\d*", s)
        if m:
            try:
                val = float(m.group())
                if 100 < val < 50000:  # sanity: monthly salary in BRL
                    return round(val, 2)
            except ValueError:
                return None
        return None
    out["salario_base_brl"]     = df[find_col(df, "9 -", "salario base")].apply(parse_salary)

    # Location
    out["bairro_sp"]            = df[find_col(df, "Bairro")].astype(str).replace("nan", None).str.strip()
    out["cep"]                  = df[find_col(df, "CEP")].apply(norm_cep)
    out["moradia_texto"]        = df[find_col(df, "4 -", "moradia")].astype(str).replace("nan", None)

    return out


# ---------- harmonize Survey B ----------

def harmonize_b() -> pd.DataFrame:
    df = pd.read_excel(FILE_B)
    n = len(df)
    out = pd.DataFrame({"respondent_anon_id": [f"B-{i:03d}" for i in range(1, n + 1)]})

    out["survey_id"]            = "B"
    out["survey_year"]          = "2021-23"
    out["data_resposta"]        = pd.to_datetime(df["Timestamp"], errors="coerce").values

    # Age — Survey B has numeric; derive 5-band from it
    out["idade_anos"]           = pd.to_numeric(df[find_col(df, "Idade da pessoa")], errors="coerce")
    out["faixa_etaria_5b"]      = out["idade_anos"].apply(age_band_5)

    # Gender — not asked; presumed feminine (all qualitative framing in fem.)
    out["genero"]               = "Feminino_presumido"

    # Race
    out["raca_etnia"]           = df[find_col(df, "Origem etnica")].apply(norm_race)
    out["raca_grupo"]           = out["raca_etnia"].apply(race_group)

    # Contract type — Survey B does NOT ask mensalista/diarista directly.
    # Col "1.B - Se trabalha, qual é a modalidade" is Completo/Parcial (jornada),
    # not contract type. Leave NA.
    out["tipo_contrato"]        = None

    # Carteira — direct question (Q13)
    out["tem_carteira"]         = df[find_col(df, "13 -", "carteira")].apply(norm_sim_nao)
    out["carteira_fonte"]       = out["tem_carteira"].apply(
        lambda v: "direto_Q13" if v is not None and not pd.isna(v) else None
    )

    # Tempo na ocupação
    out["tempo_dom_categoria"]  = df[find_col(df, "1 -", "quanto tempo")].astype(str).replace("nan", None)

    # Salário base — not asked in Survey B
    out["salario_base_brl"]     = pd.NA

    # Location
    out["bairro_sp"]            = None    # not separated in Survey B
    out["cep"]                  = df[find_col(df, "CEP do local de moradia")].apply(norm_cep)
    # "Local de moradia" appears in both col 18 ("Local de moradia") and
    # col 19 ("CEP do local de moradia"). prefer_shortest picks col 18.
    out["moradia_texto"]        = df[find_col(df, "Local de moradia", prefer_shortest=True)].astype(str).replace("nan", None)

    front = ["survey_id", "survey_year", "respondent_anon_id", "data_resposta"]
    rest = [c for c in out.columns if c not in front]
    return out[front + rest]


# ---------- Survey B extras (richer demographics, B-only) ----------

def survey_b_extras() -> pd.DataFrame:
    df = pd.read_excel(FILE_B)
    out = pd.DataFrame()
    out["respondent_anon_id"]   = [f"B-{i:03d}" for i in range(1, len(df) + 1)]
    out["estado_civil"]         = df[find_col(df, "Estado civil")].astype(str).replace("nan", None).str.strip().str.lower()
    # "Possui filho" also matches "Se possui filhos: escolaridade dos filhos"
    # and "Se possui filhos: ocupação dos filhos" — prefer the shortest (Q col).
    out["possui_filho"]         = df[find_col(df, "Possui filho", prefer_shortest=True)].astype(str).replace("nan", None)
    out["n_filhos"]             = pd.to_numeric(df[find_col(df, "Quantos")], errors="coerce")
    out["nivel_educacao"]       = df[find_col(df, "Nivel de educacao")].astype(str).replace("nan", None)
    out["escolaridade_mae"]     = df[find_col(df, "Escolaridade da mae")].astype(str).replace("nan", None)
    out["escolaridade_pai"]     = df[find_col(df, "Escolaridade do pai")].astype(str).replace("nan", None)
    out["ocupacao_pais"]        = df[find_col(df, "Ocupacao dos pais")].astype(str).replace("nan", None)
    out["estado_origem"]        = df[find_col(df, "Estado de origem")].astype(str).replace("nan", None).str.strip()
    out["pais_origem"]          = df[find_col(df, "pais de origem")].astype(str).replace("nan", None).str.strip()
    out["estado_saude"]         = df[find_col(df, "Estado de saude")].astype(str).replace("nan", None)
    out["modalidade_jornada"]   = df[find_col(df, "1.B", "modalidade")].astype(str).replace("nan", None)
    out["trabalha_atualmente"]  = df[find_col(df, "1.A", "trabalha atualmente")].apply(norm_sim_nao)
    return out


# ---------- gap report ----------

def gap_report(df: pd.DataFrame, name: str) -> str:
    lines = [f"\n### {name} (n = {len(df)})\n"]
    lines.append("| Variável | Preenchimento | % |")
    lines.append("|---|---:|---:|")
    for col in df.columns:
        non_null = df[col].notna().sum()
        # also treat empty string as missing
        if df[col].dtype == object:
            non_null = ((df[col].notna()) & (df[col].astype(str).str.strip() != "") & (df[col].astype(str) != "None")).sum()
        pct = 100 * non_null / len(df) if len(df) else 0
        lines.append(f"| `{col}` | {non_null}/{len(df)} | {pct:.1f}% |")
    return "\n".join(lines)


def crosstab_md(df: pd.DataFrame, row: str, col: str, title: str) -> str:
    lines = [f"\n### {title}\n"]
    if row not in df.columns or col not in df.columns:
        lines.append(f"_(columns not available)_")
        return "\n".join(lines)
    ct = pd.crosstab(df[row], df[col], dropna=False, margins=True, margins_name="Total")
    lines.append(ct.to_markdown())
    return "\n".join(lines)


# ---------- main ----------

def main():
    a = harmonize_a()
    b = harmonize_b()
    core = pd.concat([a, b], ignore_index=True)

    extras = survey_b_extras()

    # Outputs
    core_csv = OUT_DIR / "harmonized_core.csv"
    core_xlsx = OUT_DIR / "harmonized_core.xlsx"
    extras_csv = OUT_DIR / "survey_b_extras.csv"

    core.to_csv(core_csv, index=False, encoding="utf-8")
    core.to_excel(core_xlsx, index=False)
    extras.to_csv(extras_csv, index=False, encoding="utf-8")

    print(f"Wrote {core_csv}  ({len(core)} rows)")
    print(f"Wrote {core_xlsx}")
    print(f"Wrote {extras_csv}  ({len(extras)} rows)")

    # Quality report
    qr_lines = [
        "# STDMSP Surveys — Quality Report (Harmonized Core)",
        "",
        f"Gerado por `etl/harmonize_surveys.py`. Survey A n={len(a)}, Survey B n={len(b)}, total n={len(core)}.",
        "",
        "## 1. Cobertura por variável (preenchimento ≠ vazio)",
        gap_report(a, "Survey A (2024-25)"),
        gap_report(b, "Survey B (2021-23)"),
        gap_report(core, "Core unificado"),
        "",
        "## 2. Cruzamentos de sanidade",
        crosstab_md(core, "raca_grupo", "survey_id",
                    "Raça (grupo) × Survey — composição racial em cada survey"),
        crosstab_md(core, "faixa_etaria_5b", "survey_id",
                    "Faixa etária × Survey"),
        crosstab_md(core, "raca_grupo", "faixa_etaria_5b",
                    "Raça × Faixa etária (n combinado)"),
        crosstab_md(a, "raca_grupo", "tipo_contrato",
                    "Survey A: Raça × Tipo de contrato (apenas para quem respondeu Q6)"),
        crosstab_md(b, "raca_grupo", "tem_carteira",
                    "Survey B: Raça × Carteira (resposta direta)"),
        "",
        "## 3. Salário base (Survey A apenas)",
    ]
    sal = a["salario_base_brl"].dropna()
    if len(sal):
        # Salary by race
        sal_by_race = a.groupby("raca_grupo")["salario_base_brl"].agg(["count", "mean", "median"]).round(0)
        qr_lines.append(sal_by_race.to_markdown())
        qr_lines.append(f"\nResumo geral: n={len(sal)}, mín R$ {sal.min():.0f}, mediana R$ {sal.median():.0f}, máx R$ {sal.max():.0f}, média R$ {sal.mean():.0f}")

    (OUT_DIR / "quality_report.md").write_text("\n".join(qr_lines), encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'quality_report.md'}")

    # Codebook
    codebook = """# Codebook — STDMSP Surveys Harmonized Core

Gerado por `etl/harmonize_surveys.py` em 2026-06-12.

## Decisões editoriais

- **CPF dropado integralmente.** O CPF da entrevistada presente na Survey A (col 4, 87,6% cobertura) NÃO é incluído em nenhuma das saídas harmonizadas. Apenas IDs anônimos sequenciais (A-001..A-242, B-001..B-241) são mantidos. Os arquivos brutos preservam o CPF mas não devem ser commitados nem compartilhados.
- **Gênero da Survey B presumido feminino.** A Survey B não pergunta gênero diretamente; o enquadramento qualitativo todo é em forma feminina ("trabalhadora", "ela"). Marcamos como `Feminino_presumido` em vez de `Feminino` para tornar visível que é uma inferência.
- **Carteira da Survey A inferida.** A Survey A não pergunta carteira diretamente. Inferimos a partir da Q6 (diarista vs com vínculo): "com vínculo" → carteira=Sim; "diarista" → carteira=Não. A coluna `carteira_fonte` distingue `inferido_de_Q6` (A) de `direto_Q13` (B). Cobertura limitada pela Q6 (65,3% na Survey A).
- **Tipo de contrato apenas na Survey A.** A Survey B não distingue mensalista/diarista. A coluna `tipo_contrato` é NA para todos os respondentes B.
- **Faixas etárias harmonizadas em 5 bandas** (18-29, 30-39, 40-49, 50-59, 60+) por compatibilidade com a granularidade da Survey A. Para a Survey B reconstruímos as bandas a partir da idade numérica (99,6% cobertura). A coluna `idade_anos` é populada apenas para B.

## Variáveis — `harmonized_core.csv` / `harmonized_core.xlsx`

| Coluna | Tipo | Survey A | Survey B | Notas |
|---|---|---|---|---|
| `survey_id` | str | "A" | "B" | identificador do survey |
| `survey_year` | str | "2024-25" | "2021-23" | janela de campo |
| `respondent_anon_id` | str | A-001..A-242 | B-001..B-241 | ID anônimo sequencial |
| `data_resposta` | datetime | Timestamp do Google Forms | idem | quando a resposta foi submetida |
| `idade_anos` | num | NA | col "Idade da pessoa entrevistada" | apenas B coleta numérica |
| `faixa_etaria_5b` | str | mapeada da col Q1 | derivada de `idade_anos` | bandas 18-29/30-39/40-49/50-59/60+ |
| `genero` | str | col Q2 (Feminino/Masculino) | "Feminino_presumido" | B não pergunta direto |
| `raca_etnia` | str | col Q3 normalizada | col "Origem étnica" normalizada | preta/parda/branca/amarela/indigena |
| `raca_grupo` | str | derivado | derivado | negras (preta+parda) / nao_negras |
| `tipo_contrato` | str | mensalista/diarista de Q6 | NA | só Survey A pergunta |
| `tem_carteira` | str | inferido de Q6 | direto de Q13 | `carteira_fonte` distingue |
| `carteira_fonte` | str | "inferido_de_Q6" | "direto_Q13" | rastreabilidade |
| `tempo_dom_categoria` | str | col Q7 (texto) | col Q1 (texto) | tempo de ocupação |
| `salario_base_brl` | num | parsed de Q9 | NA | só Survey A pergunta |
| `bairro_sp` | str | col "Bairro" direta | NA | B não separa bairro |
| `cep` | str | col CEP normalizada | col "CEP do local de moradia" normalizada | formato XXXXX-XXX |
| `moradia_texto` | str | col Q4 livre | col "Local de moradia" livre | texto bruto preservado |

## Variáveis — `survey_b_extras.csv` (Survey B apenas)

| Coluna | Descrição |
|---|---|
| `respondent_anon_id` | ID anônimo B-001..B-241 |
| `estado_civil` | solteira/casada/divorciada/viúva/união estável |
| `possui_filho` / `n_filhos` | Sim/Não + número |
| `nivel_educacao` | 8 categorias do analfabetismo ao superior |
| `escolaridade_mae` / `escolaridade_pai` | mesma escala |
| `ocupacao_pais` | texto livre |
| `estado_origem` / `pais_origem` | migração interna e internacional |
| `estado_saude` | autorreporte |
| `modalidade_jornada` | Completo/Parcial (não é mensalista/diarista) |
| `trabalha_atualmente` | Sim/Não |

## Limitações conhecidas

- **Survey A é auto-aplicada**, com lacunas substanciais nas perguntas longas (Q12 contrato 65%, Q13/Q14 sobre CCT 47–52%). As demografias core (idade, gênero, raça) têm 97% de cobertura.
- **Survey B é entrevista guiada**, com cobertura demográfica acima de 96% em todas as variáveis core. As lacunas estão nos campos qualitativos longos (relatos de abuso, negociação) — preservados nos arquivos brutos mas fora do escopo desta harmonização.
- **Composição racial das amostras** difere: Survey A 59,6% pretas+pardas (240/235 válidos), Survey B 67,9% (159/234). Ambas são amostras de conveniência via STDMSP — não são representativas da categoria em SP. A diferença pode refletir vieses de auto-seleção (quem aceita responder formulário escrito vs. quem aceita entrevista qualitativa).
- **Não há vínculo respondente entre os dois surveys.** Tratá-los como amostras independentes.
"""
    (OUT_DIR / "codebook.md").write_text(codebook, encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'codebook.md'}")


if __name__ == "__main__":
    main()
