""" @bruin
name: bronze.provider_status
type: python
image: python:3.12
connection: duckdb-default
description: |
  Availability probe for every data provider (no credentials are printed or stored).
  CFBD needs CFBD_API_KEY; PFF needs PFF_API_KEY plus a licence that allows this use.
  High-school sources (MaxPreps, Hudl) are interface-only until authorised access exists.
materialization:
  type: table
columns:
  - name: provider
    type: varchar
    checks:
      - name: not_null
      - name: unique
  - name: status
    type: varchar
    checks:
      - name: accepted_values
        value: [available, unavailable, interface_only, synthetic]
@bruin """

import os
from datetime import datetime, timezone

import pandas as pd
import requests


def probe_cfbd():
    key = os.environ.get("CFBD_API_KEY")
    if not key:
        return "unavailable", "CFBD_API_KEY not set (free key: collegefootballdata.com/key)"
    try:
        r = requests.get("https://api.collegefootballdata.com/teams/fbs", params={"year": 2024},
                         headers={"Authorization": f"Bearer {key}"}, timeout=20)
        return ("available", "authenticated probe ok") if r.ok else ("unavailable", f"probe HTTP {r.status_code}")
    except Exception as e:  # network problems are a status, not a crash
        return "unavailable", f"probe error: {type(e).__name__}"


def probe_pff():
    if not os.environ.get("PFF_API_KEY"):
        return "unavailable", "PFF_API_KEY not configured; PFF grades are never invented or scraped"
    return "unavailable", "key present but licence for redistribution/demo use not confirmed; provider disabled"


def materialize():
    now = datetime.now(timezone.utc).isoformat()
    cfbd = probe_cfbd()
    pff = probe_pff()
    rows = [
        ("nflverse", "available", "public nflverse releases via nflreadpy", "public-open-data (attribution)"),
        ("collegefootballdata", cfbd[0], cfbd[1], "CFBD API terms (free tier, rate limited)"),
        ("pff", pff[0], pff[1], "commercial licence required"),
        ("backfield-demo", "synthetic", "seeds/backfield_demo_athletes.json (synthetic demo athlete)", "synthetic-demo"),
        ("maxpreps", "interface_only", "no authorised API access; not scraped", "restricted"),
        ("hudl", "interface_only", "attribution URL only; athlete uploads the clip directly", "restricted"),
    ]
    return pd.DataFrame([{"provider": p, "status": s, "detail": d, "license_category": l, "checked_at": now} for p, s, d, l in rows])
