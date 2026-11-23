""" @bruin
name: bronze.nfl_players
type: python
image: python:3.12
connection: duckdb-default
description: Raw nflverse player identity table (nflreadpy.load_players); carries cross-provider IDs (gsis, pfr, pff, espn).
materialization:
  type: table
columns:
  - name: gsis_id
    type: varchar
@bruin """

from datetime import datetime, timezone

import nflreadpy as nfl

KEEP = ["gsis_id", "display_name", "position", "position_group", "height", "weight", "birth_date",
        "college_name", "college_conference", "pfr_id", "pff_id", "espn_id", "rookie_season",
        "last_season", "latest_team", "draft_year", "draft_round", "draft_pick", "draft_team"]


def materialize():
    df = nfl.load_players().to_pandas()
    df = df[[c for c in KEEP if c in df.columns]].copy()
    df["_source_provider"] = "nflverse"
    df["_source_dataset"] = "nflreadpy.load_players"
    df["_license_category"] = "public-open-data (nflverse; attribution required)"
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    return df
