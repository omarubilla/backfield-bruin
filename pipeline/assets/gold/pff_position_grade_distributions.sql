/* @bruin
name: gold.pff_position_grade_distributions
type: duckdb.sql
description: |
  Position-specific PFF grade distributions per league and season, among qualified players
  (minimum volume on the grade's own qualifier). PFF vs PFF only - kept apart from NFL
  Combine benchmarks and never averaged with them. Aggregates of PFF Pro data (internal licence).
materialization:
  type: table
depends:
  - silver.pff_grades
columns:
  - name: n
    type: integer
    checks:
      - name: positive
custom_checks:
  - name: percentiles ordered
    query: SELECT count(*) FROM gold.pff_position_grade_distributions WHERE NOT (p10 <= p25 AND p25 <= p50 AND p50 <= p75 AND p75 <= p90)
    value: 0
@bruin */

WITH q AS (
  SELECT *, CASE qualifier_metric
      WHEN 'pass_dropbacks' THEN 100 WHEN 'rush_attempts' THEN 40 WHEN 'rec_routes' THEN 100
      ELSE 200 END AS min_qualifier
  FROM silver.pff_grades
)
SELECT league, season, position, grade_metric, any_value(definition) AS definition,
  qualifier_metric, any_value(min_qualifier) AS min_qualifier,
  count(*)::INT AS n,
  round(quantile_cont(grade_value, 0.10), 1) AS p10, round(quantile_cont(grade_value, 0.25), 1) AS p25,
  round(quantile_cont(grade_value, 0.50), 1) AS p50, round(quantile_cont(grade_value, 0.75), 1) AS p75,
  round(quantile_cont(grade_value, 0.90), 1) AS p90, round(avg(grade_value), 1) AS mean,
  'PFF' AS grade_source, 'gold.pff_position_grade_distributions' AS source_ref
FROM q WHERE qualifier_value >= min_qualifier
GROUP BY league, season, position, grade_metric, qualifier_metric
HAVING count(*) >= 10
