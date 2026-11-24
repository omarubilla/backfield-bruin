/* @bruin
name: silver.live_assessments
type: duckdb.sql
description: |
  Normalized live assessments: drill -> combine metric, units -> seconds/inches, method classed as
  comparable (electronic) or not, latest record per evaluation_id. Invalid rows are kept with a
  validation_error instead of being silently dropped.
materialization:
  type: table
depends:
  - bronze.live_assessments
columns:
  - name: evaluation_id
    type: varchar
    checks:
      - name: not_null
      - name: unique
  - name: metric
    type: varchar
    checks:
      - name: accepted_values
        value: [ten_yd_split_sec, forty_sec, shuttle_sec, cone_sec, vertical_in, broad_jump_in]
  - name: unit
    type: varchar
    checks:
      - name: accepted_values
        value: [s, in]
  - name: quality_status
    type: varchar
    checks:
      - name: accepted_values
        value: [verified, unverified, failed]
custom_checks:
  - name: valid rows have positive normalized values
    query: SELECT count(*) FROM silver.live_assessments WHERE validation_error IS NULL AND NOT (value > 0)
    value: 0
  - name: sprint times are physically plausible when valid
    query: |
      SELECT count(*) FROM silver.live_assessments WHERE validation_error IS NULL AND (
        (metric = 'ten_yd_split_sec' AND value NOT BETWEEN 1.2 and 3.5) OR (metric = 'forty_sec' AND value NOT BETWEEN 4.0 AND 8.0))
    value: 0
@bruin */

WITH ranked AS (
  SELECT *, row_number() OVER (PARTITION BY evaluation_id ORDER BY captured_at DESC NULLS LAST, record_source DESC) AS rn
  FROM bronze.live_assessments
),
n AS (
  SELECT *,
    CASE drill WHEN '10_yard_dash' THEN 'ten_yd_split_sec' WHEN '40_yard_dash' THEN 'forty_sec' WHEN '20_yard_shuttle' THEN 'shuttle_sec'
               WHEN 'three_cone' THEN 'cone_sec' WHEN 'vertical_jump' THEN 'vertical_in' WHEN 'broad_jump' THEN 'broad_jump_in' END AS metric,
    CASE lower(unit_raw) WHEN 'seconds' THEN value_raw WHEN 'second' THEN value_raw WHEN 'sec' THEN value_raw WHEN 's' THEN value_raw
      WHEN 'milliseconds' THEN value_raw / 1000.0 WHEN 'ms' THEN value_raw / 1000.0
      WHEN 'inches' THEN value_raw WHEN 'in' THEN value_raw WHEN 'cm' THEN value_raw / 2.54 WHEN 'centimeters' THEN value_raw / 2.54 END AS value_norm
  FROM ranked WHERE rn = 1
)
SELECT evaluation_id, athlete_id, upper(position) AS position, drill, metric,
  round(value_norm, 3) AS value, CASE WHEN metric LIKE '%_sec' THEN 's' ELSE 'in' END AS unit,
  lower(method) AS method,
  lower(method) IN ('electronic_laser', 'electronic_timing', 'freelap', 'laser') AS method_comparable_to_combine,
  calibration_status, quality_status, app_confidence_json, captured_at, video_asset_id, modal_job_id, glb_asset_id,
  motion_observations_json, is_sample, record_source, _ingested_at AS ingested_at,
  CASE WHEN metric IS NULL THEN 'unknown drill'
       WHEN value_norm IS NULL THEN 'unsupported unit'
       WHEN quality_status NOT IN ('verified', 'unverified', 'failed') THEN 'invalid quality status' END AS validation_error
FROM n
