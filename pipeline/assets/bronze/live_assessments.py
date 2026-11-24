""" @bruin
name: bronze.live_assessments
type: python
image: python:3.12
connection: duckdb-default
description: |
  Raw live athlete combine assessments (live-assessment 1.0.0 contract). Sources:
  data/landing/assessments/*.json (records accepted by the authenticated ingest API, synced from the
  Modal volume with scripts/sync_live_assessments.sh) and seeds/live_assessment_samples.json (a clearly
  labelled SAMPLE athlete). One row per submitted record, raw values as sent.
materialization:
  type: table
columns:
  - name: evaluation_id
    type: varchar
    checks:
      - name: not_null
  - name: athlete_id
    type: varchar
    checks:
      - name: not_null
@bruin """

import glob
import json
import os
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def rows():
    with open(os.path.join(ROOT, "seeds", "live_assessment_samples.json")) as f:
        for a in json.load(f)["assessments"]:
            yield a, "seed:live_assessment_samples.json"
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "landing", "assessments", "*.json"))):
        with open(p) as f:
            rec = json.load(f)
        yield rec.get("input", rec), "landing:" + os.path.basename(p)


def materialize():
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for a, src in rows():
        m = a.get("measurement", {})
        out.append({
            "evaluation_id": a.get("evaluationId"), "athlete_id": a.get("athleteId"), "sport": a.get("sport"),
            "position": a.get("position"), "drill": a.get("drill"), "value_raw": m.get("value"), "unit_raw": m.get("unit"),
            "method": m.get("method"), "calibration_status": m.get("calibrationStatus"), "quality_status": m.get("qualityStatus"),
            "app_confidence_json": json.dumps(m.get("appConfidence")) if m.get("appConfidence") else None,
            "captured_at": a.get("capturedAt"), "video_asset_id": a.get("videoAssetId"), "modal_job_id": a.get("modalJobId"),
            "glb_asset_id": a.get("glbAssetId"), "motion_observations_json": json.dumps(a.get("motionObservations") or []),
            "is_sample": bool(a.get("isSample", False)), "record_source": src,
        })
    df = pd.DataFrame(out)
    df["_source_provider"] = "backfield-live"
    df["_license_category"] = "athlete-submitted (private; public views redact identity)"
    df["_ingested_at"] = now
    return df
