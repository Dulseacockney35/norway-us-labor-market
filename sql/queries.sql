-- queries.sql
-- Analytical queries for the Norway–US Labor Market project.


-- ── Query 1: Tech employment share over time (LAG, YoY change) ───────────────

SELECT
    e.year,
    c.country_name,
    e.employment_pct,
    LAG(e.employment_pct) OVER (PARTITION BY e.country_code ORDER BY e.year) AS prev_year_pct,
    ROUND(
        e.employment_pct - LAG(e.employment_pct) OVER (PARTITION BY e.country_code ORDER BY e.year)
    , 2) AS yoy_change
FROM employment e
JOIN countries c ON e.country_code = c.country_code
JOIN industries i ON e.industry_id = i.industry_id
WHERE i.common_name = 'Technology'
ORDER BY e.year, c.country_name;


-- ── Query 2: Wage gap analysis (AVG OVER, indexed vs. two-country mean) ──────

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


-- ── Query 3: COVID impact — change from 2019 baseline (FIRST_VALUE) ──────────

SELECT
    u.year,
    c.country_name,
    u.unemployment_rate,
    ROUND(
        u.unemployment_rate - FIRST_VALUE(u.unemployment_rate) OVER (
            PARTITION BY u.country_code ORDER BY u.year
        )
    , 2) AS change_from_2019_baseline
FROM unemployment u
JOIN countries c ON u.country_code = c.country_code
WHERE u.year BETWEEN 2019 AND 2023
  AND u.age_group = 'total'
  AND u.month IS NULL
ORDER BY u.year, c.country_name;


-- ── Query 4: Industry composition — latest year ───────────────────────────────

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


-- ── Query 5: Tech wage premium ratio ─────────────────────────────────────────

SELECT
    t.year,
    c.country_name,
    t.wage_annual_usd_ppp                                AS tech_wage_ppp,
    avg_all.wage_annual_usd_ppp                          AS avg_wage_ppp,
    ROUND(t.wage_annual_usd_ppp / avg_all.wage_annual_usd_ppp, 2) AS tech_premium_ratio
FROM wages t
JOIN wages avg_all
    ON t.country_code = avg_all.country_code AND t.year = avg_all.year
JOIN countries c  ON t.country_code   = c.country_code
JOIN industries it ON t.industry_id   = it.industry_id
JOIN industries ia ON avg_all.industry_id = ia.industry_id
WHERE it.common_name = 'Technology'
  AND ia.common_name = 'Total'
ORDER BY t.year, c.country_name;


-- ── Query 6: Difference-in-Differences — COVID as natural experiment ──────────
-- Treatment: Norway (strong safety net). Control: US.
-- Pre: 2015–2019. Post: 2020–2022.
-- DiD = (Norway_post - Norway_pre) - (US_post - US_pre)

WITH period_avgs AS (
    SELECT
        c.country_name,
        CASE WHEN u.year BETWEEN 2015 AND 2019 THEN 'pre' ELSE 'post' END AS period,
        AVG(u.unemployment_rate) AS avg_unemployment
    FROM unemployment u
    JOIN countries c ON u.country_code = c.country_code
    WHERE u.year BETWEEN 2015 AND 2022
      AND u.age_group = 'total'
      AND u.month IS NULL
    GROUP BY c.country_name, period
),
pivoted AS (
    SELECT
        country_name,
        MAX(CASE WHEN period = 'pre'  THEN avg_unemployment END) AS pre_avg,
        MAX(CASE WHEN period = 'post' THEN avg_unemployment END) AS post_avg
    FROM period_avgs
    GROUP BY country_name
),
changes AS (
    SELECT
        country_name,
        ROUND(post_avg - pre_avg, 3) AS delta
    FROM pivoted
)
SELECT
    country_name,
    delta,
    delta - LAG(delta) OVER (ORDER BY country_name) AS did_estimate
FROM changes
ORDER BY country_name;


-- ── Query 7: Wage growth quartiles (NTILE) ────────────────────────────────────
-- Rank each country-year by YoY tech wage growth and assign to quartiles.

WITH yoy AS (
    SELECT
        c.country_name,
        w.year,
        w.wage_annual_usd_ppp,
        ROUND(
            (w.wage_annual_usd_ppp - LAG(w.wage_annual_usd_ppp) OVER (
                PARTITION BY w.country_code ORDER BY w.year
            )) / LAG(w.wage_annual_usd_ppp) OVER (
                PARTITION BY w.country_code ORDER BY w.year
            ) * 100
        , 2) AS yoy_growth_pct
    FROM wages w
    JOIN countries c ON w.country_code = c.country_code
    JOIN industries i ON w.industry_id = i.industry_id
    WHERE i.common_name = 'Technology'
)
SELECT
    country_name,
    year,
    yoy_growth_pct,
    NTILE(4) OVER (PARTITION BY country_name ORDER BY yoy_growth_pct) AS growth_quartile
FROM yoy
WHERE yoy_growth_pct IS NOT NULL
ORDER BY country_name, year;


-- ── Query 8: Median wage by country using PERCENTILE_CONT ────────────────────
-- Median tech wage across all years — more robust than mean for skewed distributions.

SELECT
    c.country_name,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY w.wage_annual_usd_ppp) AS median_tech_wage_ppp,
    AVG(w.wage_annual_usd_ppp)                                          AS mean_tech_wage_ppp,
    ROUND(
        AVG(w.wage_annual_usd_ppp) - PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY w.wage_annual_usd_ppp)
    , 0) AS mean_minus_median
FROM wages w
JOIN countries c ON w.country_code = c.country_code
JOIN industries i ON w.industry_id = i.industry_id
WHERE i.common_name = 'Technology'
GROUP BY c.country_name;


-- ── Query 9: Multi-level CTE — identify high-growth outlier years ─────────────
-- Step 1: compute YoY growth. Step 2: flag years above 1 std dev from mean.

WITH yoy AS (
    SELECT
        c.country_name,
        w.year,
        ROUND(
            (w.wage_annual_usd_ppp - LAG(w.wage_annual_usd_ppp) OVER (
                PARTITION BY w.country_code ORDER BY w.year
            )) / LAG(w.wage_annual_usd_ppp) OVER (
                PARTITION BY w.country_code ORDER BY w.year
            ) * 100
        , 2) AS yoy_growth_pct
    FROM wages w
    JOIN countries c ON w.country_code = c.country_code
    JOIN industries i ON w.industry_id = i.industry_id
    WHERE i.common_name = 'Technology'
),
stats AS (
    SELECT
        country_name,
        AVG(yoy_growth_pct)    AS mean_growth,
        STDDEV(yoy_growth_pct) AS stddev_growth
    FROM yoy
    WHERE yoy_growth_pct IS NOT NULL
    GROUP BY country_name
)
SELECT
    y.country_name,
    y.year,
    y.yoy_growth_pct,
    ROUND(s.mean_growth, 2)    AS country_mean,
    ROUND(s.stddev_growth, 2)  AS country_stddev,
    CASE WHEN y.yoy_growth_pct > s.mean_growth + s.stddev_growth THEN 'high outlier'
         WHEN y.yoy_growth_pct < s.mean_growth - s.stddev_growth THEN 'low outlier'
         ELSE 'normal' END     AS classification
FROM yoy y
JOIN stats s ON y.country_name = s.country_name
WHERE y.yoy_growth_pct IS NOT NULL
ORDER BY y.country_name, y.year;
