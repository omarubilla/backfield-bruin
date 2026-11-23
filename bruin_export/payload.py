"""Builds the athlete benchmark payload (schema: docs/athlete_benchmark.schema.json)
from the Bruin gold layer plus the latest pipeline execution status.

    python -m bruin_export.payload --athlete bf-demo-qb-001            # print one payload
    python -m bruin_export.payload --all --out exports/                # write every athlete
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

import duckdb

SCHEMA_VERSION = "1.0.0"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB = os.environ.get("BRUIN_DUCKDB", os.path.join(ROOT, "data", "scouting.duckdb"))
RUN_STATUS = os.path.join(ROOT, "logs", "bruin_run_latest.json")


def _rows(sql: str, params=()) -> list[dict]:
    con = duckdb.connect(DB, read_only=True)
    try:
        cur = con.execute(sql, list(params))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def pipeline_status() -> dict:
    if not os.path.exists(RUN_STATUS):
        return {"status": "unknown", "validated": False, "detail": "no recorded run; execute scripts/run_pipeline.sh"}
    s = json.load(open(RUN_STATUS))
    providers = _rows("SELECT provider, status, detail, license_category FROM bronze.provider_status ORDER BY provider")
    return {
        "status": "succeeded" if s["validated"] else "failed",
        "validated": s["validated"],
        "tool": "bruin", "bruin_version": s.get("bruin_version"), "pipeline": s.get("pipeline"),
        "git_commit": s.get("git_commit"), "started_at": s.get("started_at"), "finished_at": s.get("finished_at"),
        "exit_code": s.get("exit_code"),
        "assets": {"total": s["assets_total"], "passed": s["assets_passed"]},
        "quality_checks": {"passed": s["checks_passed"], "failed": s["checks_failed"],
                           "failed_blocking": s["checks_failed_blocking"], "failures": s["check_failures"]},
        "providers": providers,
    }


def list_athletes() -> list[str]:
    return [r["athlete_id"] for r in _rows("SELECT DISTINCT athlete_id FROM gold.athlete_benchmark_results ORDER BY 1")]


def build(athlete_id: str) -> dict | None:
    rows = _rows("SELECT * FROM gold.athlete_benchmark_results WHERE athlete_id = ? ORDER BY measured DESC, metric", [athlete_id])
    if not rows:
        return None
    a = rows[0]
    status = pipeline_status()
    measurements = []
    for r in rows:
        measurements.append({
            "metric": r["metric"],
            "definition": r["definition"],
            "value": r["value"],
            "unit": r["unit"],
            "lower_is_better": r["lower_is_better"],
            "measured": r["measured"],
            "source": None if not r["measured"] else {
                "provider": r["source_provider"], "record_id": r["source_record_id"],
                "capture_method": r["capture_method"], "capture_confidence": r["capture_confidence"],
                "observed_on": _iso(r["observed_on"]), "license_category": r["license_category"], "notes": r["notes"],
            },
            "benchmark": None if r["cohort_n"] is None else {
                "cohort": f"NFL Combine invitees, {r['cohort_position']}",
                "position_group": r["cohort_position"],
                "reference_population": r["cohort_population"],
                "sample_size": r["cohort_n"],
                "missing_in_cohort": r["cohort_missing_n"],
                "seasons": {"from": r["cohort_season_min"], "to": r["cohort_season_max"]},
                "distribution": {k: r[k] for k in ("p10", "p25", "p50", "p75", "p90")},
                "source": r["cohort_source"],
                "source_ref": r["cohort_ref"],
            },
            "percentile": r["percentile"],
            "percentile_status": r["percentile_status"],
            "comparability": r["comparability"],
            "comparability_note": r["comparability_note"],
            "missing": {
                "value_missing": not r["measured"],
                "cohort_missing": r["cohort_n"] is None,
                "percentile_withheld": r["percentile"] is None,
                "reason": r["missing_reason"],
            },
        })
    # Deterministic id: same athlete + same validated data -> same evaluationId.
    fingerprint = json.dumps({"m": measurements, "run": status.get("finished_at")}, sort_keys=True, default=str)
    evaluation_id = f"bfe-{athlete_id}-{hashlib.sha256(fingerprint.encode()).hexdigest()[:12]}"
    calc = [m for m in measurements if m["percentile_status"] == "calculated"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "evaluationId": evaluation_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "athlete": {
            "athleteId": a["athlete_id"], "displayName": a["display_name"], "position": a["position"],
            "level": a["level"], "gradYear": a["grad_year"], "isSynthetic": a["is_synthetic"],
            "identityProvider": a["identity_provider"],
        },
        "measurements": measurements,
        "summary": {
            "metrics_total": len(measurements),
            "metrics_measured": sum(m["measured"] for m in measurements),
            "percentiles_calculated": len(calc),
            "percentiles_with_caveat": sum(m["comparability"] == "caveat" for m in calc),
            "missing_values": [m["metric"] for m in measurements if m["missing"]["value_missing"]],
            "missing_cohorts": [m["metric"] for m in measurements if m["measured"] and m["missing"]["cohort_missing"]],
        },
        "interpretation": "Percentiles are descriptive comparisons with NFL Combine invitees at the same position "
                          "(share of the cohort the athlete beats, direction-aware). They are not grades or projections.",
        "sourceReferences": [
            {"id": "nflverse-combine", "description": "NFL Scouting Combine results via nflreadpy.load_combine",
             "url": "https://github.com/nflverse/nflverse-data/releases/tag/combine", "license": "nflverse open data (attribution)"},
            {"id": "bruin-gold", "description": "Bruin gold tables gold.athlete_benchmark_results, gold.combine_benchmarks",
             "url": "https://github.com/bruin-data/bruin"},
            {"id": a["identity_provider"], "description": "Backfield athlete records (synthetic demo data in this build)"},
        ],
        "pipeline": status,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--athlete")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    ids = list_athletes() if a.all else [a.athlete or "bf-demo-qb-001"]
    for aid in ids:
        p = build(aid)
        if p is None:
            raise SystemExit(f"unknown athlete {aid}")
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            path = os.path.join(a.out, f"{aid}.json")
            json.dump(p, open(path, "w"), indent=2, default=str)
            print(f"wrote {path} ({p['evaluationId']})")
        else:
            print(json.dumps(p, indent=2, default=str))


if __name__ == "__main__":
    main()
