# Fetches US labor market data from the Bureau of Labor Statistics (BLS) API v2
# Docs: https://www.bls.gov/developers/
# Requires a free API key in .env as BLS_API_KEY

import requests
import pandas as pd
import json
import os
from dotenv import load_dotenv

load_dotenv()

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_API_KEY = os.getenv("BLS_API_KEY", "")
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

# BLS series IDs we need
# Verified against the BLS API — CES50 = Information sector (NAICS 51)
SERIES = {
    "it_employment":   "CES5000000001",  # Information sector employment (thousands)
    "it_wages":        "CES5000000003",  # Information sector avg hourly wages (USD)
    "unemployment":    "LNS14000000",    # National unemployment rate (%)
    "youth_unemployment": "LNS14024887", # Unemployment, 20-24 years
}


def fetch_bls_series(series_ids, start_year=2010, end_year=2024):
    """
    Fetch one or more BLS series for a given year range.

    Returns a dict: {series_id: DataFrame}
    """
    if not BLS_API_KEY:
        print("Warning: No BLS_API_KEY found in .env — using unauthenticated API (limited to 25 req/day)")

    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
        "registrationkey": BLS_API_KEY,
    }

    response = requests.post(BLS_API_URL, json=payload, timeout=30)
    response.raise_for_status()

    data = response.json()

    if data.get("status") != "REQUEST_SUCCEEDED":
        print(f"BLS API warning: {data.get('message', 'Unknown error')}")

    # Save raw response
    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, "bls_raw.json")
    with open(raw_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved raw response to {raw_path}")

    result = {}
    for series in data.get("Results", {}).get("series", []):
        sid = series["seriesID"]
        rows = []
        for obs in series["data"]:
            rows.append({
                "year": int(obs["year"]),
                "period": obs["period"],
                "period_name": obs["periodName"],
                "value": float(obs["value"]) if obs["value"] != "-" else None,
            })
        if rows:
            result[sid] = pd.DataFrame(rows)
            print(f"  {sid}: {len(rows)} observations")
        else:
            print(f"  {sid}: 0 observations (series not found — check series ID)")

    return result


def fetch_all():
    """
    Fetch all the series we need and save processed CSVs.
    """
    print("=== Fetching BLS (US) data ===")

    all_series = list(SERIES.values())
    series_data = fetch_bls_series(all_series, start_year=2010, end_year=2024)

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # --- Unemployment ---
    uid = SERIES["unemployment"]
    if uid in series_data:
        df_unemp = series_data[uid].copy()
        # Keep only monthly data (period M01-M12), not annual averages (M13)
        df_unemp = df_unemp[df_unemp["period"] != "M13"].copy()
        df_unemp["month"] = df_unemp["period"].str.replace("M", "").astype(int)
        df_unemp = df_unemp[["year", "month", "value"]].rename(columns={"value": "unemployment_rate"})
        path = os.path.join(PROCESSED_DIR, "us_unemployment_raw.csv")
        df_unemp.to_csv(path, index=False)
        print(f"  Saved unemployment: {len(df_unemp)} rows to {path}")

    # --- IT Employment ---
    eid = SERIES["it_employment"]
    if eid in series_data:
        df_emp = series_data[eid].copy()
        df_emp = df_emp[df_emp["period"] != "M13"].copy()
        df_emp["month"] = df_emp["period"].str.replace("M", "").astype(int)
        # BLS IT employment is in thousands
        df_emp = df_emp[["year", "month", "value"]].rename(columns={"value": "it_employment_thousands"})
        path = os.path.join(PROCESSED_DIR, "us_it_employment_raw.csv")
        df_emp.to_csv(path, index=False)
        print(f"  Saved IT employment: {len(df_emp)} rows to {path}")

    # --- IT Wages ---
    wid = SERIES["it_wages"]
    if wid in series_data:
        df_wages = series_data[wid].copy()
        df_wages = df_wages[df_wages["period"] != "M13"].copy()
        df_wages["month"] = df_wages["period"].str.replace("M", "").astype(int)
        # BLS wages are average hourly; we'll annualize later in clean.py
        df_wages = df_wages[["year", "month", "value"]].rename(columns={"value": "hourly_wage_usd"})
        path = os.path.join(PROCESSED_DIR, "us_it_wages_raw.csv")
        df_wages.to_csv(path, index=False)
        print(f"  Saved IT wages: {len(df_wages)} rows to {path}")

    print("\nAll BLS data fetched successfully!")
    return series_data


if __name__ == "__main__":
    fetch_all()
