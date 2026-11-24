/* @bruin
name: gold.live_reference_catalog
type: duckdb.sql
description: |
  Which reference cohort a live drill result may be compared with, per position. Built from
  gold.combine_benchmarks (electronic NFL Combine timing). The 10-yard split is listed explicitly as
  unavailable: no ingested source publishes it (docs/evidence/ten_yard_split_audit.md).
materialization:
  type: table
depends:
  - gold.combine_benchmarks
columns:
  - name: metric
    type: varchar
    checks:
      - name: not_null
custom_checks:
  - name: 10-yard split is never marked available
    query: SELECT count(*) FROM gold.live_reference_catalog WHERE metric = 'ten_yd_split_sec' AND reference_available
    value: 0
  - name: available references have a cohort of at least 20
    query: SELECT count(*) FROM gold.live_reference_catalog WHERE reference_available AND coalesce(n, 0) < 20
    value: 0
@bruin */

SELECT b.position_group, b.metric, true AS reference_available, NULL AS unavailable_reason,
  'NFL Combine invitees (' || b.position_group || '), measured and plausible' AS reference_population,
  CASE WHEN b.metric IN ('forty_sec', 'shuttle_sec', 'cone_sec') THEN 'electronic (NFL Scouting Combine)' ELSE 'standardized combine measurement' END AS reference_timing_method,
  b.n, b.season_min, b.season_max, b.p10, b.p25, b.p50, b.p75, b.p90, b.lower_is_better, b.unit,
  'nflverse NFL Combine via gold.combine_benchmarks' AS source
FROM gold.combine_benchmarks b
WHERE b.metric IN ('forty_sec', 'shuttle_sec', 'cone_sec', 'vertical_in', 'broad_jump_in')
UNION ALL
SELECT DISTINCT position_group, 'ten_yd_split_sec', false,
  'No 10-yard split reference cohort exists in the ingested sources (nflverse combine publishes no splits; PFF has no sprint split fields).',
  NULL, NULL, NULL::INT, NULL::INT, NULL::INT, NULL::DOUBLE, NULL::DOUBLE, NULL::DOUBLE, NULL::DOUBLE, NULL::DOUBLE, true, 's', NULL
FROM gold.combine_benchmarks
