"""
generate_sample_data.py
-----------------------
Creates realistic sample CSVs in data/processed/ so you can run the
dashboard and explore the analysis before setting up live API access.

The numbers here are based on publicly available statistics
(OECD, SSB, BLS publications). Use the real fetch scripts to replace
these with actual API data once you have your BLS API key.

Run:  python generate_sample_data.py
"""

import pandas as pd
import numpy as np
import os

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "data", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

YEARS = list(range(2010, 2025))

# ── PPP factors (NOK per 1 international USD), OECD ─────────────────────────
PPP = {
    2010: 9.73, 2011: 9.96, 2012: 10.14, 2013: 10.24, 2014: 10.31,
    2015: 10.32, 2016: 10.41, 2017: 10.50, 2018: 10.60, 2019: 10.68,
    2020: 10.73, 2021: 10.86, 2022: 11.05, 2023: 11.21, 2024: 11.35,
}


def make_unemployment():
    """
    Annual average unemployment rates (%).
    Norway: mild, less affected by COVID.
    US: higher baseline, dramatic COVID spike.
    """
    norway_rates = [3.6, 3.3, 3.2, 3.5, 3.5, 4.4, 4.7, 4.2, 3.8, 3.7,
                    4.6, 4.4, 3.2, 1.8, 2.0]
    us_rates     = [9.6, 8.9, 8.1, 7.4, 6.2, 5.3, 4.9, 4.4, 3.9, 3.7,
                    8.1, 5.4, 3.6, 3.6, 4.0]

    rows = []
    for y, no, us in zip(YEARS, norway_rates, us_rates):
        rows.append({"year": y, "country": "Norway",        "unemployment_rate": no})
        rows.append({"year": y, "country": "United States", "unemployment_rate": us})

    df = pd.DataFrame(rows)
    path = os.path.join(PROCESSED_DIR, "unemployment_clean.csv")
    df.to_csv(path, index=False)
    print(f"Saved unemployment sample: {path}")
    return df


def make_wages():
    """
    Tech sector wages.
    Norway: monthly NOK → annualized → PPP-adjusted USD.
    US: hourly USD → annualized (× 2,080 hrs).

    Reality check: Norwegian tech wages (PPP) are competitive with US
    mid-tier but trail US senior-heavy averages. This is itself a finding.
    """
    # Norway monthly wages in NOK (Information & Communication, NACE J)
    norway_monthly_nok = [
        51000, 53500, 55000, 57000, 58500, 58000, 58000, 60000,
        62000, 64000, 65000, 67000, 70000, 73000, 76000
    ]
    # US average hourly wage (IT sector, BLS CEU5051000003)
    us_hourly_usd = [
        36.94, 38.03, 39.06, 40.00, 41.35, 43.13, 44.52, 46.24,
        48.41, 50.87, 53.74, 56.20, 58.50, 59.62, 60.83
    ]

    rows = []
    for i, year in enumerate(YEARS):
        nok_annual = norway_monthly_nok[i] * 12
        ppp_usd = nok_annual / PPP[year]
        rows.append({
            "country": "Norway",
            "year": year,
            "industry_code": "J",
            "industry": "Technology",
            "wage_local": norway_monthly_nok[i],
            "wage_local_currency": "NOK_monthly",
            "wage_annual_usd_ppp": round(ppp_usd, 0),
        })

        us_annual = us_hourly_usd[i] * 2080
        rows.append({
            "country": "United States",
            "year": year,
            "industry_code": "51",
            "industry": "Technology",
            "wage_local": us_hourly_usd[i],
            "wage_local_currency": "USD_hourly",
            "wage_annual_usd_ppp": round(us_annual, 0),
        })

    # Add "Total Economy" wages for wage-premium comparison
    norway_total_monthly_nok = [
        38500, 40000, 41500, 43000, 44000, 44500, 45000, 46500,
        48000, 50000, 51000, 53000, 56000, 59000, 61000
    ]
    us_total_hourly_usd = [
        22.70, 23.24, 23.83, 24.31, 24.87, 25.46, 25.93, 26.42,
        27.16, 27.90, 29.36, 30.96, 32.59, 33.87, 35.05
    ]
    for i, year in enumerate(YEARS):
        nok_annual = norway_total_monthly_nok[i] * 12
        ppp_usd = nok_annual / PPP[year]
        rows.append({
            "country": "Norway",
            "year": year,
            "industry_code": "00-99",
            "industry": "Total",
            "wage_local": norway_total_monthly_nok[i],
            "wage_local_currency": "NOK_monthly",
            "wage_annual_usd_ppp": round(ppp_usd, 0),
        })
        us_annual = us_total_hourly_usd[i] * 2080
        rows.append({
            "country": "United States",
            "year": year,
            "industry_code": "00",
            "industry": "Total",
            "wage_local": us_total_hourly_usd[i],
            "wage_local_currency": "USD_hourly",
            "wage_annual_usd_ppp": round(us_annual, 0),
        })

    df = pd.DataFrame(rows)
    path = os.path.join(PROCESSED_DIR, "wages_clean.csv")
    df.to_csv(path, index=False)
    print(f"Saved wages sample: {path}")
    return df


