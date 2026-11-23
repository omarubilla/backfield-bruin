/* @bruin
name: gold.athlete_evidence
type: duckdb.sql
description: |
  Gold output 3 - Backfield athlete evidence package. Each athlete metric is placed in the
  matching position cohort as an empirical percentile (share of the reference cohort the
  athlete beats, direction-aware). Metrics with no cohort (e.g. 10-yard split) or with a
  capture method that is not comparable to electronic combine timing are flagged, not hidden.
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
  - name: comparability
    type: varchar
    checks:
      - name: accepted_values
        value: [comparable, comparable_with_caveat, no_reference_cohort]
  - name: percentile
    type: double
    checks:
      - name: min
        value: 0
      - name: max
        value: 100
@bruin */

WITH ath AS (SELECT * FROM bronze.backfield_athlete_records),
cohort AS (
  SELECT a.position_group, m.metric, m.value, m.lower_is_better
  FROM silver.physical_measurements m JOIN silver.athletes a USING (athlete_key) WHERE NOT m.implausible
),
pct AS (
  SELECT ath.athlete_id, ath.metric,
    count(c.value) AS cohort_n,
    100.0 * avg(CASE WHEN c.lower_is_better THEN (c.value > ath.value)::INT ELSE (c.value < ath.value)::INT END) AS percentile
  FROM ath LEFT JOIN cohort c ON c.position_group = ath.position AND c.metric = ath.metric
  GROUP BY 1, 2
)
SELECT ath.athlete_id, ath.display_name, ath.position, ath.level, ath.is_synthetic,
  ath.metric, ath.value, ath.unit, ath.observed_on, ath.capture_method, ath.confidence,
  ath.source_record_id, ath._source_provider AS source_provider, ath._license_category AS license_category, ath.notes,
  pct.cohort_n, CASE WHEN pct.cohort_n >= 20 THEN round(pct.percentile, 1) END AS percentile,
  b.p10, b.p50, b.p90, b.season_min AS cohort_season_min, b.season_max AS cohort_season_max,
  CASE WHEN b.n IS NULL OR pct.cohort_n < 20 THEN 'no_reference_cohort'
       WHEN ath.capture_method ILIKE '%hand%' OR ath.capture_method ILIKE '%self-reported%' OR ath.capture_method ILIKE '%uncalibrated%'
         THEN 'comparable_with_caveat'
       ELSE 'comparable' END AS comparability,
  CASE WHEN b.n IS NULL OR pct.cohort_n < 20 THEN 'No NFL combine reference cohort for this metric/position in the source data.'
       WHEN ath.capture_method ILIKE '%hand%' THEN 'Hand timing usually reads faster than electronic combine timing; percentile is optimistic.'
       WHEN ath.capture_method ILIKE '%self-reported%' THEN 'Self-reported; verify with a measured value.'
       WHEN ath.capture_method ILIKE '%uncalibrated%' THEN 'Uncalibrated capture; treat as an estimate.'
       ELSE 'Measured with a method comparable to the reference.' END AS comparability_note,
  'Percentile vs NFL Combine invitees at the same position - descriptive only, not a projection.' AS interpretation
FROM ath
LEFT JOIN pct USING (athlete_id, metric)
LEFT JOIN gold.combine_benchmarks b ON b.position_group = ath.position AND b.metric = ath.metric
