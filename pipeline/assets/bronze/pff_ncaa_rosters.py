""" @bruin
name: bronze.pff_ncaa_rosters
type: python
image: python:3.12
connection: duckdb-default
description: |
  Raw PFF /v2/ncaa/teams/{team}/roster for a small representative set of FBS teams
  (same teams as the CFBD sample), season 2025: NCAA player profiles, depth, PFF grade,
  height (PFF format feet*100+inches), weight, eligibility year, snap counts.
  Licence: PFF Pro, internal analysis only - never exported raw.
materialization:
  type: table
columns:
  - name: _source_provider
    type: varchar
    checks:
      - name: accepted_values
        value: [pff]
@bruin """

import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from providers import pff_client  # noqa: E402

SEASON = 2025
TEAMS = ["UCLA Bruins", "USC Trojans", "Oregon Ducks", "Michigan Wolverines", "Texas Longhorns", "Georgia Bulldogs"]


def materialize():
    now = datetime.now(timezone.utc).isoformat()
    if not pff_client.key():
        return pd.DataFrame([{"playerId": None, "_status": "unavailable: PFF_API_KEY not set", "_source_provider": "pff",
                              "_license_category": pff_client.LICENSE, "_ingested_at": now}])
    teams = {r["name"]: r for r in pff_client.get("/v2/ncaa/teams", season=SEASON)["rows"]}
    frames = []
    for name in TEAMS:
        t = teams.get(name)
        if not t:
            continue
        d = pff_client.get(f"/v2/ncaa/teams/{t['slug']}/roster", season=SEASON)
        df = pd.DataFrame(d["rows"])
        df["team_name"], df["team_slug"], df["franchise_id"] = t["name"], t["slug"], t["franchiseId"]
        df["_league"], df["_season"] = "ncaa", SEASON
        df["_endpoint"] = f"/v2/ncaa/teams/{t['slug']}/roster?season={SEASON}"
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["_status"] = "ok"
    out["_source_provider"] = "pff"
    out["_license_category"] = pff_client.LICENSE
    out["_ingested_at"] = now
    return out
