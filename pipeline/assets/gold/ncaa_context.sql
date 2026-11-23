/* @bruin
name: gold.ncaa_qb_context
type: duckdb.sql
description: |
  Gold output 2 - NCAA player statistical context from CollegeFootballData (2024 sample teams).
  Empty with an explicit status when the CFBD provider is unavailable.
materialization:
  type: table
depends:
  - bronze.cfbd_player_season_passing
columns:
  - name: provider_status
    type: varchar
    checks:
      - name: not_null
@bruin */

SELECT provider_status, detail, cfbd_player_id, player_name, team, conference, season, position,
  attempts, completions, passing_yards, passing_tds, interceptions, yards_per_attempt, recruit_stars, recruit_rating
FROM bronze.cfbd_player_season_passing
