/* @bruin
name: silver.physical_measurements
type: duckdb.sql
description: |
  PhysicalMeasurement entity in long form (one row per athlete x metric) with units,
  definitions, lineage, capture method, licence and a plausibility flag. Missing values
  stay missing (no row) - nothing is imputed, and there is no 10-yard split in this source.
materialization:
  type: table
depends:
  - silver.athletes
  - bronze.nfl_combine
columns:
  - name: athlete_key
    type: varchar
    checks:
      - name: not_null
  - name: metric
    type: varchar
    checks:
      - name: accepted_values
        value: [height_in, weight_lb, forty_sec, vertical_in, broad_jump_in, bench_reps, cone_sec, shuttle_sec]
  - name: value
    type: double
    checks:
      - name: not_null
      - name: positive
  - name: unit
    type: varchar
    checks:
      - name: accepted_values
        value: [in, lb, s, reps]
  - name: source_record_id
    type: varchar
    checks:
      - name: not_null
custom_checks:
  - name: one value per athlete, metric and season
    query: SELECT count(*) FROM (SELECT athlete_key, metric, season FROM silver.physical_measurements GROUP BY 1,2,3 HAVING count(*) > 1)
    value: 0
@bruin */

WITH c AS (
  SELECT b.*,
    CASE WHEN b.pfr_id IS NOT NULL THEN 'pfr:' || b.pfr_id
         WHEN b.cfb_id IS NOT NULL THEN 'cfb:' || b.cfb_id
         ELSE 'provisional:nflverse_combine:' || b.season || ':' || b._row_number END AS athlete_key,
    CASE WHEN regexp_matches(b.ht, '^[0-9]+-[0-9]+$')
         THEN split_part(b.ht, '-', 1)::INT * 12 + split_part(b.ht, '-', 2)::INT END AS height_in
  FROM bronze.nfl_combine b
),
-- keep each athlete's most recent combine appearance (some players attend twice)
latest AS (
  SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY athlete_key ORDER BY season DESC) rn FROM c) WHERE rn = 1
),
long AS (
  SELECT athlete_key, pos, season, _row_number, _ingested_at, m.metric, m.value FROM latest,
  LATERAL (VALUES
    ('height_in', height_in::DOUBLE), ('weight_lb', wt), ('forty_sec', forty), ('vertical_in', vertical),
    ('broad_jump_in', broad_jump), ('bench_reps', bench), ('cone_sec', cone), ('shuttle_sec', shuttle)
  ) AS m(metric, value)
)
SELECT
  l.athlete_key, l.metric, l.value,
  d.unit, d.definition, d.lower_is_better,
  l.value NOT BETWEEN d.plausible_min AND d.plausible_max AS implausible,
  l.season, make_date(l.season, 3, 1) AS observed_on_approx,
  'official NFL Scouting Combine (electronic timing where applicable)' AS capture_method,
  'published' AS confidence,
  'nflverse' AS source_provider,
  'nflverse_combine:' || l.season || ':' || l._row_number AS source_record_id,
  'public-open-data (nflverse; attribution required)' AS license_category,
  l._ingested_at AS ingested_at
FROM long l
JOIN (VALUES
  ('height_in', 'in', 'Standing height', false, 64, 83),
  ('weight_lb', 'lb', 'Body weight', false, 150, 400),
  ('forty_sec', 's', '40-yard dash time', true, 4.2, 6.2),
  ('vertical_in', 'in', 'Vertical jump', false, 15, 48),
  ('broad_jump_in', 'in', 'Standing broad jump', false, 75, 150),
  ('bench_reps', 'reps', '225 lb bench press repetitions', false, 0, 55),
  ('cone_sec', 's', '3-cone drill', true, 6.2, 9.0),
  ('shuttle_sec', 's', '20-yard (5-10-5) shuttle', true, 3.7, 5.8)
) AS d(metric, unit, definition, lower_is_better, plausible_min, plausible_max) USING (metric)
WHERE l.value IS NOT NULL
