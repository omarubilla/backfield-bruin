/* @bruin
name: gold.player_benchmark_results
type: duckdb.sql
description: |
  Real-player version of the integration contract (same columns as gold.athlete_benchmark_results)
  for NFL Combine athletes whose identity is linked to PFF through provider ids
  (PFF player_id = nflverse players.pff_id -> pfr_id -> combine athlete). Percentiles compare the
  player's own published combine results with the same position cohort, EXCLUDING the player.
  Combine metrics the player did not record stay listed as not_measured (never imputed).
materialization:
  type: table
depends:
  - silver.athlete_identity_xref
  - silver.athletes
  - silver.physical_measurements
  - gold.combine_benchmarks
columns:
  - name: athlete_id
    type: varchar
    checks:
      - name: not_null
  - name: pff_player_id
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
    query: SELECT count(*) FROM gold.player_benchmark_results WHERE (percentile IS NOT NULL) <> (percentile_status = 'calculated')
    value: 0
  - name: one row per player and metric
    query: SELECT count(*) FROM (SELECT athlete_id, metric FROM gold.player_benchmark_results GROUP BY 1, 2 HAVING count(*) > 1)
    value: 0
  - name: every player is linked by provider id (never name)
    query: |
      SELECT count(*) FROM gold.player_benchmark_results r
      LEFT JOIN silver.athlete_identity_xref x ON x.pff_player_id = r.pff_player_id
      WHERE x.match_type IS DISTINCT FROM 'provider_id_nflverse_pff_id' OR x.combine_athlete_key <> r.athlete_id
    value: 0
@bruin */

WITH players AS (
  SELECT x.combine_athlete_key AS athlete_id, x.pff_player_id, x.gsis_id, x.pfr_id, a.player_name, a.position_group,
    a.school, a.season AS combine_season, a.draft_year, a.draft_team, a.draft_round
  FROM silver.athlete_identity_xref x JOIN silver.athletes a ON a.athlete_key = x.combine_athlete_key
  WHERE x.match_type = 'provider_id_nflverse_pff_id'
),
grid AS (
  SELECT p.*, b.metric FROM players p JOIN gold.combine_benchmarks b ON b.position_group = p.position_group
),
cohort AS (
  SELECT m.athlete_key, a.position_group, m.metric, m.value, m.lower_is_better
  FROM silver.physical_measurements m JOIN silver.athletes a USING (athlete_key) WHERE NOT m.implausible
),
pct AS (
  SELECT g.athlete_id, g.metric, count(c.value) AS n,
    100.0 * avg(CASE WHEN c.lower_is_better THEN (c.value > m.value)::INT ELSE (c.value < m.value)::INT END) AS pct
  FROM grid g
  JOIN silver.physical_measurements m ON m.athlete_key = g.athlete_id AND m.metric = g.metric AND NOT m.implausible
  JOIN cohort c ON c.position_group = g.position_group AND c.metric = g.metric AND c.athlete_key <> g.athlete_id
  GROUP BY 1, 2
)
SELECT
  g.athlete_id, g.player_name AS display_name, g.position_group AS position,
  'NFL Combine ' || g.combine_season || coalesce(' · ' || g.school, '') AS level,
  g.draft_year::INT AS grad_year, false AS is_synthetic,
  'nflverse combine (pfr_id) <-> PFF via nflverse players.pff_id' AS identity_provider,
  g.pff_player_id, g.gsis_id, g.pfr_id, g.combine_season, g.school, g.draft_team, g.draft_round,
  g.metric, b.definition, b.unit, b.lower_is_better,
  m.value, m.value IS NOT NULL AS measured,
  m.capture_method, m.confidence AS capture_confidence, m.observed_on_approx AS observed_on, m.source_record_id,
  CASE WHEN m.value IS NOT NULL THEN 'Official combine result as published by nflverse; observation date approximated to March 1 of the combine year.' END AS notes,
  m.source_provider, m.license_category,
  b.position_group AS cohort_position, b.reference_population AS cohort_population,
  b.n AS cohort_n, b.missing_n AS cohort_missing_n, b.season_min AS cohort_season_min, b.season_max AS cohort_season_max,
  b.p10, b.p25, b.p50, b.p75, b.p90, b.source AS cohort_source,
  'bruin:gold.combine_benchmarks/' || b.position_group || '/' || g.metric AS cohort_ref,
  CASE WHEN m.value IS NULL THEN 'not_measured' WHEN coalesce(p.n, 0) < 20 THEN 'insufficient_cohort' ELSE 'calculated' END AS percentile_status,
  CASE WHEN m.value IS NOT NULL AND p.n >= 20 THEN round(p.pct, 1) END AS percentile,
  CASE WHEN m.value IS NULL THEN 'Player has no published combine value for this metric (did not test or not recorded).'
       WHEN coalesce(p.n, 0) < 20 THEN 'Cohort smaller than 20; percentile withheld.' END AS missing_reason,
  CASE WHEN m.value IS NOT NULL THEN 'comparable' END AS comparability,
  CASE WHEN m.value IS NOT NULL THEN 'Official combine measurement compared with combine invitees at the same position (player excluded from his own cohort).' END AS comparability_note
FROM grid g
JOIN gold.combine_benchmarks b ON b.position_group = g.position_group AND b.metric = g.metric
LEFT JOIN silver.physical_measurements m ON m.athlete_key = g.athlete_id AND m.metric = g.metric AND NOT m.implausible
LEFT JOIN pct p ON p.athlete_id = g.athlete_id AND p.metric = g.metric
