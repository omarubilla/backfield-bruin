/* @bruin
name: silver.pff_player_seasons
type: duckdb.sql
description: |
  One row per PFF player x league x season, joining PFF passing, rushing, receiving and
  offense (snaps/grades) season reports by PFF player_id. Column prefixes keep each
  report's definitions apart (pass_*, rush_*, rec_*). Grades are PFF's proprietary 0-100
  grades (pff_grade_*), never Backfield evaluations. Source: PFF Pro (internal licence).
materialization:
  type: table
depends:
  - bronze.pff_passing_summary
  - bronze.pff_rushing_summary
  - bronze.pff_receiving_summary
  - bronze.pff_offense_summary
columns:
  - name: pff_player_id
    type: varchar
    checks:
      - name: not_null
  - name: league
    type: varchar
    checks:
      - name: accepted_values
        value: [nfl, ncaa]
  - name: season
    type: integer
    checks:
      - name: not_null
custom_checks:
  - name: unique player-league-season
    query: SELECT count(*) FROM (SELECT pff_player_id, league, season FROM silver.pff_player_seasons GROUP BY 1,2,3 HAVING count(*) > 1)
    value: 0
  - name: PFF grades within 0-100
    query: |
      SELECT count(*) FROM silver.pff_player_seasons
      WHERE NOT (coalesce(pff_grade_offense, 50) BETWEEN 0 AND 100 AND coalesce(pff_grade_pass, 50) BETWEEN 0 AND 100
             AND coalesce(pff_grade_run, 50) BETWEEN 0 AND 100 AND coalesce(pff_grade_pass_route, 50) BETWEEN 0 AND 100)
    value: 0
  - name: completions never exceed attempts
    query: SELECT count(*) FROM silver.pff_player_seasons WHERE pass_completions > pass_attempts
    value: 0
@bruin */

WITH o AS (SELECT * FROM bronze.pff_offense_summary WHERE player_id IS NOT NULL),
p AS (SELECT * FROM bronze.pff_passing_summary WHERE player_id IS NOT NULL),
r AS (SELECT * FROM bronze.pff_rushing_summary WHERE player_id IS NOT NULL),
c AS (SELECT * FROM bronze.pff_receiving_summary WHERE player_id IS NOT NULL),
ids AS (
  SELECT player_id::VARCHAR AS pid, _league AS league, _season AS season FROM o
  UNION SELECT player_id::VARCHAR, _league, _season FROM p
  UNION SELECT player_id::VARCHAR, _league, _season FROM r
  UNION SELECT player_id::VARCHAR, _league, _season FROM c
)
SELECT
  ids.pid AS pff_player_id, ids.league, ids.season::INT AS season,
  coalesce(o.player, p.player, r.player, c.player) AS player_name,
  coalesce(o.position, p.position, r.position, c.position) AS position,
  coalesce(o.team_name, p.team_name, r.team_name, c.team_name) AS team,
  coalesce(o.franchise_id, p.franchise_id, r.franchise_id, c.franchise_id)::VARCHAR AS pff_franchise_id,
  coalesce(o.player_game_count, p.player_game_count, r.player_game_count, c.player_game_count)::INT AS games,
  -- snaps (offense summary)
  o.snap_counts_total::INT AS snaps_offense, o.snap_counts_pass::INT AS snaps_pass, o.snap_counts_run::INT AS snaps_run,
  -- passing
  p.dropbacks::INT AS pass_dropbacks, p.attempts::INT AS pass_attempts, p.completions::INT AS pass_completions,
  p.yards::INT AS pass_yards, p.touchdowns::INT AS pass_touchdowns, p.interceptions::INT AS pass_interceptions,
  p.big_time_throws::INT AS pass_big_time_throws, p.turnover_worthy_plays::INT AS pass_turnover_worthy_plays,
  p.accuracy_percent::DOUBLE AS pass_accuracy_pct, p.avg_time_to_throw::DOUBLE AS pass_avg_time_to_throw_s,
  p.avg_depth_of_target::DOUBLE AS pass_adot_yds, p.ypa::DOUBLE AS pass_yards_per_attempt, p.qb_rating::DOUBLE AS pass_qb_rating,
  -- rushing
  r.attempts::INT AS rush_attempts, r.yards::INT AS rush_yards, r.touchdowns::INT AS rush_touchdowns,
  r.yards_after_contact::INT AS rush_yards_after_contact, r.elusive_rating::DOUBLE AS rush_elusive_rating,
  r.avoided_tackles::INT AS rush_avoided_tackles, r.breakaway_percent::DOUBLE AS rush_breakaway_pct,
  -- receiving
  c.targets::INT AS rec_targets, c.receptions::INT AS rec_receptions, c.yards::INT AS rec_yards,
  c.touchdowns::INT AS rec_touchdowns, c.routes::INT AS rec_routes, c.yprr::DOUBLE AS rec_yards_per_route_run,
  c.drop_rate::DOUBLE AS rec_drop_rate, c.yards_after_catch::INT AS rec_yards_after_catch,
  -- PFF grades (0-100, PFF proprietary)
  coalesce(o.grades_offense, p.grades_offense, r.grades_offense, c.grades_offense)::DOUBLE AS pff_grade_offense,
  p.grades_pass::DOUBLE AS pff_grade_pass, coalesce(r.grades_run, o.grades_run)::DOUBLE AS pff_grade_run,
  coalesce(c.grades_pass_route, o.grades_pass_route)::DOUBLE AS pff_grade_pass_route,
  o.grades_pass_block::DOUBLE AS pff_grade_pass_block, o.grades_run_block::DOUBLE AS pff_grade_run_block,
  'pff' AS source_provider, 'PFF Pro licensed data - internal analysis only; redistribution not confirmed' AS license_category,
  coalesce(o._ingested_at, p._ingested_at, r._ingested_at, c._ingested_at) AS ingested_at
FROM ids
LEFT JOIN o ON o.player_id::VARCHAR = ids.pid AND o._league = ids.league AND o._season = ids.season
LEFT JOIN p ON p.player_id::VARCHAR = ids.pid AND p._league = ids.league AND p._season = ids.season
LEFT JOIN r ON r.player_id::VARCHAR = ids.pid AND r._league = ids.league AND r._season = ids.season
LEFT JOIN c ON c.player_id::VARCHAR = ids.pid AND c._league = ids.league AND c._season = ids.season
