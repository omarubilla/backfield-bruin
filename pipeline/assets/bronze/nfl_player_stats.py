""" @bruin
name: bronze.nfl_player_stats
type: python
image: python:3.12
connection: duckdb-default
description: |
  Raw nflverse weekly player stats (nflreadpy.load_player_stats), regular + post season,
  seasons 2019-2024, passing/rushing columns only (QB vertical slice).
materialization:
  type: table
columns:
  - name: player_id
    type: varchar
    description: nflverse GSIS id. ~130 upstream rows have no id; check kept visible but non-blocking, rows excluded in silver.
    checks:
      - name: not_null
        blocking: false
  - name: season
    type: integer
    checks:
      - name: not_null
@bruin """

from datetime import datetime, timezone

import nflreadpy as nfl

SEASONS = list(range(2019, 2025))
KEEP = ["player_id", "player_display_name", "position", "position_group", "season", "week", "season_type",
        "team", "opponent_team", "completions", "attempts", "passing_yards", "passing_tds",
        "passing_interceptions", "sacks_suffered", "passing_air_yards", "passing_epa", "passing_cpoe",
        "carries", "rushing_yards", "rushing_tds", "rushing_epa"]


def materialize():
    df = nfl.load_player_stats(seasons=SEASONS).to_pandas()
    df = df[[c for c in KEEP if c in df.columns]].copy()
    df["_source_provider"] = "nflverse"
    df["_source_dataset"] = "nflreadpy.load_player_stats"
    df["_license_category"] = "public-open-data (nflverse; attribution required)"
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    return df
