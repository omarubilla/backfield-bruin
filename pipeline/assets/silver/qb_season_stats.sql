/* @bruin
name: silver.nfl_qb_season_stats
type: duckdb.sql
description: GameStatistic rollup - NFL regular-season passing per QB-season (2019-2024). Rows without a player id are excluded.
materialization:
  type: table
depends:
  - bronze.nfl_player_stats
columns:
  - name: player_id
    type: varchar
    checks:
      - name: not_null
  - name: attempts
    type: integer
    checks:
      - name: non_negative
custom_checks:
  - name: completions never exceed attempts
    query: SELECT count(*) FROM silver.nfl_qb_season_stats WHERE completions > attempts
    value: 0
  - name: unique QB-season
    query: SELECT count(*) FROM (SELECT player_id, season FROM silver.nfl_qb_season_stats GROUP BY 1,2 HAVING count(*) > 1)
    value: 0
@bruin */

SELECT player_id, any_value(player_display_name) AS player_name, season,
  count(*) AS games, sum(completions)::INT AS completions, sum(attempts)::INT AS attempts,
  sum(passing_yards)::INT AS passing_yards, sum(passing_tds)::INT AS passing_tds,
  sum(passing_interceptions)::INT AS interceptions, sum(sacks_suffered)::INT AS sacks,
  round(sum(passing_epa) / nullif(sum(attempts), 0), 3) AS epa_per_attempt,
  round(sum(completions) * 100.0 / nullif(sum(attempts), 0), 1) AS completion_pct,
  sum(carries)::INT AS carries, sum(rushing_yards)::INT AS rushing_yards,
  'nflverse' AS source_provider, 'nflreadpy.load_player_stats (REG)' AS source_dataset
FROM bronze.nfl_player_stats
WHERE player_id IS NOT NULL AND position = 'QB' AND season_type = 'REG'
GROUP BY player_id, season
