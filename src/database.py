"""
database.py
-----------
Create PostgreSQL tables and load cleaned CSVs into the database.

Requires PostgreSQL running locally and a .env file with DB credentials.
Run create_tables.sql first, then this script to load data.

Usage:
    python src/database.py
"""

import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
SQL_DIR = os.path.join(os.path.dirname(__file__), "..", "sql")


def get_engine():
    """Create a SQLAlchemy engine from .env credentials."""
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "norway_us_labor")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")

    conn_str = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    engine = create_engine(conn_str)
    return engine


def create_tables(engine):
    """Run create_tables.sql to set up the schema."""
    sql_path = os.path.join(SQL_DIR, "create_tables.sql")
    with open(sql_path, "r") as f:
        sql = f.read()

    with engine.connect() as conn:
        # Split by statement separator and run each
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()
    print("Tables created successfully.")


def get_industry_id(conn, common_name):
    """Look up industry_id by common_name."""
    result = conn.execute(
        text("SELECT industry_id FROM industries WHERE common_name = :name"),
        {"name": common_name}
    ).fetchone()
    if result:
        return result[0]
    raise ValueError(f"Industry '{common_name}' not found in industries table")


def load_unemployment(engine):
    """Load unemployment_clean.csv into the unemployment table."""
    path = os.path.join(PROCESSED_DIR, "unemployment_clean.csv")
    df = pd.read_csv(path)
    print(f"Loading unemployment: {len(df)} rows...")

    # Map country names to codes
    country_map = {"Norway": "NO", "United States": "US"}

    rows = []
    for _, row in df.iterrows():
        rows.append({
            "country_code": country_map[row["country"]],
            "year": int(row["year"]),
            "month": None,  # annual averages
            "unemployment_rate": row["unemployment_rate"],
            "age_group": "total",
            "source": "SSB" if row["country"] == "Norway" else "BLS",
        })

    insert_df = pd.DataFrame(rows)
    insert_df.to_sql("unemployment", engine, if_exists="append", index=False)
    print(f"  Loaded {len(insert_df)} rows into unemployment table")


def load_wages(engine):
    """Load wages_clean.csv into the wages table."""
    path = os.path.join(PROCESSED_DIR, "wages_clean.csv")
    df = pd.read_csv(path)
    print(f"Loading wages: {len(df)} rows...")

    country_map = {"Norway": "NO", "United States": "US"}

    rows = []
    with engine.connect() as conn:
        for _, row in df.iterrows():
            try:
                industry_id = get_industry_id(conn, row["industry"])
            except ValueError:
                continue  # Skip unmapped industries

            rows.append({
                "country_code": country_map[row["country"]],
                "industry_id": industry_id,
                "year": int(row["year"]),
                "wage_local": row["wage_local"],
                "wage_local_currency": row["wage_local_currency"],
                "wage_annual_usd_ppp": row["wage_annual_usd_ppp"],
                "source": "SSB" if row["country"] == "Norway" else "BLS",
            })

    insert_df = pd.DataFrame(rows)
    insert_df.to_sql("wages", engine, if_exists="append", index=False)
    print(f"  Loaded {len(insert_df)} rows into wages table")


def load_employment(engine):
    """Load employment_clean.csv into the employment table."""
    path = os.path.join(PROCESSED_DIR, "employment_clean.csv")
    df = pd.read_csv(path)
    print(f"Loading employment: {len(df)} rows...")

    country_map = {"Norway": "NO", "United States": "US"}

    rows = []
    with engine.connect() as conn:
        for _, row in df.iterrows():
            try:
                industry_id = get_industry_id(conn, row["industry"])
            except ValueError:
                continue

            rows.append({
                "country_code": country_map[row["country"]],
                "industry_id": industry_id,
                "year": int(row["year"]),
                "employment_count": int(row["employment_count"]) if pd.notna(row["employment_count"]) else None,
                "employment_pct": row["employment_pct"] if pd.notna(row["employment_pct"]) else None,
                "source": "SSB" if row["country"] == "Norway" else "BLS",
            })

    insert_df = pd.DataFrame(rows)
    insert_df.to_sql("employment", engine, if_exists="append", index=False)
    print(f"  Loaded {len(insert_df)} rows into employment table")


def verify_counts(engine):
    """Print row counts to confirm everything loaded correctly."""
    tables = ["countries", "industries", "employment", "wages", "unemployment"]
    print("\nRow count verification:")
    with engine.connect() as conn:
        for table in tables:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table}: {count} rows")


def run_all():
    print("=== Loading data into PostgreSQL ===\n")
    engine = get_engine()

    # Test connection first
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection: OK\n")
    except Exception as e:
        print(f"Cannot connect to database: {e}")
        print("Check your .env file settings and make sure PostgreSQL is running.")
        return

    create_tables(engine)
    load_unemployment(engine)
    load_wages(engine)
    load_employment(engine)
    verify_counts(engine)
    print("\nAll data loaded successfully!")


if __name__ == "__main__":
    run_all()
