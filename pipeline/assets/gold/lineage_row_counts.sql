/* @bruin
name: gold.lineage_row_counts
type: duckdb.sql
description: |
  Row counts at every stage of the pipeline, computed by Bruin inside the run (public-safe:
  counts only, no PFF values). Feeds the sponsor showcase and the submission evidence.
materialization:
  type: table
depends:
  - bronze.nfl_combine
  - bronze.nfl_players
  - bronze.nfl_player_stats
  - bronze.cfbd_player_season_passing
  - bronze.backfield_athlete_records
  - bronze.provider_status
  - bronze.pff_passing_summary
  - bronze.pff_rushing_summary
  - bronze.pff_receiving_summary
  - bronze.pff_offense_summary
  - bronze.pff_ncaa_rosters
  - silver.athletes
  - silver.physical_measurements
  - silver.nfl_qb_season_stats
  - silver.pff_player_seasons
  - silver.pff_grades
  - silver.athlete_identity_xref
  - gold.combine_benchmarks
  - gold.athlete_evidence
  - gold.athlete_benchmark_results
  - gold.player_benchmark_results
  - gold.pff_position_grade_distributions
  - gold.pff_player_context
  - gold.qb_physical_comparables
  - gold.ncaa_qb_context
  - bronze.live_assessments
  - silver.live_assessments
  - gold.live_reference_catalog
  - gold.live_assessment_comparisons
columns:
  - name: asset
    type: varchar
    checks:
      - name: unique
      - name: not_null
  - name: row_count
    type: bigint
    checks:
      - name: non_negative
@bruin */

SELECT 'bronze' AS layer, 'bronze.nfl_combine' AS asset, 'nflverse' AS provider, 'NFL Scouting Combine results' AS description, count(*) AS row_count FROM bronze.nfl_combine
UNION ALL SELECT 'bronze', 'bronze.nfl_players', 'nflverse', 'player identity + cross-provider ids', count(*) FROM bronze.nfl_players
UNION ALL SELECT 'bronze', 'bronze.nfl_player_stats', 'nflverse', 'weekly player stats 2019-2024', count(*) FROM bronze.nfl_player_stats
UNION ALL SELECT 'bronze', 'bronze.cfbd_player_season_passing', 'collegefootballdata', 'NCAA passing/rosters/recruiting (key not configured)', count(*) FILTER (WHERE provider_status = 'available') FROM bronze.cfbd_player_season_passing
UNION ALL SELECT 'bronze', 'bronze.backfield_athlete_records', 'backfield-demo', 'synthetic demo athlete evidence', count(*) FROM bronze.backfield_athlete_records
UNION ALL SELECT 'bronze', 'bronze.provider_status', 'all', 'provider availability probe', count(*) FROM bronze.provider_status
UNION ALL SELECT 'bronze', 'bronze.pff_passing_summary', 'pff', 'PFF passing season reports NFL+NCAA 2024-25', count(*) FROM bronze.pff_passing_summary WHERE player_id IS NOT NULL
UNION ALL SELECT 'bronze', 'bronze.pff_rushing_summary', 'pff', 'PFF rushing season reports NFL+NCAA 2024-25', count(*) FROM bronze.pff_rushing_summary WHERE player_id IS NOT NULL
UNION ALL SELECT 'bronze', 'bronze.pff_receiving_summary', 'pff', 'PFF receiving season reports NFL+NCAA 2024-25', count(*) FROM bronze.pff_receiving_summary WHERE player_id IS NOT NULL
UNION ALL SELECT 'bronze', 'bronze.pff_offense_summary', 'pff', 'PFF offense snaps/grades NFL+NCAA 2024-25', count(*) FROM bronze.pff_offense_summary WHERE player_id IS NOT NULL
UNION ALL SELECT 'bronze', 'bronze.pff_ncaa_rosters', 'pff', 'PFF NCAA rosters, 6 FBS teams 2025', count(*) FROM bronze.pff_ncaa_rosters WHERE player_id IS NOT NULL
UNION ALL SELECT 'silver', 'silver.athletes', 'nflverse', 'Athlete entity keyed on provider ids', count(*) FROM silver.athletes
UNION ALL SELECT 'silver', 'silver.physical_measurements', 'nflverse', 'long-form measurements with units/lineage', count(*) FROM silver.physical_measurements
UNION ALL SELECT 'silver', 'silver.nfl_qb_season_stats', 'nflverse', 'QB season rollups (null-id rows excluded)', count(*) FROM silver.nfl_qb_season_stats
UNION ALL SELECT 'silver', 'silver.pff_player_seasons', 'pff', 'PFF reports joined per player-league-season', count(*) FROM silver.pff_player_seasons
UNION ALL SELECT 'silver', 'silver.pff_grades', 'pff', 'PFF grades long form', count(*) FROM silver.pff_grades
UNION ALL SELECT 'silver', 'silver.athlete_identity_xref', 'pff x nflverse', 'PFF players with identity resolution', count(*) FROM silver.athlete_identity_xref
UNION ALL SELECT 'silver', 'silver.athlete_identity_xref [linked]', 'pff x nflverse', 'linked by provider id (nflverse pff_id)', count(*) FILTER (WHERE match_type = 'provider_id_nflverse_pff_id') FROM silver.athlete_identity_xref
UNION ALL SELECT 'silver', 'silver.athlete_identity_xref [linked to combine]', 'pff x nflverse x combine', 'linked through to a combine athlete', count(combine_athlete_key) FROM silver.athlete_identity_xref
UNION ALL SELECT 'gold', 'gold.combine_benchmarks', 'nflverse', 'position x metric combine distributions', count(*) FROM gold.combine_benchmarks
UNION ALL SELECT 'gold', 'gold.athlete_evidence', 'backfield-demo', 'demo athlete evidence', count(*) FROM gold.athlete_evidence
UNION ALL SELECT 'gold', 'gold.athlete_benchmark_results', 'backfield-demo', 'contract table (demo athlete)', count(*) FROM gold.athlete_benchmark_results
UNION ALL SELECT 'gold', 'gold.player_benchmark_results', 'nflverse x pff', 'contract table (real linked players)', count(*) FROM gold.player_benchmark_results
UNION ALL SELECT 'gold', 'gold.pff_position_grade_distributions', 'pff', 'PFF grade distributions within position', count(*) FROM gold.pff_position_grade_distributions
UNION ALL SELECT 'gold', 'gold.pff_player_context', 'pff', 'PFF player lookup', count(*) FROM gold.pff_player_context
UNION ALL SELECT 'gold', 'gold.qb_physical_comparables', 'nflverse', 'descriptive QB comparables', count(*) FROM gold.qb_physical_comparables
UNION ALL SELECT 'gold', 'gold.ncaa_qb_context', 'collegefootballdata', 'CFBD context (unavailable)', count(*) FILTER (WHERE provider_status = 'available') FROM gold.ncaa_qb_context
UNION ALL SELECT 'bronze', 'bronze.live_assessments', 'backfield-live', 'live athlete assessments (sample + ingested)', count(*) FROM bronze.live_assessments
UNION ALL SELECT 'silver', 'silver.live_assessments', 'backfield-live', 'normalized live assessments', count(*) FROM silver.live_assessments
UNION ALL SELECT 'gold', 'gold.live_reference_catalog', 'nflverse', 'drill -> reference cohort catalog (10-yd unavailable)', count(*) FROM gold.live_reference_catalog
UNION ALL SELECT 'gold', 'gold.live_assessment_comparisons', 'backfield-live x nflverse', 'live comparisons with status', count(*) FROM gold.live_assessment_comparisons
