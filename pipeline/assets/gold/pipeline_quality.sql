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
  - silver.pff_player_seasons
  - silver.athlete_identity_xref
  - bronze.pff_ncaa_rosters
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
UNION ALL SELECT 'silver.pff_player_seasons', 'pff', count(*), count(*) FILTER (WHERE pff_player_id IS NULL), NULL, max(ingested_at),
  min(league) || '/' || max(league) || ' ' || min(season) || '-' || max(season) FROM silver.pff_player_seasons
UNION ALL SELECT 'bronze.pff_ncaa_rosters', 'pff', count(*) FILTER (WHERE player_id IS NOT NULL), count(*) FILTER (WHERE player_id IS NULL), NULL, max(_ingested_at), 'ncaa 2025, 6 teams' FROM bronze.pff_ncaa_rosters
UNION ALL SELECT 'silver.athlete_identity_xref', 'pff x nflverse', count(*), count(*) FILTER (WHERE match_type = 'unmatched'), NULL, NULL,
  count(*) FILTER (WHERE match_type <> 'unmatched') || ' provider-id links' FROM silver.athlete_identity_xref
