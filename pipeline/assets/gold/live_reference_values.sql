/* @bruin
name: gold.live_reference_values
type: duckdb.sql
description: Individual reference values (public nflverse combine results) behind gold.live_reference_catalog, used to compute verified percentiles.
materialization:
  type: table
depends:
  - silver.physical_measurements
  - silver.athletes
columns:
  - name: value
    type: double
    checks:
      - name: positive
@bruin */

SELECT a.position_group, m.metric, m.value, m.season, m.source_record_id
FROM silver.physical_measurements m JOIN silver.athletes a USING (athlete_key)
WHERE NOT m.implausible AND m.metric IN ('forty_sec', 'shuttle_sec', 'cone_sec', 'vertical_in', 'broad_jump_in')
