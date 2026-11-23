/* @bruin
name: silver.pff_grades
type: duckdb.sql
description: |
  PFF-sourced grades in long form (player x season x grade), each with the volume that
  qualifies it. grade_source is always 'PFF' - these are PFF's proprietary evaluations and are
  labelled separately from any Backfield-generated evaluation. Never averaged with combine data.
materialization:
  type: table
depends:
  - silver.pff_player_seasons
columns:
  - name: grade_source
    type: varchar
    checks:
      - name: accepted_values
        value: [PFF]
  - name: grade_value
    type: double
    checks:
      - name: not_null
      - name: min
        value: 0
      - name: max
        value: 100
@bruin */

SELECT s.pff_player_id, s.league, s.season, s.player_name, s.position, s.team, g.grade_metric, g.grade_value,
  g.qualifier_metric, g.qualifier_value, g.definition,
  'PFF' AS grade_source, 'pff_proprietary_grade_0_100' AS grade_type, false AS is_backfield_evaluation,
  s.license_category
FROM silver.pff_player_seasons s,
LATERAL (VALUES
  ('pff_grade_offense', s.pff_grade_offense, 'snaps_offense', s.snaps_offense, 'PFF overall offense grade'),
  ('pff_grade_pass', s.pff_grade_pass, 'pass_dropbacks', s.pass_dropbacks, 'PFF passing grade'),
  ('pff_grade_run', s.pff_grade_run, 'rush_attempts', s.rush_attempts, 'PFF rushing grade'),
  ('pff_grade_pass_route', s.pff_grade_pass_route, 'rec_routes', s.rec_routes, 'PFF receiving (route) grade'),
  ('pff_grade_pass_block', s.pff_grade_pass_block, 'snaps_pass', s.snaps_pass, 'PFF pass-blocking grade'),
  ('pff_grade_run_block', s.pff_grade_run_block, 'snaps_run', s.snaps_run, 'PFF run-blocking grade')
) AS g(grade_metric, grade_value, qualifier_metric, qualifier_value, definition)
WHERE g.grade_value IS NOT NULL
