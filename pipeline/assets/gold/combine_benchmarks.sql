/* @bruin
name: gold.combine_benchmarks
type: duckdb.sql
description: |
  Gold output 1 - position-specific NFL Combine distributions (descriptive percentiles).
  Reference population = combine invitees with a measured, plausible value for the metric.
  Keeps sample size, missing count, units, season range, source and direction.
materialization:
  type: table
depends:
  - silver.physical_measurements
  - silver.athletes
columns:
  - name: position_group
    type: varchar
    checks:
      - name: not_null
  - name: metric
    type: varchar
    checks:
      - name: not_null
  - name: n
    type: integer
    checks:
      - name: positive
custom_checks:
  - name: percentiles are ordered
    query: SELECT count(*) FROM gold.combine_benchmarks WHERE NOT (p10 <= p25 AND p25 <= p50 AND p50 <= p75 AND p75 <= p90)
    value: 0
  - name: QB benchmark cohort exists for 40-yard dash
    query: SELECT CASE WHEN count(*) = 1 THEN 0 ELSE 1 END FROM gold.combine_benchmarks WHERE position_group = 'QB' AND metric = 'forty_sec' AND n >= 100
    value: 0
@bruin */

WITH pop AS (
  SELECT a.position_group, m.*
  FROM silver.physical_measurements m JOIN silver.athletes a USING (athlete_key)
  WHERE NOT m.implausible AND a.position_group NOT IN ('K', 'P', 'LS')
),
roster AS (
  SELECT position_group, count(*) AS invitees FROM silver.athletes GROUP BY 1
)
SELECT p.position_group, p.metric, any_value(p.unit) AS unit, any_value(p.definition) AS definition,
  any_value(p.lower_is_better) AS lower_is_better,
  count(*)::INT AS n, (r.invitees - count(*))::INT AS missing_n, r.invitees::INT AS invitees,
  round(quantile_cont(p.value, 0.10), 3) AS p10, round(quantile_cont(p.value, 0.25), 3) AS p25,
  round(quantile_cont(p.value, 0.50), 3) AS p50, round(quantile_cont(p.value, 0.75), 3) AS p75,
  round(quantile_cont(p.value, 0.90), 3) AS p90, round(avg(p.value), 3) AS mean, round(stddev_samp(p.value), 3) AS sd,
  min(p.value) AS min, max(p.value) AS max, min(p.season) AS season_min, max(p.season) AS season_max,
  'nflverse combine' AS source, 'combine invitees with measured, plausible values' AS reference_population
FROM pop p JOIN roster r USING (position_group)
GROUP BY p.position_group, p.metric, r.invitees
HAVING count(*) >= 20
