"""
analyze.py
----------
Run the SQL queries from sql/queries.sql and return DataFrames.
These functions are used by the dashboard and the exploration notebook.

Can also be run standalone to print results to the terminal.
"""

import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def get_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "norway_us_labor")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    conn_str = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return create_engine(conn_str)


def query_tech_employment_share(engine):
    """
    Tech employment as % of total workforce over time, with YoY change.
    """
    sql = """
        SELECT
            e.year,
            c.country_name,
            e.employment_pct,
            ROUND(
                e.employment_pct - LAG(e.employment_pct) OVER (
                    PARTITION BY e.country_code ORDER BY e.year
                ), 2
            ) AS yoy_change
        FROM employment e
        JOIN countries c ON e.country_code = c.country_code
        JOIN industries i ON e.industry_id = i.industry_id
        WHERE i.common_name = 'Technology'
        ORDER BY e.year, c.country_name
    """
    return pd.read_sql(sql, engine)


def query_wage_comparison(engine):
    """Tech wages (PPP-adjusted annual USD) by country and year."""
    sql = """
        SELECT
            w.year,
            c.country_name,
            w.wage_annual_usd_ppp,
            ROUND(
                w.wage_annual_usd_ppp / AVG(w.wage_annual_usd_ppp) OVER (PARTITION BY w.year) * 100
            , 1) AS index_vs_average
        FROM wages w
        JOIN countries c ON w.country_code = c.country_code
        JOIN industries i ON w.industry_id = i.industry_id
        WHERE i.common_name = 'Technology'
        ORDER BY w.year, c.country_name
    """
    return pd.read_sql(sql, engine)


def query_unemployment(engine, start_year=2010, end_year=2024):
    """Unemployment rates over time for both countries."""
    sql = """
        SELECT
            u.year,
            c.country_name,
            u.unemployment_rate
        FROM unemployment u
        JOIN countries c ON u.country_code = c.country_code
        WHERE u.year BETWEEN :start_year AND :end_year
          AND u.age_group = 'total'
          AND u.month IS NULL
        ORDER BY u.year, c.country_name
    """
    return pd.read_sql(text(sql), engine, params={"start_year": start_year, "end_year": end_year})


def query_industry_composition(engine, year=2023):
    """Industry composition for a given year (both countries)."""
    sql = """
        SELECT
            c.country_name,
            i.common_name AS industry,
            e.employment_pct
        FROM employment e
        JOIN countries c ON e.country_code = c.country_code
        JOIN industries i ON e.industry_id = i.industry_id
        WHERE e.year = :year
          AND i.common_name != 'Total'
        ORDER BY c.country_name, e.employment_pct DESC
    """
    return pd.read_sql(text(sql), engine, params={"year": year})


def query_tech_wage_premium(engine):
    """
    Tech wage premium: how much more do tech workers earn vs. the national average?
    """
    sql = """
        SELECT
            t.year,
            c.country_name,
            t.wage_annual_usd_ppp AS tech_wage_ppp,
            avg_all.wage_annual_usd_ppp AS avg_wage_ppp,
            ROUND(t.wage_annual_usd_ppp / avg_all.wage_annual_usd_ppp, 2) AS tech_premium_ratio
        FROM wages t
        JOIN wages avg_all
            ON t.country_code = avg_all.country_code
            AND t.year = avg_all.year
        JOIN countries c ON t.country_code = c.country_code
        JOIN industries it ON t.industry_id = it.industry_id
        JOIN industries ia ON avg_all.industry_id = ia.industry_id
        WHERE it.common_name = 'Technology'
          AND ia.common_name = 'Total'
        ORDER BY t.year, c.country_name
    """
    return pd.read_sql(sql, engine)


# ── CSV-based versions (for dashboard without database) ─────────────────────

def load_unemployment_csv():
    path = os.path.join(PROCESSED_DIR, "unemployment_clean.csv")
    return pd.read_csv(path)


def load_wages_csv():
    path = os.path.join(PROCESSED_DIR, "wages_clean.csv")
    return pd.read_csv(path)


def load_employment_csv():
    path = os.path.join(PROCESSED_DIR, "employment_clean.csv")
    return pd.read_csv(path)


if __name__ == "__main__":
    engine = get_engine()
    try:
        print("=== Tech Employment Share ===")
        df = query_tech_employment_share(engine)
        print(df.to_string(index=False))

        print("\n=== Wage Comparison ===")
        df = query_wage_comparison(engine)
        print(df.to_string(index=False))

        print("\n=== Tech Wage Premium ===")
        df = query_tech_wage_premium(engine)
        print(df.to_string(index=False))
    except Exception as e:
        print(f"Database not available: {e}")
        print("Use load_*_csv() functions instead, or run generate_sample_data.py first.")
