""" @bruin
name: bronze.nfl_combine
type: python
image: python:3.12
connection: duckdb-default
description: |
  Raw NFL Scouting Combine results as published by nflverse (nflreadpy.load_combine).
  One row per combine invitee per season. Units as published: ht 'F-I' string, wt lb,
  forty/cone/shuttle seconds, vertical/broad_jump inches, bench reps at 225 lb.
  The source has NO 10-yard split column; it is never derived here.
materialization:
  type: table
columns:
  - name: season
    type: integer
    checks:
      - name: not_null
  - name: player_name
    type: varchar
    checks:
      - name: not_null
  - name: pos
    type: varchar
    checks:
      - name: not_null
@bruin """

from datetime import datetime, timezone

import nflreadpy as nfl


def materialize():
    df = nfl.load_combine().to_pandas()
    df["_source_provider"] = "nflverse"
    df["_source_dataset"] = "nflreadpy.load_combine"
    df["_source_url"] = "https://github.com/nflverse/nflverse-data/releases/tag/combine"
    df["_license_category"] = "public-open-data (nflverse; attribution required)"
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    df["_row_number"] = range(1, len(df) + 1)
    return df
