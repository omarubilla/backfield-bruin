/* @bruin
name: gold.live_assessment_comparisons
type: duckdb.sql
description: |
  Batch/audit form of the live comparison (the API applies identical rules in bruin_export/live.py).
  status: verified (electronic + verified quality -> percentile), provisional (reference exists, method
  or quality not equivalent -> descriptive band), unavailable (no reference), rejected (quality failed).
materialization:
  type: table
depends:
  - silver.live_assessments
  - gold.live_reference_catalog
  - gold.live_reference_values
columns:
  - name: status
    type: varchar
    checks:
      - name: accepted_values
        value: [verified, provisional, unavailable, rejected, invalid]
  - name: percentile
    type: double
    checks:
      - name: min
        value: 0
      - name: max
        value: 100
custom_checks:
  - name: percentile only for verified electronic measurements
    query: |
      SELECT count(*) FROM gold.live_assessment_comparisons
      WHERE (percentile IS NOT NULL) <> (status = 'verified') OR (status = 'verified' AND NOT method_comparable_to_combine)
    value: 0
  - name: 10-yard results are never given a percentile or band
    query: SELECT count(*) FROM gold.live_assessment_comparisons WHERE metric = 'ten_yd_split_sec' AND (percentile IS NOT NULL OR descriptive_band IS NOT NULL)
    value: 0
@bruin */

WITH j AS (
  SELECT l.*, c.reference_available, c.unavailable_reason, c.reference_population, c.reference_timing_method,
    c.n AS reference_n, c.season_min, c.season_max, c.p10, c.p25, c.p50, c.p75, c.p90, c.lower_is_better
  FROM silver.live_assessments l
  LEFT JOIN gold.live_reference_catalog c ON c.metric = l.metric AND c.position_group = l.position
),
pct AS (
  SELECT j.evaluation_id,
    100.0 * avg(CASE WHEN j.lower_is_better THEN (v.value > j.value)::INT ELSE (v.value < j.value)::INT END) AS pct
  FROM j JOIN gold.live_reference_values v ON v.position_group = j.position AND v.metric = j.metric
  GROUP BY 1
),
s AS (
  SELECT j.*,
    CASE WHEN j.validation_error IS NOT NULL THEN 'invalid'
         WHEN j.quality_status = 'failed' THEN 'rejected'
         WHEN NOT coalesce(j.reference_available, false) THEN 'unavailable'
         WHEN j.method_comparable_to_combine AND j.quality_status = 'verified' THEN 'verified'
         ELSE 'provisional' END AS status
  FROM j
)
SELECT s.evaluation_id, s.athlete_id, s.position, s.drill, s.metric, s.value, s.unit, s.method, s.method_comparable_to_combine,
  s.calibration_status, s.quality_status, s.is_sample, s.status,
  CASE WHEN s.status = 'verified' THEN round(p.pct, 1) END AS percentile,
  CASE WHEN s.status IN ('verified', 'provisional') THEN
    CASE WHEN s.value <= s.p10 THEN 'below p10' WHEN s.value <= s.p25 THEN 'p10-p25' WHEN s.value <= s.p50 THEN 'p25-p50'
         WHEN s.value <= s.p75 THEN 'p50-p75' WHEN s.value <= s.p90 THEN 'p75-p90' ELSE 'above p90' END END AS descriptive_band,
  s.reference_population, s.reference_timing_method, s.reference_n, s.season_min, s.season_max,
  CASE WHEN s.status = 'unavailable' THEN coalesce(s.unavailable_reason, 'No reference cohort for this metric/position.')
       WHEN s.status = 'provisional' THEN 'Timing method or quality not equivalent to electronic combine timing; descriptive band only.'
       WHEN s.status = 'rejected' THEN 'Capture quality failed.'
       WHEN s.status = 'invalid' THEN s.validation_error END AS reason,
  s.video_asset_id, s.modal_job_id, s.glb_asset_id
FROM s LEFT JOIN pct p USING (evaluation_id)
