"""Deployed Bruin benchmark API (Modal, HTTPS).

Public (no auth)                                    PFF values redacted
  GET /v1/health
  GET /v1/schema
  GET /v1/public/pipeline/status
  GET /v1/public/athletes
  GET /v1/public/athletes/{athlete_id}/benchmark    schema 1.1.0, pffContext redacted
  GET /v1/public/benchmarks/{position}              NFL Combine distributions (nflverse, public)

Private (Authorization: Bearer <BRUIN_API_TOKEN>)   full licensed PFF context, server-side consumers only
  GET /v1/private/athletes/{athlete_id}/benchmark   schema 1.1.0, pffContext with values
  GET /v1/private/pff/players?name=&league=&season=
  GET /v1/private/pff/players/{pff_player_id}
  GET /v1/private/pff/distributions/{position}?league=&season=
"""
import hmac
import json
import os
import sys

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bruin_export import payload as P  # noqa: E402

SCHEMA_PATH = os.environ.get("BRUIN_SCHEMA", os.path.join(P.ROOT, "docs", "athlete_benchmark.schema.json"))
PUBLIC_PFF_NOTE = ("Redacted in public responses: PFF Pro licensed values are served only to authenticated "
                   "server-side consumers (/v1/private/*).")

app = FastAPI(title="Backfield Bruin Benchmark API", version=P.SCHEMA_VERSION, docs_url="/docs", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["Authorization"])


def require_token(authorization: str | None = Header(default=None)):
    expected = os.environ.get("BRUIN_API_TOKEN")
    if not expected:
        raise HTTPException(503, "private API not configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(401, "missing or invalid bearer token", headers={"WWW-Authenticate": "Bearer"})


def _public_payload(athlete_id: str) -> dict:
    doc = P.build(athlete_id, redact_pff=True)
    if doc is None:
        raise HTTPException(404, f"no benchmark results for athlete '{athlete_id}'")
    ctx = doc["pffContext"]
    ctx["statusDetail"] = PUBLIC_PFF_NOTE
    ctx["playerSeasons"] = []
    for r in ctx["positionReference"]:
        r["distribution"] = None
    return doc


@app.get("/v1/health")
def health():
    st = P.pipeline_status()
    return {"ok": os.path.exists(P.DB), "schemaVersion": P.SCHEMA_VERSION, "pipelineValidated": st["validated"],
            "lastRunFinishedAt": st.get("finished_at")}


@app.get("/v1/schema")
def schema():
    return json.load(open(SCHEMA_PATH))


public = APIRouter(prefix="/v1/public")


@public.get("/pipeline/status")
def pipeline_status():
    return P.pipeline_status()


@public.get("/athletes")
def athletes():
    return [{"athleteId": a, "benchmarkUrl": f"/v1/public/athletes/{a}/benchmark"} for a in P.list_athletes()]


@public.get("/athletes/{athlete_id}/benchmark")
def public_benchmark(athlete_id: str):
    return _public_payload(athlete_id)


@public.get("/benchmarks/{position}")
def combine_benchmarks(position: str):
    rows = P._rows("SELECT * FROM gold.combine_benchmarks WHERE position_group = ? ORDER BY metric", [position.upper()])
    if not rows:
        raise HTTPException(404, f"no combine cohort for position '{position}'")
    return {"source": "nflverse NFL Combine (public open data, attribution required)", "distributions": rows}


private = APIRouter(prefix="/v1/private", dependencies=[Depends(require_token)])


@private.get("/athletes/{athlete_id}/benchmark")
def private_benchmark(athlete_id: str):
    doc = P.build(athlete_id)
    if doc is None:
        raise HTTPException(404, f"no benchmark results for athlete '{athlete_id}'")
    return doc


@private.get("/pff/players")
def pff_players(name: str, league: str | None = None, season: int | None = None, limit: int = 25):
    if len(name.strip()) < 2:
        raise HTTPException(400, "name must be at least 2 characters")
    return {"gradeSource": "PFF", "license": P.PFF_LICENSE, "results": P.pff_search(name.strip(), league, season, min(limit, 100))}


@private.get("/pff/players/{pff_player_id}")
def pff_player(pff_player_id: str):
    rows = P.pff_player(pff_player_id)
    if not rows:
        raise HTTPException(404, "unknown PFF player id")
    return {"gradeSource": "PFF", "license": P.PFF_LICENSE, "seasons": rows}


@private.get("/pff/distributions/{position}")
def pff_distributions(position: str, league: str | None = None, season: int | None = None):
    sql = "SELECT * FROM gold.pff_position_grade_distributions WHERE position = ?"
    params: list = [position.upper()]
    if league:
        sql += " AND league = ?"; params.append(league)
    if season:
        sql += " AND season = ?"; params.append(season)
    rows = P._rows(sql + " ORDER BY league, season, grade_metric", params)
    if not rows:
        raise HTTPException(404, "no PFF distribution for that position/league/season")
    return {"gradeSource": "PFF", "license": P.PFF_LICENSE, "distributions": rows}


app.include_router(public)
app.include_router(private)
