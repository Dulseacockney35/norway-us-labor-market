"""
clean.py
--------
Take the raw CSVs from data/processed/ and produce clean,
comparable datasets for Norway and the US.

Main tasks:
  1. Standardize to annual data (average monthly observations)
  2. Convert wages to comparable units (annual USD, PPP-adjusted)
  3. Map industry codes to a common schema
  4. Calculate employment as % of total workforce
  5. Document missing data
"""

import pandas as pd
import numpy as np
import os

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

# OECD PPP conversion factors for Norway (NOK per 1 international USD)
# Source: OECD.stat, "Purchasing Power Parities for GDP"
# These convert NOK into internationally comparable dollars.
# To convert a NOK wage to PPP USD: divide by the PPP factor.
PPP_FACTORS = {
    2010: 9.73, 2011: 9.96, 2012: 10.14, 2013: 10.24, 2014: 10.31,
    2015: 10.32, 2016: 10.41, 2017: 10.50, 2018: 10.60, 2019: 10.68,
    2020: 10.73, 2021: 10.86, 2022: 11.05, 2023: 11.21, 2024: 11.35,
}

# Map SSB NACE codes to a common industry label
# Note: NACE J (Info & Communication) is our best proxy for US NAICS 51 (Information).
# It includes some publishing the US sector excludes — documented as a limitation.
NACE_TO_COMMON = {
    "00-99": "Total",
    "J":     "Technology",
    "C":     "Manufacturing",
    "K":     "Finance",
    "G-I":   "Trade & Services",
    "M":     "Professional Services",
}


def clean_norway_unemployment():
    """
    Load raw Norway unemployment CSV and return a clean annual series.
    SSB data is monthly; we average to get annual rates.
    """
    path = os.path.join(PROCESSED_DIR, "norway_unemployment_raw.csv")
    if not os.path.exists(path):
        print(f"  Missing: {path} — run fetch_ssb.py first (or generate_sample_data.py)")
        return None

    df = pd.read_csv(path)
    print(f"  Norway unemployment raw: {df.shape}")

    # pyjstat columns for table 08517: sex, age, contents, year, value
    # Data is already annual, so no aggregation needed
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["unemployment_rate"] = pd.to_numeric(df["value"], errors="coerce")

    # Data is already annual — just select year and rate columns
    annual = df[["year", "unemployment_rate"]].copy()
    annual["country"] = "Norway"
    annual["year"] = annual["year"].astype(int)
    annual = annual[annual["year"].between(2010, 2024)]

    missing = annual["unemployment_rate"].isna().sum()
    if missing > 0:
        print(f"  Note: {missing} missing unemployment values in Norway data")

    return annual


def clean_us_unemployment():
    """
    Load raw US BLS unemployment CSV and return a clean annual series.
    BLS data is monthly; we average to annual.
    """
    path = os.path.join(PROCESSED_DIR, "us_unemployment_raw.csv")
    if not os.path.exists(path):
        print(f"  Missing: {path} — run fetch_bls.py first (or generate_sample_data.py)")
        return None

    df = pd.read_csv(path)
    print(f"  US unemployment raw: {df.shape}")

    annual = (
        df.groupby("year")["unemployment_rate"]
        .mean()
        .reset_index()
    )
    annual["country"] = "United States"
    annual = annual[annual["year"].between(2010, 2024)]

    return annual


def clean_wages():
    """
    Load Norway and US wage data and produce a comparable annual wage series.

    Norway: monthly wages in NOK → annualize → convert to PPP USD
    US: hourly wages in USD → annualize (× 2,080 hours/year)
    """
    rows = []

    # --- Norway wages ---
    # Table 09174 returns total wage bill (NOK million) and employment (1000 persons).
    # Average annual wage per person = (Lonn_NOK_million / Sysselsatte_thousands) * 1000
    path_no = os.path.join(PROCESSED_DIR, "norway_wages_raw.csv")
    if os.path.exists(path_no):
        df_no = pd.read_csv(path_no)
        print(f"  Norway wages raw: {df_no.shape}")
        # pyjstat columns: industry, contents, year, value

        # Map SSB English industry labels to our common names
        industry_label_map = {
            "Total industry":                                        "Total",
            "Information and communcation":                          "Technology",   # note SSB typo
            "Information and communication":                         "Technology",
            "Manufacturing":                                         "Manufacturing",
            "Financial and insurance activities":                    "Finance",
            "Professional, scientific and and technical activities": "Professional Services",
        }

        # Pivot so Lonn and Sysselsatte are separate columns
        df_no["value"] = pd.to_numeric(df_no["value"], errors="coerce")
        pivot = df_no.pivot_table(
            index=["industry", "year"],
            columns="contents",
            values="value",
            aggfunc="mean"
        ).reset_index()

        # Rename columns — pyjstat uses full English descriptions
        wage_col  = [c for c in pivot.columns if "wages" in c.lower() or "lonn" in c.lower()][0]
        emp_col   = [c for c in pivot.columns if "employed" in c.lower() or "syssels" in c.lower()][0]

        pivot["wage_annual_nok"] = (pivot[wage_col] / pivot[emp_col]) * 1_000_000 / 1_000
        # Lonn (NOK million) / Sysselsatte (1000 persons) * 1e6 / 1e3 = NOK per person per year

        for _, row in pivot.iterrows():
            year = int(row["year"])
            ppp = PPP_FACTORS.get(year, 10.5)
            wage_ppp_usd = row["wage_annual_nok"] / ppp
            industry_name = industry_label_map.get(row["industry"], row["industry"])

            rows.append({
                "country": "Norway",
                "year": year,
                "industry_code": row["industry"],
                "industry": industry_name,
                "wage_local": round(row["wage_annual_nok"], 0),
                "wage_local_currency": "NOK_annual",
                "wage_annual_usd_ppp": round(wage_ppp_usd, 0),
            })
    else:
        print(f"  Missing Norway wages — skipping")

    # --- US wages ---
    path_us = os.path.join(PROCESSED_DIR, "us_it_wages_raw.csv")
    if os.path.exists(path_us):
        df_us = pd.read_csv(path_us)
        print(f"  US wages raw: {df_us.shape}")

        annual_us = (
            df_us.groupby("year")["hourly_wage_usd"]
            .mean()
            .reset_index()
        )

        for _, row in annual_us.iterrows():
            # Annualize: 52 weeks × 40 hours = 2,080 hours/year
            annual_wage = row["hourly_wage_usd"] * 2080

            rows.append({
                "country": "United States",
                "year": int(row["year"]),
                "industry_code": "51",  # NAICS Information sector
                "industry": "Technology",
                "wage_local": row["hourly_wage_usd"],
                "wage_local_currency": "USD_hourly",
                "wage_annual_usd_ppp": round(annual_wage, 0),
            })
    else:
        print(f"  Missing US wages — skipping")

    if rows:
        df = pd.DataFrame(rows)
        df = df[df["year"].between(2010, 2024)]
        return df
    return None


