# Fetches labor market data from Statistics Norway (SSB) API
# Docs: https://data.ssb.no/api/v0/en/
# SSB uses POST requests with a JSON body — responses are in JSON-stat format

import requests
from pyjstat import pyjstat
import pandas as pd
import json
import os

BASE_URL = "https://data.ssb.no/api/v0/en/table"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def get_table_metadata(table_id):
    """Helper to check what variable codes a table accepts — useful when a query returns 400."""
    url = f"{BASE_URL}/{table_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def fetch_ssb_table(table_id, query):
    """POST to SSB API and return a DataFrame. Saves raw JSON to data/raw/ for reference."""
    url = f"{BASE_URL}/{table_id}"
    response = requests.post(url, json=query, timeout=30)
    response.raise_for_status()

    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, f"ssb_{table_id}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"  Saved raw response to {raw_path}")

    dataset = pyjstat.Dataset.read(response.text)
    df = dataset.write("dataframe")
    # newer pyjstat versions return a list instead of a single DataFrame
    if isinstance(df, list):
        df = df[0]
    return df


def fetch_unemployment():
    """
    Table 08517: AKU Labour Force Survey unemployment rate, annual.
    Using AKU (not NAV registered) because it's the internationally comparable measure.
    """
    print("Fetching Norway unemployment data (table 08517)...")

    query = {
        "query": [
            {
                "code": "Kjonn",
                "selection": {"filter": "item", "values": ["0"]}  # both sexes
            },
            {
                "code": "Alder",
                "selection": {"filter": "item", "values": ["15-74"]}
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Prosent"]}  # rate as %, not headcount
            },
            {
                "code": "Tid",
                "selection": {"filter": "all", "values": ["*"]}
            }
        ],
        "response": {"format": "json-stat2"}
    }

    df = fetch_ssb_table("08517", query)
    df = df[df["year"] >= "2010"].copy()

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    out_path = os.path.join(PROCESSED_DIR, "norway_unemployment_raw.csv")
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} rows to {out_path}")
    return df


def fetch_wages():
    """
    Table 09174: Total wages (NOK million) and employment (1000 persons) by industry.
    Fetching both so clean.py can compute average per-person wage = Lonn / Sysselsatte * 1000
    NACE codes verified by calling get_table_metadata("09174") first.
    """
    print("Fetching Norway wage data (table 09174)...")

    query = {
        "query": [
            {
                "code": "NACE",
                "selection": {
                    "filter": "item",
                    "values": [
                        "nr23_6",      # total economy
                        "pub2X58_63",  # information & communication
                        "pub2X69_75",  # professional/scientific/technical
                    ]
                }
            },
            {
                "code": "ContentsCode",
                "selection": {
                    "filter": "item",
                    "values": ["Lonn", "Sysselsatte"]
                }
            },
            {
                "code": "Tid",
                "selection": {"filter": "all", "values": ["*"]}
            }
        ],
        "response": {"format": "json-stat2"}
    }

    df = fetch_ssb_table("09174", query)
    time_col = [c for c in df.columns if c.lower() in ("tid", "year", "time")][0]
    df = df[df[time_col] >= "2010"].copy()

    out_path = os.path.join(PROCESSED_DIR, "norway_wages_raw.csv")
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} rows to {out_path}")
    return df


def fetch_employment():
    """Table 09174 again, but pulling Sysselsatte for more industry breakdowns."""
    print("Fetching Norway employment by industry (table 09174)...")

    query = {
        "query": [
            {
                "code": "NACE",
                "selection": {
                    "filter": "item",
                    "values": [
                        "nr23_6",      # total
                        "pub2X58_63",  # ICT
                        "nr23ind",     # manufacturing
                        "pub2X64_66",  # finance
                        "pub2X69_75",  # professional services
                    ]
                }
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Sysselsatte"]}
            },
            {
                "code": "Tid",
                "selection": {"filter": "all", "values": ["*"]}
            }
        ],
        "response": {"format": "json-stat2"}
    }

    df = fetch_ssb_table("09174", query)
    time_col = [c for c in df.columns if c.lower() in ("tid", "year", "time")][0]
    df = df[df[time_col] >= "2010"].copy()

    out_path = os.path.join(PROCESSED_DIR, "norway_employment_raw.csv")
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} rows to {out_path}")
    return df


if __name__ == "__main__":
    print("Fetching SSB (Norway) data...")
    try:
        fetch_unemployment()
        fetch_wages()
        fetch_employment()
        print("\nDone!")
    except requests.exceptions.HTTPError as e:
        print(f"\nAPI error: {e}")
        print("Check variable codes with get_table_metadata(TABLE_ID)")
    except Exception as e:
        print(f"\nError: {e}")
        raise