def make_employment():
    """
    Employment counts and % of workforce for Tech and other industries.
    Norway figures in thousands of persons (SSB).
    US IT employment in thousands (BLS CES5051000001).
    """
    # Norway: tech (NACE J) employment, thousands
    no_tech = [92, 95, 100, 103, 108, 111, 113, 116, 121, 126,
               130, 135, 141, 148, 152]
    # Norway total employment, thousands
    no_total = [2450, 2490, 2520, 2540, 2560, 2560, 2550, 2570,
                2600, 2640, 2590, 2630, 2680, 2720, 2740]
    # US IT employment, thousands
    us_tech = [2700, 2750, 2830, 2900, 2990, 3120, 3220, 3310,
               3440, 3570, 3480, 3620, 3890, 3940, 3850]
    # US total nonfarm employment, thousands
    us_total = [129818, 131148, 133721, 136367, 138940, 141827, 144340,
                146609, 148910, 151000, 142205, 144476, 151858, 155770, 157500]

    rows = []
    industries = [
        # (code, name, no_share, us_share)  shares as % of total
        ("J",   "Technology",          None, None),  # filled from no_tech/us_tech
        ("C",   "Manufacturing",       [11.2,11.0,10.8,10.6,10.3,10.1,9.9,9.8,9.7,9.6,9.5,9.4,9.3,9.2,9.1],
                                       [8.4,8.3,8.3,8.3,8.3,8.4,8.4,8.5,8.5,8.5,8.2,8.1,8.3,8.3,8.2]),
        ("K",   "Finance",             [3.0,3.1,3.1,3.2,3.2,3.2,3.2,3.2,3.2,3.2,3.1,3.1,3.2,3.2,3.2],
                                       [5.8,5.8,5.7,5.7,5.7,5.7,5.7,5.7,5.7,5.7,5.6,5.6,5.6,5.5,5.5]),
        ("G-I", "Trade & Services",    [20.1,20.2,20.3,20.4,20.5,20.5,20.5,20.5,20.5,20.5,19.8,20.1,20.3,20.4,20.4],
                                       [14.5,14.4,14.4,14.4,14.3,14.3,14.2,14.2,14.1,14.1,13.8,13.9,14.1,14.0,14.0]),
    ]

    for i, year in enumerate(YEARS):
        # Norway tech
        tech_pct_no = (no_tech[i] / no_total[i] * 100)
        rows.append({
            "country": "Norway", "year": year,
            "industry_code": "J", "industry": "Technology",
            "employment_count": no_tech[i] * 1000,
            "employment_pct": round(tech_pct_no, 2),
        })
        rows.append({
            "country": "Norway", "year": year,
            "industry_code": "00-99", "industry": "Total",
            "employment_count": no_total[i] * 1000,
            "employment_pct": 100.0,
        })

        # US tech
        tech_pct_us = (us_tech[i] / us_total[i] * 100)
        rows.append({
            "country": "United States", "year": year,
            "industry_code": "51", "industry": "Technology",
            "employment_count": us_tech[i] * 1000,
            "employment_pct": round(tech_pct_us, 2),
        })
        rows.append({
            "country": "United States", "year": year,
            "industry_code": "00", "industry": "Total",
            "employment_count": us_total[i] * 1000,
            "employment_pct": 100.0,
        })

        # Other industries
        for code, name, no_shares, us_shares in industries:
            if code == "J":
                continue
            if no_shares:
                rows.append({
                    "country": "Norway", "year": year,
                    "industry_code": code, "industry": name,
                    "employment_count": int(no_total[i] * no_shares[i] / 100 * 1000),
                    "employment_pct": no_shares[i],
                })
            if us_shares:
                rows.append({
                    "country": "United States", "year": year,
                    "industry_code": code, "industry": name,
                    "employment_count": int(us_total[i] * us_shares[i] / 100 * 1000),
                    "employment_pct": us_shares[i],
                })

    df = pd.DataFrame(rows)
    path = os.path.join(PROCESSED_DIR, "employment_clean.csv")
    df.to_csv(path, index=False)
    print(f"Saved employment sample: {path}")
    return df


if __name__ == "__main__":
    print("Generating sample data...\n")
    make_unemployment()
    make_wages()
    make_employment()
    print("\nDone! Sample CSVs are in data/processed/")
    print("Run: streamlit run app/dashboard.py")
