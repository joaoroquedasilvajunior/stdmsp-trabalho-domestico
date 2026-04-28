"""
fetch_ilostat.py
================

Pulls "Domestic workers by sex and status in employment" from ILOSTAT bulk
files and loads the LatAm comparator into `domestic_work.fact_intl`.

ILOSTAT exposes bulk CSV files at:
  https://rplumber.ilo.org/data/indicator/?id=DWAP_DWRK_SEX_EMP_NB_A&ref_area=...

We default to a curated comparator set (Brazil + Mexico headline, plus regional
peers) that maps onto Mayer's BR/MX comparative-politics framing.

Usage:
    python fetch_ilostat.py
"""

from __future__ import annotations

import os
import logging
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("fetch_ilostat")

sb: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
SCHEMA = sb.schema("domestic_work")

# Comparator set — Brazil + Mexico are required (Mayer's research focus); the rest
# give Latin America context.
COUNTRIES = {
    "BRA": ("Brasil",     "Brazil"),
    "MEX": ("México",     "Mexico"),
    "ARG": ("Argentina",  "Argentina"),
    "COL": ("Colômbia",   "Colombia"),
    "CHL": ("Chile",      "Chile"),
    "PER": ("Peru",       "Peru"),
    "URY": ("Uruguai",    "Uruguay"),
    "ECU": ("Equador",    "Ecuador"),
}

INDICATOR = "EMP_TEMP_SEX_OC2_NB_A"   # Employment by sex and 2-digit ISCO occupation, annual (thousands)
ISCO_DOMESTIC = "OC2_ISCO08_91"        # ISCO-08 sub-major group 91: cleaners and helpers (proxy for domestic workers in many countries)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
def fetch_indicator(country_iso3: str) -> pd.DataFrame:
    url = (
        "https://rplumber.ilo.org/data/indicator/"
        f"?id={INDICATOR}&ref_area={country_iso3}&format=.csv"
    )
    log.info("fetch: %s", url)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    return df


def upsert_dim_time_year(year: int) -> int:
    payload = {"year": year, "quarter": None, "period_code": str(year)}
    res = SCHEMA.table("dim_time").upsert(payload, on_conflict="period_code").execute()
    return res.data[0]["time_id"]


def main() -> None:
    payload = []
    for iso3, (name_pt, name_en) in COUNTRIES.items():
        try:
            df = fetch_indicator(iso3)
        except Exception as e:
            log.warning("skip %s: %s", iso3, e)
            continue

        # Filter to ISCO 91 + total sex, then keep latest 15 years
        f = df[(df.get("classif1", "") == ISCO_DOMESTIC) & (df.get("sex", "") == "SEX_T")]
        f = f.sort_values("time").tail(15)
        for _, r in f.iterrows():
            try:
                year = int(r["time"])
                value = float(r["obs_value"])
            except (ValueError, KeyError):
                continue
            payload.append({
                "time_id": upsert_dim_time_year(year),
                "country_iso3": iso3,
                "country_pt": name_pt,
                "country_en": name_en,
                "domestic_workers_thousands": value,
                "pct_of_employed_women": None,        # second pass with ratio indicator
                "pct_informal": None,
                "source": "ILOSTAT",
            })

    if not payload:
        log.error("no rows fetched — check network and indicator codes")
        return

    for i in range(0, len(payload), 500):
        chunk = payload[i:i+500]
        SCHEMA.table("fact_intl").upsert(
            chunk,
            on_conflict="time_id,country_iso3,source",
        ).execute()
    log.info("upserted %d rows into fact_intl", len(payload))


if __name__ == "__main__":
    main()
