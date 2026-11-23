/* @bruin
name: gold.pff_player_context
type: duckdb.sql
description: |
  PFF player lookup: one row per PFF player-season with stats, PFF grades, the grade's
  percentile WITHIN the same league/season/position among qualified PFF players, and the
  cross-source identity (gsis / pfr / combine athlete) where a provider-id link exists.
  PFF-sourced and labelled as such; not a Backfield evaluation; internal licence.
materialization:
  type: table
depends:
  - silver.pff_player_seasons
  - silver.pff_grades
  - silver.athlete_identity_xref
columns:
  - name: pff_player_id
    type: varchar
    checks:
      - name: not_null
  - name: pff_grade_offense_pctl_in_position
    type: double
    checks:
      - name: min
        value: 0
      - name: max
        value: 100
custom_checks:
  - name: unique player-league-season
    query: SELECT count(*) FROM (SELECT pff_player_id, league, season FROM gold.pff_player_context GROUP BY 1,2,3 HAVING count(*) > 1)
    value: 0
@bruin */

WITH qual AS (
  SELECT *, (CASE grade_metric WHEN 'pff_grade_pass' THEN qualifier_value >= 100 ELSE qualifier_value >= 200 END) AS qualified
  FROM silver.pff_grades WHERE grade_metric IN ('pff_grade_offense', 'pff_grade_pass')
),
pct AS (
  SELECT pff_player_id, league, season, grade_metric,
    round(100 * percent_rank() OVER (PARTITION BY league, season, position, grade_metric ORDER BY grade_value), 1) AS pctl,
    count(*) OVER (PARTITION BY league, season, position, grade_metric) AS cohort_n
  FROM qual WHERE qualified
)
SELECT s.*,
  po.pctl AS pff_grade_offense_pctl_in_position, po.cohort_n AS pff_grade_offense_cohort_n,
  pp.pctl AS pff_grade_pass_pctl_in_position, pp.cohort_n AS pff_grade_pass_cohort_n,
  x.gsis_id, x.pfr_id, x.combine_athlete_key, x.match_type AS identity_match_type,
  'PFF' AS grade_source, false AS is_backfield_evaluation
FROM silver.pff_player_seasons s
LEFT JOIN pct po ON po.pff_player_id = s.pff_player_id AND po.league = s.league AND po.season = s.season AND po.grade_metric = 'pff_grade_offense'
LEFT JOIN pct pp ON pp.pff_player_id = s.pff_player_id AND pp.league = s.league AND pp.season = s.season AND pp.grade_metric = 'pff_grade_pass'
LEFT JOIN silver.athlete_identity_xref x ON x.pff_player_id = s.pff_player_id
