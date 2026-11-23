/* @bruin
name: gold.pipeline_quality
type: duckdb.sql
description: Dataset-level quality and freshness summary for the dashboard (row counts, identity coverage, implausible values, ingestion time).
materialization:
  type: table
depends:
  - bronze.nfl_combine
  - bronze.nfl_players
  - bronze.nfl_player_stats
  - bronze.provider_status
  - silver.physical_measurements
  - silver.athletes
  - silver.nfl_qb_season_stats
  - gold.combine_benchmarks
  - gold.athlete_evidence
  - gold.ncaa_qb_context
columns:
  - name: dataset
    type: varchar
    checks:
      - name: unique
@bruin */

SELECT 'bronze.nfl_combine' AS dataset, 'nflverse' AS provider, count(*) AS row_count,
  count(*) FILTER (WHERE pfr_id IS NULL AND cfb_id IS NULL) AS rows_missing_provider_id,
  NULL::BIGINT AS implausible_values, max(_ingested_at) AS ingested_at,
  min(season) || '-' || max(season) AS coverage FROM bronze.nfl_combine
UNION ALL SELECT 'bronze.nfl_players', 'nflverse', count(*), count(*) FILTER (WHERE gsis_id IS NULL), NULL, max(_ingested_at), NULL FROM bronze.nfl_players
UNION ALL SELECT 'bronze.nfl_player_stats', 'nflverse', count(*), count(*) FILTER (WHERE player_id IS NULL), NULL, max(_ingested_at),
  min(season) || '-' || max(season) FROM bronze.nfl_player_stats
UNION ALL SELECT 'silver.athletes', 'nflverse', count(*), count(*) FILTER (WHERE identity_match_type = 'provisional_source_record'), NULL, NULL, NULL FROM silver.athletes
UNION ALL SELECT 'silver.physical_measurements', 'nflverse', count(*), 0, count(*) FILTER (WHERE implausible), max(ingested_at), min(season) || '-' || max(season) FROM silver.physical_measurements
UNION ALL SELECT 'silver.nfl_qb_season_stats', 'nflverse', count(*), 0, NULL, NULL, min(season) || '-' || max(season) FROM silver.nfl_qb_season_stats
UNION ALL SELECT 'gold.combine_benchmarks', 'nflverse', count(*), NULL, NULL, NULL, min(season_min) || '-' || max(season_max) FROM gold.combine_benchmarks
UNION ALL SELECT 'gold.athlete_evidence', 'backfield-demo (synthetic)', count(*), NULL, NULL, NULL, NULL FROM gold.athlete_evidence
UNION ALL SELECT 'gold.ncaa_qb_context', 'collegefootballdata', count(*) FILTER (WHERE provider_status = 'available'), NULL, NULL, NULL, any_value(provider_status) FROM gold.ncaa_qb_context
