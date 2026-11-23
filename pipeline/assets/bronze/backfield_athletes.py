""" @bruin
name: bronze.backfield_athlete_records
type: python
image: python:3.12
connection: duckdb-default
description: |
  Backfield athlete evidence (Source D). In this hackathon build the records come from
  seeds/backfield_demo_athletes.json, which are CLEARLY SYNTHETIC demo records
  (is_synthetic = true). They are never mixed into reference cohorts.
materialization:
  type: table
columns:
  - name: athlete_id
    type: varchar
    checks:
      - name: not_null
  - name: metric
    type: varchar
    checks:
      - name: not_null
  - name: is_synthetic
    type: boolean
    checks:
      - name: not_null
@bruin """

import json
import os
from datetime import datetime, timezone

import pandas as pd

SEED = os.path.join(os.path.dirname(__file__), "..", "..", "..", "seeds", "backfield_demo_athletes.json")


def materialize():
    with open(SEED) as f:
        data = json.load(f)
    rows = []
    for a in data["athletes"]:
        for m in a["measurements"]:
            rows.append({
                "athlete_id": a["athlete_id"], "display_name": a["display_name"], "position": a["position"],
                "level": a["level"], "grad_year": a["grad_year"], "is_synthetic": a["is_synthetic"],
                "metric": m["metric"], "value": m["value"], "unit": m["unit"], "observed_on": m["observed_on"],
                "capture_method": m["capture_method"], "confidence": m.get("confidence"),
                "source_record_id": m["source_record_id"], "notes": m.get("notes"),
            })
    df = pd.DataFrame(rows)
    df["_source_provider"] = data["provider"]
    df["_license_category"] = data["license_category"]
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    return df
