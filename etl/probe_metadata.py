"""
probe_metadata.py — Round 5 (filtered)
=======================================

Round 4 was too greedy — SIDRA's pesquisa= keyword matches 9,000+ tables because
"doméstic" also matches "domicílio" (households). This round narrows to:
  * Only the PNAD Contínua survey (table catalog filtered by pesquisa.nome)
  * Only tables whose OWN name contains "doméstic" or "Trabalhador doméstic"
  * Skips tables with periodicidade in the past (long-discontinued series)

Outputs metadata_probe.json with one entry per matched table.

Usage:
    python probe_metadata.py > metadata_probe.json
"""

from __future__ import annotations

import json
import re
import sys
import requests


def list_pnadc_domestic_tables() -> list[dict]:
    """Pull catalog and filter strictly client-side."""
    url = "https://servicodados.ibge.gov.br/api/v3/agregados?pesquisa=doméstic"
    print(f"# catalog: {url}", file=sys.stderr)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    catalog = r.json()

    out = []
    for pesquisa in catalog:
        pname = (pesquisa.get("nome") or "")
        # Only PNAD Contínua surveys — not Censo, not POF, not the older PNAD
        if "PNAD Contínua" not in pname and "Pesquisa Nacional por Amostra de Domicílios Contínua" not in pname:
            continue
        for agg in pesquisa.get("agregados", []):
            tname = (agg.get("nome") or "").lower()
            # Table name must literally mention domestic worker or domestic services
            if not re.search(r"trabalhador.*doméstic|serviço.*doméstic|empregad.*doméstic|emprego.*doméstic", tname):
                continue
            out.append({
                "table_id": agg["id"],
                "table_nome": agg["nome"],
                "pesquisa_nome": pname,
            })
    return out


def probe_table(table_id: str) -> dict:
    url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{table_id}/metadados"
    print(f"# meta: {url}", file=sys.stderr)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.HTTPError as e:
        print(f"#   ! {e}", file=sys.stderr)
        return {"error": str(e)}
    m = r.json()
    has_dom = any(
        "doméstic" in (cat.get("nome") or "").lower() or "domestico" in (cat.get("nome") or "").lower()
        for c in m.get("classificacoes", [])
        for cat in c.get("categorias", [])
    )
    classifs = m.get("classificacoes", [])
    classif_names = [c.get("nome", "") for c in classifs]
    has_sex = any("sexo" in n.lower() for n in classif_names)
    has_race = any("cor" in n.lower() and "raça" in n.lower() for n in classif_names)
    levels = m.get("nivelTerritorial", {}).get("Administrativo", [])

    return {
        "id": m.get("id"),
        "nome": m.get("nome"),
        "periodicidade": m.get("periodicidade"),
        "nivelTerritorial_Administrativo": levels,
        "_has_domestic_category": has_dom,
        "_has_sex_classification": has_sex,
        "_has_race_classification": has_race,
        "_supports_uf_n3": "N3" in levels,
        "variaveis": [
            {"id": v["id"], "nome": v["nome"], "unidade": v.get("unidade")}
            for v in m.get("variaveis", [])
        ],
        "classificacoes": [
            {
                "id": c["id"],
                "nome": c["nome"],
                "categorias_total": len(c.get("categorias", [])),
                "categorias_amostra": [
                    {"id": cat["id"], "nome": cat["nome"]}
                    for cat in c.get("categorias", [])[:30]
                ],
            }
            for c in classifs
        ],
    }


if __name__ == "__main__":
    matches = list_pnadc_domestic_tables()
    print(f"# {len(matches)} PNADC tables match 'trabalhador/serviço doméstico' filter", file=sys.stderr)
    for m in matches:
        print(f"#   {m['table_id']}: {m['table_nome'][:120]}", file=sys.stderr)

    result = {}
    for m in matches:
        tid = str(m["table_id"])
        result[tid] = probe_table(tid)
        if "error" not in result[tid]:
            result[tid]["_pesquisa_nome"] = m["pesquisa_nome"]
            result[tid]["_table_nome_short"] = m["table_nome"]

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
