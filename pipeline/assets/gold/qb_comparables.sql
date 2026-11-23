/* @bruin
name: gold.qb_physical_comparables
type: duckdb.sql
description: |
  Example player comparisons - the combine QBs whose measured profile is closest to each
  Backfield athlete (mean absolute z-score over shared metrics, at least 4 shared).
  NFL production is attached through provider IDs (pfr_id -> gsis_id), never names.
  Descriptive similarity only; not a prediction of the athlete's outcome.
materialization:
  type: table
depends:
  - gold.athlete_evidence
  - gold.combine_benchmarks
  - silver.physical_measurements
  - silver.athletes
  - silver.nfl_qb_season_stats
  - bronze.nfl_players
columns:
  - name: rank
    type: integer
    checks:
      - name: positive
@bruin */

WITH ath AS (
  SELECT athlete_id, metric, value FROM gold.athlete_evidence WHERE position = 'QB' AND comparability <> 'no_reference_cohort'
),
qb AS (
  SELECT m.athlete_key, a.player_name, a.school, a.season, a.pfr_id, m.metric, m.value
  FROM silver.physical_measurements m JOIN silver.athletes a USING (athlete_key)
  WHERE a.position_group = 'QB' AND NOT m.implausible
),
dist AS (
  SELECT ath.athlete_id, qb.athlete_key, any_value(qb.player_name) AS player_name, any_value(qb.school) AS school,
    any_value(qb.season) AS combine_season, any_value(qb.pfr_id) AS pfr_id,
    count(*) AS shared_metrics, avg(abs(qb.value - ath.value) / nullif(b.sd, 0)) AS mean_abs_z
  FROM ath JOIN qb USING (metric) JOIN gold.combine_benchmarks b ON b.position_group = 'QB' AND b.metric = ath.metric
  GROUP BY 1, 2 HAVING count(*) >= 4
),
prod AS (
  SELECT p.pfr_id, sum(s.attempts) AS nfl_attempts_2019_2024, round(sum(s.passing_yards) * 1.0 / nullif(sum(s.attempts), 0), 2) AS nfl_yards_per_attempt
  FROM bronze.nfl_players p JOIN silver.nfl_qb_season_stats s ON s.player_id = p.gsis_id
  WHERE p.pfr_id IS NOT NULL GROUP BY 1
)
SELECT * FROM (
  SELECT d.*, round(d.mean_abs_z, 3) AS similarity_distance, prod.nfl_attempts_2019_2024, prod.nfl_yards_per_attempt,
    row_number() OVER (PARTITION BY d.athlete_id ORDER BY d.mean_abs_z) AS rank
  FROM dist d LEFT JOIN prod USING (pfr_id)
) WHERE rank <= 10