def clean_employment():
    """
    Load Norway and US employment data.
    Calculate tech employment as % of total workforce.
    """
    rows = []

    # Map pyjstat English industry labels to our common names
    industry_label_map = {
        "Total industry":                                        "Total",
        "Information and communcation":                          "Technology",
        "Information and communication":                         "Technology",
        "Manufacturing":                                         "Manufacturing",
        "Financial and insurance activities":                    "Finance",
        "Professional, scientific and and technical activities": "Professional Services",
    }

    # --- Norway ---
    path_no = os.path.join(PROCESSED_DIR, "norway_employment_raw.csv")
    if os.path.exists(path_no):
        df_no = pd.read_csv(path_no)
        print(f"  Norway employment raw: {df_no.shape}")
        # pyjstat columns: industry, contents, year, value
        # Sysselsatte = employed persons (1000 persons)

        df_no["employment_thousands"] = pd.to_numeric(df_no["value"], errors="coerce")

        annual_no = (
            df_no.groupby(["year", "industry"])["employment_thousands"]
            .mean()
            .reset_index()
        )

        # Get total employment for each year to compute percentages
        total_label = "Total industry"
        total_no = annual_no[annual_no["industry"] == total_label][["year", "employment_thousands"]].rename(
            columns={"employment_thousands": "total_employment"}
        )

        annual_no = annual_no.merge(total_no, on="year", how="left")
        annual_no["employment_pct"] = (annual_no["employment_thousands"] / annual_no["total_employment"] * 100).round(2)

        for _, row in annual_no.iterrows():
            rows.append({
                "country": "Norway",
                "year": int(row["year"]),
                "industry_code": row["industry"],
                "industry": industry_label_map.get(row["industry"], row["industry"]),
                "employment_count": int(row["employment_thousands"] * 1000) if pd.notna(row["employment_thousands"]) else None,
                "employment_pct": row["employment_pct"],
            })

    # --- US employment ---
    path_us = os.path.join(PROCESSED_DIR, "us_it_employment_raw.csv")
    if os.path.exists(path_us):
        df_us = pd.read_csv(path_us)
        print(f"  US employment raw: {df_us.shape}")

        annual_us = (
            df_us.groupby("year")["it_employment_thousands"]
            .mean()
            .reset_index()
        )

        # US total employment (approximate, in thousands) — from BLS CES series
        # We'll use the value from the sample data or hardcode a reasonable total
        # These are approximate total nonfarm employment figures
        us_total_employment = {
            2010: 129818, 2011: 131148, 2012: 133721, 2013: 136367, 2014: 138940,
            2015: 141827, 2016: 144340, 2017: 146609, 2018: 148910, 2019: 151000,
            2020: 142205, 2021: 144476, 2022: 151858, 2023: 155770, 2024: 157500,
        }

        for _, row in annual_us.iterrows():
            year = int(row["year"])
            total = us_total_employment.get(year, 150000)
            pct = (row["it_employment_thousands"] / total * 100).round(2)

            rows.append({
                "country": "United States",
                "year": year,
                "industry_code": "51",
                "industry": "Technology",
                "employment_count": row["it_employment_thousands"] * 1000,
                "employment_pct": pct,
            })

    if rows:
        df = pd.DataFrame(rows)
        df = df[df["year"].between(2010, 2024)]
        return df
    return None


def run_all():
    """Run all cleaning steps and save outputs."""
    print("=== Cleaning data ===\n")

    # Unemployment
    no_unemp = clean_norway_unemployment()
    us_unemp = clean_us_unemployment()
    if no_unemp is not None and us_unemp is not None:
        combined_unemp = pd.concat([no_unemp, us_unemp], ignore_index=True)
        path = os.path.join(PROCESSED_DIR, "unemployment_clean.csv")
        combined_unemp.to_csv(path, index=False)
        print(f"  -> Saved combined unemployment to {path}\n")

    # Wages
    wages = clean_wages()
    if wages is not None:
        path = os.path.join(PROCESSED_DIR, "wages_clean.csv")
        wages.to_csv(path, index=False)
        print(f"  -> Saved wages to {path}\n")

    # Employment
    employment = clean_employment()
    if employment is not None:
        path = os.path.join(PROCESSED_DIR, "employment_clean.csv")
        employment.to_csv(path, index=False)
        print(f"  -> Saved employment to {path}\n")

    print("Cleaning complete!")


if __name__ == "__main__":
    run_all()
