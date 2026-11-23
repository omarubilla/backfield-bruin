""" @bruin
name: bronze.pff_rushing_summary
type: python
image: python:3.12
connection: duckdb-default
description: |
  Raw PFF /v1/facet/rushing/summary season rows (league-wide), NFL and NCAA, seasons 2024-2025.
  Kept separate from nflverse and CFBD. PFF grades are PFF's proprietary 0-100 evaluations.
  Licence: PFF Pro, internal analysis only (redistribution not confirmed) - never exported raw.
  Without PFF_API_KEY the asset writes one status row instead of failing.
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

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from providers import pff_client  # noqa: E402


def materialize():
    if not pff_client.key():
        return pd.DataFrame([{"player_id": None, "_league": None, "_season": None, "_endpoint": "/v1/facet/rushing/summary",
                              "_status": "unavailable: PFF_API_KEY not set", "_source_provider": "pff",
                              "_license_category": pff_client.LICENSE, "_ingested_at": pd.Timestamp.utcnow().isoformat()}])
    df, status = pff_client.facet_frame("rushing/summary")
    failed = [s for s in status if not s["ok"]]
    if df.empty:
        raise RuntimeError(f"PFF rushing/summary: no data ({failed})")
    df["_status"] = "ok" if not failed else "partial: " + "; ".join(f"{s['league']} {s['season']}: {s['detail']}" for s in failed)
    return df
