-- queries.sql
-- Analytical queries for the Norway-US Labor Market project.
-- These use window functions and joins across dimension/fact tables.


-- ── Query 1: Tech employment share over time ─────────────────────────────────
-- What percentage of each country's workforce is in tech?
-- Uses LAG() to compute year-over-year change.

SELECT
    e.year,
    c.country_name,
    e.employment_pct,
    LAG(e.employment_pct) OVER (
        PARTITION BY e.country_code
        ORDER BY e.year
    ) AS prev_year_pct,
    ROUND(
        e.employment_pct - LAG(e.employment_pct) OVER (
            PARTITION BY e.country_code
            ORDER BY e.year
        ), 2
    ) AS yoy_change
FROM employment e
JOIN countries c ON e.country_code = c.country_code
JOIN industries i ON e.industry_id = i.industry_id
WHERE i.common_name = 'Technology'
ORDER BY e.year, c.country_name;


-- ── Query 2: Wage gap analysis ───────────────────────────────────────────────
-- How do tech wages compare (PPP-adjusted)?
-- Uses AVG OVER to index each country's wage vs the two-country average.

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
ORDER BY w.year, c.country_name;


-- ── Query 3: COVID impact comparison ────────────────────────────────────────
-- How did unemployment spike and recover differently?
-- Uses FIRST_VALUE to measure change from the pre-COVID baseline (2019).

SELECT
    u.year,
    c.country_name,
    u.unemployment_rate,
    ROUND(
        u.unemployment_rate - FIRST_VALUE(u.unemployment_rate) OVER (
            PARTITION BY u.country_code
            ORDER BY u.year
        )
    , 2) AS change_from_2019_baseline
FROM unemployment u
JOIN countries c ON u.country_code = c.country_code
WHERE u.year BETWEEN 2019 AND 2023
  AND u.age_group = 'total'
  AND u.month IS NULL   -- annual averages only
ORDER BY u.year, c.country_name;


-- ── Query 4: Industry composition comparison ─────────────────────────────────
-- How different are the two economies structurally (latest year)?

SELECT
    c.country_name,
    i.common_name AS industry,
    e.employment_pct
FROM employment e
JOIN countries c ON e.country_code = c.country_code
JOIN industries i ON e.industry_id = i.industry_id
WHERE e.year = (SELECT MAX(year) FROM employment)
  AND i.common_name != 'Total'
ORDER BY c.country_name, e.employment_pct DESC;


-- ── Query 5: Tech wage premium ───────────────────────────────────────────────
-- How much more do tech workers earn vs the national average?
-- "Premium" = tech wage / total economy wage.

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
ORDER BY t.year, c.country_name;
