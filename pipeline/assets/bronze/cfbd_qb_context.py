""" @bruin
name: bronze.cfbd_player_season_passing
type: python
image: python:3.12
connection: duckdb-default
description: |
  CollegeFootballData provider (Source B), small representative subset: 2024 season
  passing stats, QB rosters and QB recruiting records for a handful of FBS teams.
  Requires CFBD_API_KEY (read from the environment, never logged). When the key is
  missing the asset writes a single status row (provider_status = 'unavailable') so the
  rest of the pipeline and the dashboard can show it honestly instead of failing.
materialization:
  type: table
columns:
  - name: provider_status
    type: varchar
    checks:
      - name: accepted_values
        value: [available, unavailable]
@bruin """

import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://api.collegefootballdata.com"
YEAR = 2024
TEAMS = ["UCLA", "USC", "Oregon", "Michigan", "Texas", "Georgia"]
COLUMNS = ["provider_status", "detail", "cfbd_player_id", "player_name", "team", "conference", "season", "position",
           "height_in", "weight_lb", "class_year", "completions", "attempts", "passing_yards", "passing_tds",
           "interceptions", "yards_per_attempt", "recruit_stars", "recruit_rating", "_ingested_at"]


def get(path, key, **params):
    r = requests.get(BASE + path, params=params, headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    time.sleep(0.4)  # stay well inside free-tier rate limits
    return r.json()


def materialize():
    now = datetime.now(timezone.utc).isoformat()
    key = os.environ.get("CFBD_API_KEY")
    if not key:
        row = {c: None for c in COLUMNS} | {"provider_status": "unavailable", "detail": "CFBD_API_KEY not set", "_ingested_at": now}
        df = pd.DataFrame([row], columns=COLUMNS)
        for c in COLUMNS[2:-1]:
            df[c] = df[c].astype("string" if c in ("cfbd_player_id", "player_name", "team", "conference", "position", "class_year") else "float64")
        return df
    rows = []
    for team in TEAMS:
        roster = {str(p.get("id")): p for p in get("/roster", key, team=team, year=YEAR) if p.get("position") == "QB"}
        stats = get("/stats/player/season", key, year=YEAR, team=team, category="passing")
        by_player = {}
        for s in stats:
            pid = str(s.get("playerId"))
            by_player.setdefault(pid, {"player": s.get("player"), "team": s.get("team"), "conference": s.get("conference")})
            by_player[pid][s.get("statType")] = s.get("stat")
        for pid, d in by_player.items():
            r = roster.get(pid, {})
            rows.append({
                "provider_status": "available", "cfbd_player_id": pid, "player_name": d["player"], "team": d["team"],
                "conference": d["conference"], "season": YEAR, "position": r.get("position", "QB"),
                "height_in": r.get("height"), "weight_lb": r.get("weight"), "class_year": r.get("year"),
                "completions": d.get("COMPLETIONS"), "attempts": d.get("ATT"), "passing_yards": d.get("YDS"),
                "passing_tds": d.get("TD"), "interceptions": d.get("INT"), "yards_per_attempt": d.get("YPA"),
                "detail": "cfbd /stats/player/season + /roster", "_ingested_at": now,
            })
    recruits = get("/recruiting/players", key, year=YEAR - 3, classification="HighSchool", position="PRO")
    for rc in recruits[:50]:
        rows.append({"provider_status": "available", "cfbd_player_id": str(rc.get("athleteId") or ""), "player_name": rc.get("name"),
                     "team": rc.get("committedTo"), "season": rc.get("year"), "position": rc.get("position"),
                     "height_in": rc.get("height"), "weight_lb": rc.get("weight"), "recruit_stars": rc.get("stars"),
                     "recruit_rating": rc.get("rating"), "detail": "cfbd /recruiting/players (pro-style QB)", "_ingested_at": now})
    df = pd.DataFrame(rows).reindex(columns=COLUMNS)
    for c in ["completions", "attempts", "passing_yards", "passing_tds", "interceptions", "yards_per_attempt", "height_in", "weight_lb", "recruit_rating"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
