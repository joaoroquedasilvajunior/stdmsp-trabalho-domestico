"""
probe_sidra_4093.py — Discovery probe for SIDRA tables (CNPJ search)
=====================================================================

ORIGINAL ASSUMPTION (wrong, kept for record):
  Tabela 4093 was supposed to publish "% of self-employed with CNPJ".
  Actual content of 4093: força de trabalho × sexo only — no posição
  na ocupação and no CNPJ breakdown.

REVISED MISSION:
  Probe N candidate PNADC tables looking for a classification that
  has CATEGORIES mentioning "conta-própria" AND "CNPJ" (or "sem
  cnpj" / "sem cadastro"). Surface the best candidate to feed the
  manifest entry.

USAGE
-----
    python etl/probe_sidra_4093.py               # default candidate list
    python etl/probe_sidra_4093.py 6320 7714     # explicit table IDs

OUTPUT (per table)
------------------
  - Table title + periodicidade
  - Each classification: id, name, category count
  - For classifications that look related to posição na ocupação:
    full category dump highlighting conta-própria + CNPJ hits
  - If a "CNPJ-aware" classification is found, run sample fetch
    at BR + SP for the latest period

NO Supabase writes — read-only probe.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

import requests


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("probe_4093")


SIDRA_BASE = "https://apisidra.ibge.gov.br/values"

# Candidate PNADC tables most likely to have a "conta-própria × CNPJ"
# classification. Ordered from most likely to least:
#   6320 — Trimestral Móvel · posição na ocupação (categoria c11913);
#          we already use it for trabalhador doméstico but only fetch
#          3 of its categories — full c11913 dump may have CNPJ split
#   7714 — Anual · características pessoas ocupadas (suspected richest)
#   7716 — Anual · características rendimentos
#   6403 — Anual · posição na ocupação (PNADC anual continuation)
#   6463 — variantes anuais com sex/race × posição
#   6471 — variantes anuais
DEFAULT_CANDIDATES = [6320, 7714, 7716, 6403, 6463, 6471, 6477]


# Keywords we expect on conta-própria PT labels in this classification
CONTA_PROPRIA_KEYWORDS = ["conta própria", "conta-própria", "conta propria"]
CNPJ_KEYWORDS = ["cnpj"]
SEM_CNPJ_HINTS = ["sem cnpj", "não possu", "nao possu", "sem cadastro"]


def fetch(url: str, timeout: int = 30) -> Any:
    log.info("GET %s", url)
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "stdmsp-etl/1.0"})
    r.raise_for_status()
    return r.json()


def find_conta_propria_categories(classifications: list[dict]) -> dict[str, list[dict]]:
    """Walk each classification and identify categories whose PT label
    mentions conta-própria. Return {classification_id: [matched_cats]}."""
    hits: dict[str, list[dict]] = {}
    for cls in classifications:
        cls_id = str(cls.get("id"))
        cats = cls.get("categorias", []) or []
        matched = []
        for cat in cats:
            label = (cat.get("nome") or "").lower()
            if any(kw in label for kw in CONTA_PROPRIA_KEYWORDS):
                matched.append({
                    "id": cat.get("id"),
                    "label": cat.get("nome"),
                    "is_cnpj_yes": any(kw in label for kw in CNPJ_KEYWORDS)
                                    and not any(h in label for h in SEM_CNPJ_HINTS),
                    "is_cnpj_no":  any(h in label for h in SEM_CNPJ_HINTS),
                })
        if matched:
            hits[cls_id] = matched
    return hits


def probe_table(table: int) -> dict | None:
    """Probe one table; return {"table": id, "matched_cls": {...}} if a
    CNPJ-aware classification is found, else None."""
    meta_url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{table}/metadados"
    try:
        meta = fetch(meta_url)
    except Exception as e:
        print(f"\n## Table {table} — METADATA FETCH FAILED: {e}\n")
        return None

    print("\n" + "=" * 70)
    print(f"## Table {table}")
    print("=" * 70)
    print(f"  nome: {meta.get('nome')}")
    print(f"  pesquisa: {meta.get('pesquisa')}")
    p = meta.get("periodicidade", {}) or {}
    print(f"  periodicidade: freq={p.get('frequencia')} "
          f"inicio={p.get('inicio')} fim={p.get('fim')}")

    classifications = meta.get("classificacoes", []) or []
    print(f"\n  Classifications ({len(classifications)}):")
    for cls in classifications:
        cats = cls.get("categorias", []) or []
        print(f"    [c{cls.get('id')}] {cls.get('nome')} — {len(cats)} categorias")

    # Look for any classification whose CATEGORIES mention conta-própria
    hits = find_conta_propria_categories(classifications)
    if not hits:
        print("  ⚠ No 'conta-própria' categories in any classification of this table.")
        return None

    print("\n  ✓ Found conta-própria categories:")
    cnpj_aware = False
    for cls_id, cats in hits.items():
        cls_name = next(
            (c.get("nome") for c in classifications if str(c.get("id")) == cls_id),
            f"c{cls_id}"
        )
        any_cnpj_yes = any(c["is_cnpj_yes"] for c in cats)
        any_cnpj_no  = any(c["is_cnpj_no"]  for c in cats)
        marker = " ★ CNPJ-AWARE" if (any_cnpj_yes and any_cnpj_no) else ""
        print(f"\n    Classification c{cls_id} — {cls_name}{marker}")
        # Full dump of this classification's categories
        all_cats = next((c.get("categorias") for c in classifications
                         if str(c.get("id")) == cls_id), [])
        matched_ids = {c["id"] for c in cats}
        print(f"    {'id':>10}  label")
        for c in all_cats:
            m = "★" if c.get("id") in matched_ids else " "
            cnpj_marker = ""
            label_l = (c.get("nome") or "").lower()
            if "cnpj" in label_l or "sem cnpj" in label_l or "sem cadastro" in label_l:
                cnpj_marker = "  [CNPJ]"
            print(f"    {c.get('id'):>10}  [{m}] {c.get('nome')}{cnpj_marker}")
        if any_cnpj_yes and any_cnpj_no:
            cnpj_aware = True

    if cnpj_aware:
        return {"table": table, "meta": meta, "hits": hits}
    return None


def sample_fetch(table: int, meta: dict, hits: dict[str, list[dict]]):
    """Fetch a small sample for the latest period at BR + SP."""
    periods_url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{table}/periodos"
    latest = fetch(periods_url)
    if not latest:
        print("\n  ⚠ Could not list periods for sample fetch.")
        return
    period = str(sorted([str(p.get("id")) for p in latest], reverse=True)[0])
    log.info("latest period for table %d: %s", table, period)

    head_var = None
    for v in meta.get("variaveis", []) or []:
        name = (v.get("nome") or "").lower()
        if ("pessoas" in name and "ocupadas" in name
                and "coeficiente" not in name and "distribuição" not in name):
            head_var = v.get("id")
            break
    if head_var is None and meta.get("variaveis"):
        head_var = meta["variaveis"][0].get("id")

    cls_to_query: dict[str, list[int]] = {}
    for cls_id, cats in hits.items():
        cat_ids = [c["id"] for c in cats if c["is_cnpj_yes"] or c["is_cnpj_no"]]
        if cat_ids:
            cls_to_query[cls_id] = cat_ids

    if head_var is None or not cls_to_query:
        return

    cls_path = "".join(
        f"/c{cls_id}/{','.join(str(c) for c in cats)}"
        for cls_id, cats in cls_to_query.items()
    )
    for level, codes_segment in [("n1", "all"), ("n3", "35")]:
        url = (f"{SIDRA_BASE}/t/{table}/{level}/{codes_segment}"
               f"/v/{head_var}/p/{period}{cls_path}")
        try:
            data = fetch(url)
        except Exception as e:
            print(f"\n  ⚠ Sample fetch failed for {level}: {e}")
            continue
        if not data or len(data) < 2:
            print(f"\n  ⚠ Empty response for {level}")
            continue
        header = data[0]
        body = data[1:]
        print(f"\n  ### Sample ({level} · period={period} · var={head_var})\n")
        key_cols = []
        for short, label in header.items():
            ll = label.lower()
            if any(s in ll for s in
                   ["valor", "(código)", "posição", "ocupação",
                    "brasil", "unidade", "trimestre", "ano"]):
                key_cols.append(short)
        if not key_cols:
            key_cols = list(header.keys())[:6]
        head_row = " | ".join(header[k] for k in key_cols)
        print(f"  | {head_row} |")
        print("  | " + " | ".join("---" for _ in key_cols) + " |")
        for r in body[:12]:
            row_cells = [str(r.get(k, "")) for k in key_cols]
            print("  | " + " | ".join(row_cells) + " |")


def main():
    tables = (
        [int(a) for a in sys.argv[1:]]
        if len(sys.argv) > 1 else DEFAULT_CANDIDATES
    )
    log.info("=" * 60)
    log.info("Probing %d SIDRA candidate tables for CNPJ classification", len(tables))
    log.info("=" * 60)

    winners = []
    for t in tables:
        result = probe_table(t)
        if result:
            winners.append(result)

    print("\n" + "=" * 70)
    print("## Summary\n")
    if not winners:
        print("  ⚠ None of the probed tables had a CNPJ-aware classification.")
        print("  Next steps:")
        print("    1. Inspect the dumps above for classifications matching")
        print("       'posição na ocupação' that may have CNPJ buried in")
        print("       category subnodes.")
        print("    2. Manually try a few more table IDs from the SIDRA catalog:")
        print("       https://sidra.ibge.gov.br/acervo (search 'PNAD Contínua')")
        print("    3. Or fall back to the microdata path (V4019 already available).")
        return

    print(f"  ✓ {len(winners)} CNPJ-aware table(s) found:")
    for w in winners:
        print(f"    - Table {w['table']}")
    print("\n  Sample fetches for each winner:\n")
    for w in winners:
        print("\n  " + "-" * 50)
        print(f"  Table {w['table']} sample:")
        sample_fetch(w["table"], w["meta"], w["hits"])

    print("\n## Next steps after picking the winner\n")
    print("  1. Note the table_id + the c<id> classification + the CNPJ category IDs.")
    print("  2. Add a new entry to etl/manifest.yaml using those exact IDs.")
    print("  3. Update dim_formality with 'conta_propria_cnpj' + 'conta_propria_sem_cnpj'.")
    print("  4. Run: python etl/fetch_sidra.py <new_manifest_key>")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        log.error("HTTP error: %s", e)
        sys.exit(1)
