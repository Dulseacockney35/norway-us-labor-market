"""
fetch_ssb.py
------------
Pull labor market data from Statistics Norway (SSB) API.

SSB API docs: https://data.ssb.no/api/v0/en/
The API uses POST requests with a JSON query body.
Responses come back in JSON-stat format, which we parse with pyjstat.
"""

import requests
from pyjstat import pyjstat
import pandas as pd
import json
import os

BASE_URL = "https://data.ssb.no/api/v0/en/table"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def get_table_metadata(table_id):
    """
    Fetch the available variables for an SSB table.
    Useful for debugging — call this if a query fails to see
    what variable codes the table actually accepts.
    """
    url = f"{BASE_URL}/{table_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def fetch_ssb_table(table_id, query):
    """
    Send a POST request to the SSB API and return a pandas DataFrame.

    Parameters:
        table_id: SSB table number (e.g., "09174")
        query: dict with the JSON query body
    """
    url = f"{BASE_URL}/{table_id}"
    response = requests.post(url, json=query, timeout=30)
    response.raise_for_status()

    # Save raw response to data/raw/
    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, f"ssb_{table_id}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"  Saved raw response to {raw_path}")

    # Parse JSON-stat format into a DataFrame using pyjstat
    dataset = pyjstat.Dataset.read(response.text)
    df = dataset.write("dataframe")
    # pyjstat returns a list of DataFrames in newer versions
    if isinstance(df, list):
        df = df[0]
    return df


def fetch_unemployment():
    """
    Table 08517: Unemployment rate (AKU Labour Force Survey), annual.
    Both sexes, ages 15-74. This is the standard internationally comparable measure.
    """
    print("Fetching Norway unemployment data (table 08517)...")

    query = {
        "query": [
            {
                "code": "Kjonn",
                "selection": {
                    "filter": "item",
                    "values": ["0"]        # Both sexes
                }
            },
            {
                "code": "Alder",
                "selection": {
                    "filter": "item",
                    "values": ["15-74"]
                }
            },
            {
                "code": "ContentsCode",
                "selection": {
                    "filter": "item",
                    "values": ["Prosent"]  # Unemployment rate as %
                }
            },
            {
                "code": "Tid",
                "selection": {
                    "filter": "all",
                    "values": ["*"]
                }
            }
        ],
        "response": {
            "format": "json-stat2"
        }
    }

    df = fetch_ssb_table("08517", query)
    # pyjstat columns: sex, age, contents, year, value

    df = df[df["year"] >= "2010"].copy()

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    out_path = os.path.join(PROCESSED_DIR, "norway_unemployment_raw.csv")
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} rows to {out_path}")
    return df


def fetch_wages():
    """
    Table 09174: Wages and salaries by industry (NACE codes), annual.
    Correct NACE codes verified from table metadata.
    """
    print("Fetching Norway wage data (table 09174)...")

    query = {
        "query": [
            {
                "code": "NACE",
                "selection": {
                    "filter": "item",
                    "values": [
                        "nr23_6",        # Total industry
                        "pub2X58_63",    # Information & communication (tech)
                        "pub2X69_75",    # Professional, scientific, technical
                    ]
                }
            },
            {
                "code": "ContentsCode",
                "selection": {
                    "filter": "item",
                    # Lonn = total wages (NOK million), Sysselsatte = employed (1000 persons)
                    # We fetch both so clean.py can compute average per-person wage
                    "values": ["Lonn", "Sysselsatte"]
                }
            },
            {
                "code": "Tid",
                "selection": {
                    "filter": "all",
                    "values": ["*"]
                }
            }
        ],
        "response": {
            "format": "json-stat2"
        }
    }

    df = fetch_ssb_table("09174", query)

    time_col = [c for c in df.columns if c.lower() in ("tid", "year", "time")][0]
    df = df[df[time_col] >= "2010"].copy()

    out_path = os.path.join(PROCESSED_DIR, "norway_wages_raw.csv")
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} rows to {out_path}")
    return df


def fetch_employment():
    """
    Table 09174: Employed persons by industry (NACE codes), annual.
    Same table as wages — different ContentsCode.
    """
    print("Fetching Norway employment by industry (table 09174)...")

    query = {
        "query": [
            {
                "code": "NACE",
                "selection": {
                    "filter": "item",
                    "values": [
                        "nr23_6",        # Total
                        "pub2X58_63",    # Information & communication
                        "nr23ind",       # Manufacturing
                        "pub2X64_66",    # Finance
                        "pub2X69_75",    # Professional/scientific/technical
                    ]
                }
            },
            {
                "code": "ContentsCode",
                "selection": {
                    "filter": "item",
                    "values": ["Sysselsatte"]  # Employed persons (1000 persons)
                }
            },
            {
                "code": "Tid",
                "selection": {
                    "filter": "all",
                    "values": ["*"]
                }
            }
        ],
        "response": {
            "format": "json-stat2"
        }
    }

    df = fetch_ssb_table("09174", query)

    time_col = [c for c in df.columns if c.lower() in ("tid", "year", "time")][0]
    df = df[df[time_col] >= "2010"].copy()

    out_path = os.path.join(PROCESSED_DIR, "norway_employment_raw.csv")
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} rows to {out_path}")
    return df


if __name__ == "__main__":
    print("=== Fetching SSB (Norway) data ===")
    try:
        fetch_unemployment()
        fetch_wages()
        fetch_employment()
        print("\nAll SSB data fetched successfully!")
    except requests.exceptions.HTTPError as e:
        print(f"\nAPI error: {e}")
        print("Tip: Use get_table_metadata(TABLE_ID) to inspect available variables.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        raise
