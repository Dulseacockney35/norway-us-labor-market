-- create_tables.sql
-- PostgreSQL schema for the Norway-US Labor Market project.
-- Star schema: dimension tables + fact tables.

-- Drop tables if they exist (for re-runs during development)
DROP TABLE IF EXISTS unemployment CASCADE;
DROP TABLE IF EXISTS wages CASCADE;
DROP TABLE IF EXISTS employment CASCADE;
DROP TABLE IF EXISTS industries CASCADE;
DROP TABLE IF EXISTS countries CASCADE;


-- ── Dimension Tables ────────────────────────────────────────────────────────

CREATE TABLE countries (
    country_code   CHAR(2)      PRIMARY KEY,  -- 'NO', 'US'
    country_name   VARCHAR(50)  NOT NULL,
    currency       CHAR(3)      NOT NULL,     -- 'NOK', 'USD'
    ppp_factor_2023 DECIMAL(6, 4)             -- OECD PPP factor, reference year 2023
);

INSERT INTO countries VALUES
    ('NO', 'Norway',        'NOK', 11.21),
    ('US', 'United States', 'USD',  1.00);


CREATE TABLE industries (
    industry_id   SERIAL       PRIMARY KEY,
    common_name   VARCHAR(50)  NOT NULL,      -- Our unified label
    nace_code     VARCHAR(10),               -- Norway NACE classification
    naics_code    VARCHAR(10),               -- US NAICS classification
    notes         TEXT                        -- e.g., mapping caveats
);

INSERT INTO industries (common_name, nace_code, naics_code, notes) VALUES
    ('Technology',         'J',     '51',    'NACE J = Info & Communication; NAICS 51 = Information. Not a perfect match — NACE J includes publishing.'),
    ('Manufacturing',      'C',     '31-33', NULL),
    ('Finance',            'K',     '52',    NULL),
    ('Trade & Services',   'G-I',   '44-72', 'Broad aggregation; coverage differs'),
    ('Professional Services', 'M',  '54',    NULL),
    ('Total',              '00-99', '00',    'All industries combined');


-- ── Fact Tables ─────────────────────────────────────────────────────────────

CREATE TABLE employment (
    id               SERIAL       PRIMARY KEY,
    country_code     CHAR(2)      REFERENCES countries(country_code),
    industry_id      INT          REFERENCES industries(industry_id),
    year             INT          NOT NULL,
    employment_count BIGINT,                  -- Absolute headcount
    employment_pct   DECIMAL(5, 2),           -- % of total workforce
    source           VARCHAR(10)  NOT NULL    -- 'SSB' or 'BLS'
);

CREATE INDEX idx_employment_year ON employment(year);
CREATE INDEX idx_employment_country ON employment(country_code);


CREATE TABLE wages (
    id                  SERIAL       PRIMARY KEY,
    country_code        CHAR(2)      REFERENCES countries(country_code),
    industry_id         INT          REFERENCES industries(industry_id),
    year                INT          NOT NULL,
    wage_local          DECIMAL(12, 2),        -- In local currency
    wage_local_currency VARCHAR(15),           -- 'NOK_monthly', 'USD_hourly'
    wage_annual_usd_ppp DECIMAL(12, 2),        -- PPP-adjusted annual USD
    source              VARCHAR(10)  NOT NULL
);

CREATE INDEX idx_wages_year ON wages(year);


CREATE TABLE unemployment (
    id                  SERIAL       PRIMARY KEY,
    country_code        CHAR(2)      REFERENCES countries(country_code),
    year                INT          NOT NULL,
    month               INT,                   -- NULL = annual average
    unemployment_rate   DECIMAL(5, 2),
    age_group           VARCHAR(20),           -- 'total', '20-24', etc.
    source              VARCHAR(10)  NOT NULL
);

CREATE INDEX idx_unemployment_year ON unemployment(year);
