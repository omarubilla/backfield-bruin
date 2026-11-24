"""Deployed Bruin benchmark API (Modal, HTTPS).

Public (no auth)                                    PFF values redacted
  GET /v1/health
  GET /v1/schema
  GET /v1/public/pipeline/status
  GET /v1/public/athletes
  GET /v1/public/athletes/{athlete_id}/benchmark    schema 1.1.0, pffContext redacted
  GET /v1/public/benchmarks/{position}              NFL Combine distributions (nflverse, public)
  GET /v1/public/players/featured                   real combine athletes linked to PFF by provider id
  GET /v1/public/showcase                           Bruin sponsor showcase (status, stages, counts, lineage, example)
  (real players use athleteId = "pfr:<pfr_id>", e.g. /v1/public/athletes/pfr:CookBr03/benchmark)

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

LINEAGE_PATH = os.environ.get("BRUIN_LINEAGE", os.path.join(P.ROOT, "docs", "evidence", "lineage.json"))
SHOWCASE_PLAYER = os.environ.get("SHOWCASE_PLAYER", "pfr:CookBr03")
SCHEMA_PATH = os.environ.get("BRUIN_SCHEMA", os.path.join(P.ROOT, "docs", "athlete_benchmark.schema.json"))
PUBLIC_PFF_NOTE = ("Redacted in public responses: PFF Pro licensed values are served only to authenticated "
                   "server-side consumers (/v1/private/*).")

app = FastAPI(title="Backfield Bruin Benchmark API", version=P.SCHEMA_VERSION, docs_url="/docs", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["Authorization"])


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


@public.get("/players/featured")
def featured(limit: int = 10):
    return [r | {"benchmarkUrl": f"/v1/public/athletes/{r['athlete_id']}/benchmark"} for r in P.featured_players(min(limit, 50))]


@public.get("/showcase")
def showcase():
    """Public-safe Bruin showcase for LingCode: counts, checks, lineage, one public combine benchmark and
    one real-athlete comparison. No PFF values (counts only), no credentials, no internal paths."""
    st = P.pipeline_status()
    counts = P._rows("SELECT layer, asset, provider, row_count, description FROM gold.lineage_row_counts")
    lineage = json.load(open(LINEAGE_PATH))
    stages = {layer: [a for a, v in lineage["assets"].items() if v["layer"] == layer] for layer in ("bronze", "silver", "gold")}
    forty = P._rows("SELECT metric, unit, n, missing_n, p10, p25, p50, p75, p90, season_min, season_max FROM gold.combine_benchmarks "
                    "WHERE position_group = 'QB' ORDER BY metric")
    ex = _public_payload(SHOWCASE_PLAYER)
    fresh = P._rows("SELECT dataset, provider, ingested_at FROM gold.pipeline_quality WHERE ingested_at IS NOT NULL")
    by = {r["asset"]: r["row_count"] for r in counts}
    return {
        "title": "Backfield AI Scouting Combine - powered by Bruin",
        "pipeline": {k: st.get(k) for k in ("status", "validated", "bruin_version", "started_at", "finished_at", "git_commit")}
                    | {"assets": st.get("assets"), "qualityChecks": {k: v for k, v in (st.get("quality_checks") or {}).items() if k != "failures"},
                       "dataQualityExceptions": st.get("dataQualityExceptions")},
        "stages": [
            {"layer": "bronze", "purpose": "Raw ingest per provider, lineage columns, licence tags; providers kept separate", "assets": stages["bronze"]},
            {"layer": "silver", "purpose": "Normalized entities: athletes keyed on provider ids, long-form measurements with units, PFF player-seasons, identity crosswalk", "assets": stages["silver"]},
            {"layer": "gold", "purpose": "Position benchmarks, athlete evaluation contracts, PFF position distributions, lineage counts", "assets": stages["gold"]},
        ],
        "rowCounts": counts,
        "headline": {
            "nflCombineResults": by.get("bronze.nfl_combine"), "measurementsNormalized": by.get("silver.physical_measurements"),
            "pffStatRows": sum(by.get(a, 0) for a in ("bronze.pff_passing_summary", "bronze.pff_rushing_summary", "bronze.pff_receiving_summary", "bronze.pff_offense_summary")),
            "pffGradeRows": by.get("silver.pff_grades"), "identityLinksByProviderId": by.get("silver.athlete_identity_xref [linked]"),
            "linkedToCombine": by.get("silver.athlete_identity_xref [linked to combine]"),
            "realPlayerBenchmarkRows": by.get("gold.player_benchmark_results"),
        },
        "lineage": {"edges": lineage["edges"], "assetCount": len(lineage["assets"])},
        "positionBenchmark": {"position": "QB", "source": "nflverse NFL Combine via gold.combine_benchmarks", "metrics": forty},
        "exampleAthlete": {
            "athleteId": ex["athlete"]["athleteId"], "displayName": ex["athlete"]["displayName"], "position": ex["athlete"]["position"],
            "level": ex["athlete"]["level"], "identity": ex["athlete"]["identityProvider"], "evaluationId": ex["evaluationId"],
            "measurements": [{k: m[k] for k in ("metric", "value", "unit", "percentile", "percentile_status")}
                             | {"cohortSize": (m["benchmark"] or {}).get("sample_size"), "missingReason": m["missing"]["reason"]}
                             for m in ex["measurements"]],
            "pff": {"matched": ex["pffContext"]["athleteMatch"]["matched"], "pffPlayerId": ex["pffContext"]["athleteMatch"]["pffPlayerId"],
                    "values": "redacted (PFF Pro licence) - available to authenticated server-side consumers"},
            "benchmarkUrl": f"/v1/public/athletes/{ex['athlete']['athleteId']}/benchmark",
        },
        "freshness": fresh,
        "methodology": [
            "Percentile = share of the same-position NFL Combine cohort the athlete beats, direction-aware; real players are excluded from their own cohort.",
            "Percentiles are only reported for measured values with a cohort of n >= 20; everything else is flagged, never imputed.",
            "Identity links use provider ids only: PFF player_id = nflverse players.pff_id -> gsis_id / pfr_id -> combine record.",
            "PFF grades are PFF's proprietary 0-100 evaluations, labelled separately, never averaged with combine benchmarks, and redacted publicly.",
            "Every run records execution status and quality checks; non-blocking failures are surfaced as dataQualityExceptions.",
        ],
        "sources": [
            {"provider": "nflverse", "use": "NFL Combine, player identity, weekly stats", "license": "public open data (attribution)"},
            {"provider": "PFF", "use": "NCAA/NFL season stats, snaps, PFF grades", "license": "PFF Pro - internal; values redacted publicly"},
            {"provider": "Backfield", "use": "athlete evidence (synthetic demo athlete in this build)", "license": "synthetic"},
            {"provider": "CollegeFootballData", "use": "provider implemented; key not configured", "license": "CFBD terms"},
        ],
    }


app.include_router(public)
app.include_router(private)

from api.live_routes import router as live_router  # noqa: E402

app.include_router(live_router)
