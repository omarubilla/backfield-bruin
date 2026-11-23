"""Bruin benchmark integration API (read-only).

  GET /v1/health
  GET /v1/schema                              JSON Schema of the evaluation payload
  GET /v1/pipeline/status                     latest Bruin run: assets, quality checks, providers
  GET /v1/athletes                            athletes available in the gold layer
  GET /v1/athletes/{athlete_id}/benchmark     evaluation payload (schema 1.0.0)
  GET /v1/evaluations/{evaluation_id}         same payload, fetched by evaluationId (current data version only)
  GET /v1/benchmarks/{position}               raw position cohort distributions (gold.combine_benchmarks)

Run:  scripts/run_bruin_api.sh   (default http://127.0.0.1:8787)
"""
import json
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bruin_export import payload as P  # noqa: E402

SCHEMA_PATH = os.path.join(P.ROOT, "docs", "athlete_benchmark.schema.json")
app = FastAPI(title="Backfield Bruin Benchmark API", version=P.SCHEMA_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/v1/health")
def health():
    st = P.pipeline_status()
    return {"ok": os.path.exists(P.DB), "schemaVersion": P.SCHEMA_VERSION, "pipelineValidated": st["validated"],
            "lastRunFinishedAt": st.get("finished_at")}


@app.get("/v1/schema")
def schema():
    return json.load(open(SCHEMA_PATH))


@app.get("/v1/pipeline/status")
def pipeline_status():
    return P.pipeline_status()


@app.get("/v1/athletes")
def athletes():
    return [{"athleteId": a, "benchmarkUrl": f"/v1/athletes/{a}/benchmark"} for a in P.list_athletes()]


@app.get("/v1/athletes/{athlete_id}/benchmark")
def athlete_benchmark(athlete_id: str):
    doc = P.build(athlete_id)
    if doc is None:
        raise HTTPException(404, f"no benchmark results for athlete '{athlete_id}'")
    return doc


@app.get("/v1/evaluations/{evaluation_id}")
def evaluation(evaluation_id: str):
    for a in P.list_athletes():
        if evaluation_id.startswith(f"bfe-{a}-"):
            doc = P.build(a)
            if doc and doc["evaluationId"] == evaluation_id:
                return doc
            raise HTTPException(410, "evaluationId refers to an older data version; fetch the athlete's current benchmark")
    raise HTTPException(404, "unknown evaluationId")


@app.get("/v1/benchmarks/{position}")
def benchmarks(position: str):
    rows = P._rows("SELECT * FROM gold.combine_benchmarks WHERE position_group = ? ORDER BY metric", [position.upper()])
    if not rows:
        raise HTTPException(404, f"no cohort for position '{position}'")
    return rows
