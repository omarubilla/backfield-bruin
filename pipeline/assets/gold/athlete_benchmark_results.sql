/* @bruin
name: gold.athlete_benchmark_results
type: duckdb.sql
description: |
  Integration contract table (one row per athlete x benchmark metric) behind the
  athlete benchmark JSON export. Covers every metric the athlete submitted AND every
  combine metric with a position cohort, so missing data is explicit rather than absent.
  percentile is only filled when it is genuinely calculable:
    calculated           measured value + position cohort with n >= 20
    not_measured         cohort exists, athlete has no value
    no_reference_cohort  athlete has a value, the source has no cohort (e.g. 10-yard split)
    insufficient_cohort  cohort exists but n < 20
materialization:
  type: table
depends:
  - bronze.backfield_athlete_records
  - silver.physical_measurements
  - silver.athletes
  - gold.combine_benchmarks
columns:
  - name: athlete_id
    type: varchar
    checks:
      - name: not_null
  - name: metric
    type: varchar
    checks:
      - name: not_null
  - name: unit
    type: varchar
    checks:
      - name: not_null
  - name: percentile_status
    type: varchar
    checks:
      - name: accepted_values
        value: [calculated, not_measured, no_reference_cohort, insufficient_cohort]
  - name: percentile
    type: double
    checks:
      - name: min
        value: 0
      - name: max
        value: 100
custom_checks:
  - name: percentile present exactly when status is calculated
    query: |
      SELECT count(*) FROM gold.athlete_benchmark_results
      WHERE (percentile IS NOT NULL) <> (percentile_status = 'calculated')
    value: 0
  - name: every measured value carries a source record and capture method
    query: |
      SELECT count(*) FROM gold.athlete_benchmark_results
      WHERE measured AND (source_record_id IS NULL OR capture_method IS NULL OR source_provider IS NULL)
    value: 0
  - name: one row per athlete and metric
    query: SELECT count(*) FROM (SELECT athlete_id, metric FROM gold.athlete_benchmark_results GROUP BY 1, 2 HAVING count(*) > 1)
    value: 0
  - name: calculated percentiles always have a cohort of at least 20
    query: SELECT count(*) FROM gold.athlete_benchmark_results WHERE percentile_status = 'calculated' AND coalesce(cohort_n, 0) < 20
    value: 0
@bruin */

WITH athletes AS (
  SELECT DISTINCT athlete_id, display_name, position, level, grad_year, is_synthetic, _source_provider AS identity_provider
  FROM bronze.backfield_athlete_records
),
defs AS (
  SELECT DISTINCT metric, unit, definition, lower_is_better FROM silver.physical_measurements
  UNION ALL SELECT 'ten_yd_split_sec', 's', '10-yard split (first 10 yards of a sprint)', true
),
grid AS (  -- every metric the athlete has, plus every metric with a cohort at the athlete's position
  SELECT a.athlete_id, r.metric FROM athletes a JOIN bronze.backfield_athlete_records r USING (athlete_id)
  UNION
  SELECT a.athlete_id, b.metric FROM athletes a JOIN gold.combine_benchmarks b ON b.position_group = a.position
),
cohort AS (
  SELECT a.position_group, m.metric, m.value, m.lower_is_better
  FROM silver.physical_measurements m JOIN silver.athletes a USING (athlete_key)
  WHERE NOT m.implausible
),
pct AS (
  SELECT r.athlete_id, r.metric, count(c.value) AS n,
    100.0 * avg(CASE WHEN c.lower_is_better THEN (c.value > r.value)::INT ELSE (c.value < r.value)::INT END) AS pct
  FROM bronze.backfield_athlete_records r
  JOIN athletes a USING (athlete_id)
  JOIN cohort c ON c.position_group = a.position AND c.metric = r.metric
  GROUP BY 1, 2
)
SELECT
  a.athlete_id, a.display_name, a.position, a.level, a.grad_year, a.is_synthetic, a.identity_provider,
  g.metric, d.definition, coalesce(r.unit, d.unit) AS unit, d.lower_is_better,
  r.value, r.value IS NOT NULL AS measured,
  r.capture_method, r.confidence AS capture_confidence, r.observed_on, r.source_record_id, r.notes,
  CASE WHEN r.value IS NOT NULL THEN r._source_provider END AS source_provider,
  CASE WHEN r.value IS NOT NULL THEN r._license_category END AS license_category,
  -- cohort
  b.position_group AS cohort_position, b.reference_population AS cohort_population,
  b.n AS cohort_n, b.missing_n AS cohort_missing_n, b.season_min AS cohort_season_min, b.season_max AS cohort_season_max,
  b.p10, b.p25, b.p50, b.p75, b.p90, b.source AS cohort_source,
  CASE WHEN b.n IS NOT NULL THEN 'bruin:gold.combine_benchmarks/' || b.position_group || '/' || g.metric END AS cohort_ref,
  -- percentile
  CASE
    WHEN r.value IS NULL THEN 'not_measured'
    WHEN b.n IS NULL THEN 'no_reference_cohort'
    WHEN coalesce(p.n, 0) < 20 THEN 'insufficient_cohort'
    ELSE 'calculated' END AS percentile_status,
  CASE WHEN r.value IS NOT NULL AND b.n IS NOT NULL AND p.n >= 20 THEN round(p.pct, 1) END AS percentile,
  CASE
    WHEN r.value IS NULL THEN 'Athlete has no recorded value for this metric.'
    WHEN b.n IS NULL THEN 'The nflverse combine source has no cohort for this metric; no percentile is calculated or imputed.'
    WHEN coalesce(p.n, 0) < 20 THEN 'Cohort smaller than 20; percentile withheld.'
  END AS missing_reason,
  CASE
    WHEN r.value IS NULL OR b.n IS NULL THEN NULL
    WHEN r.capture_method ILIKE '%hand%' THEN 'caveat'
    WHEN r.capture_method ILIKE '%self-reported%' THEN 'caveat'
    WHEN r.capture_method ILIKE '%uncalibrated%' THEN 'caveat'
    ELSE 'comparable' END AS comparability,
  CASE
    WHEN r.capture_method ILIKE '%hand%' THEN 'Hand timing usually reads faster than electronic combine timing; percentile is optimistic.'
    WHEN r.capture_method ILIKE '%self-reported%' THEN 'Self-reported value; verify with a measured value.'
    WHEN r.capture_method ILIKE '%uncalibrated%' THEN 'Uncalibrated capture; treat as an estimate.'
  END AS comparability_note
FROM grid g
JOIN athletes a USING (athlete_id)
JOIN defs d USING (metric)
LEFT JOIN bronze.backfield_athlete_records r ON r.athlete_id = g.athlete_id AND r.metric = g.metric
LEFT JOIN gold.combine_benchmarks b ON b.position_group = a.position AND b.metric = g.metric
LEFT JOIN pct p ON p.athlete_id = g.athlete_id AND p.metric = g.metric
