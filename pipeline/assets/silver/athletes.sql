/* @bruin
name: silver.athletes
type: duckdb.sql
description: |
  Normalized Athlete entity for combine invitees. Identity is keyed on provider IDs
  (pfr_id, else cfb_id). Rows with neither get a PROVISIONAL key scoped to the source
  record; athletes are never merged on name alone.
materialization:
  type: table
depends:
  - bronze.nfl_combine
columns:
  - name: athlete_key
    type: varchar
    primary_key: true
    checks:
      - name: not_null
      - name: unique
  - name: identity_match_type
    type: varchar
    checks:
      - name: accepted_values
        value: [provider_id_pfr, provider_id_cfb, provisional_source_record]
custom_checks:
  - name: no athlete appears under two different pfr ids in one season
    query: |
      SELECT count(*) FROM (
        SELECT player_name, school, season FROM silver.athletes
        WHERE pfr_id IS NOT NULL GROUP BY 1,2,3 HAVING count(DISTINCT pfr_id) > 1)
    value: 0
@bruin */

WITH src AS (
  SELECT *,
    CASE WHEN pfr_id IS NOT NULL THEN 'pfr:' || pfr_id
         WHEN cfb_id IS NOT NULL THEN 'cfb:' || cfb_id
         ELSE 'provisional:nflverse_combine:' || season || ':' || _row_number END AS athlete_key,
    CASE WHEN pfr_id IS NOT NULL THEN 'provider_id_pfr'
         WHEN cfb_id IS NOT NULL THEN 'provider_id_cfb'
         ELSE 'provisional_source_record' END AS identity_match_type,
    row_number() OVER (PARTITION BY coalesce(pfr_id, cfb_id, _row_number::varchar) ORDER BY season DESC) AS rn
  FROM bronze.nfl_combine
)
SELECT athlete_key, identity_match_type, pfr_id, cfb_id, player_name, pos AS position_raw,
  CASE WHEN pos IN ('OT','OG','C','OL','G') THEN 'OL'
       WHEN pos IN ('DT','DE','DL') THEN 'DL'
       WHEN pos IN ('OLB','ILB','LB') THEN 'LB'
       WHEN pos IN ('S','SAF') THEN 'S'
       WHEN pos IN ('CB','DB','CB/WR') THEN 'CB'
       ELSE pos END AS position_group,
  school, season, draft_year, draft_team, draft_round, draft_ovr,
  'nflverse' AS source_provider
FROM src WHERE rn = 1
