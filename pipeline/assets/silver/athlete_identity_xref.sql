/* @bruin
name: silver.athlete_identity_xref
type: duckdb.sql
description: |
  Cross-source athlete identity. PFF players are linked to nflverse (gsis/pfr) and to the
  combine Athlete entity ONLY through the provider id nflverse publishes (players.pff_id).
  PFF ids persist from NCAA into the NFL, so drafted college players link too. CFBD rows, when
  available, are offered as PROVISIONAL candidates (name + team + season) and never merged.
materialization:
  type: table
depends:
  - silver.pff_player_seasons
  - bronze.nfl_players
  - silver.athletes
  - bronze.cfbd_player_season_passing
columns:
  - name: pff_player_id
    type: varchar
    checks:
      - name: not_null
      - name: unique
  - name: match_type
    type: varchar
    checks:
      - name: accepted_values
        value: [provider_id_nflverse_pff_id, unmatched]
custom_checks:
  - name: no gsis id linked to two PFF players
    query: SELECT count(*) FROM (SELECT gsis_id FROM silver.athlete_identity_xref WHERE gsis_id IS NOT NULL GROUP BY 1 HAVING count(*) > 1)
    value: 0
@bruin */

WITH pff AS (
  SELECT pff_player_id, any_value(player_name) AS player_name, string_agg(DISTINCT league, ',') AS pff_leagues,
    min(season) AS first_season, max(season) AS last_season, arg_max(position, season) AS position
  FROM silver.pff_player_seasons GROUP BY 1
),
nv AS (
  SELECT pff_id::VARCHAR AS pff_id, any_value(gsis_id) AS gsis_id, any_value(pfr_id) AS pfr_id, count(*) AS n
  FROM bronze.nfl_players WHERE pff_id IS NOT NULL GROUP BY 1
),
cfbd AS (
  SELECT lower(player_name) AS nm, any_value(cfbd_player_id) AS cfbd_player_id, count(*) AS n
  FROM bronze.cfbd_player_season_passing WHERE provider_status = 'available' GROUP BY 1
)
SELECT pff.pff_player_id, pff.player_name, pff.position, pff.pff_leagues, pff.first_season, pff.last_season,
  CASE WHEN nv.n = 1 THEN nv.gsis_id END AS gsis_id,
  CASE WHEN nv.n = 1 THEN nv.pfr_id END AS pfr_id,
  CASE WHEN nv.n = 1 AND a.athlete_key IS NOT NULL THEN a.athlete_key END AS combine_athlete_key,
  CASE WHEN nv.n = 1 THEN 'provider_id_nflverse_pff_id' ELSE 'unmatched' END AS match_type,
  CASE WHEN cfbd.n = 1 THEN cfbd.cfbd_player_id END AS cfbd_candidate_id,
  CASE WHEN cfbd.n = 1 THEN 'provisional_name_match (not merged)' END AS cfbd_candidate_basis
FROM pff
LEFT JOIN nv ON nv.pff_id = pff.pff_player_id
LEFT JOIN silver.athletes a ON a.athlete_key = 'pfr:' || nv.pfr_id
LEFT JOIN cfbd ON cfbd.nm = lower(pff.player_name)
