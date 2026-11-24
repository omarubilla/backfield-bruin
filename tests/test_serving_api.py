"""Serving API tests against the gold-only snapshot (scripts/build_serving_db.py)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
os.environ["BRUIN_DUCKDB"] = os.path.join(ROOT, "data", "serving.duckdb")
os.environ["BRUIN_API_TOKEN"] = "test-token-not-real"

import jsonschema  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.serving_api import app  # noqa: E402

c = TestClient(app)
SCHEMA = json.load(open(os.path.join(ROOT, "docs", "athlete_benchmark.schema.json")))
PFF_VALUE_KEYS = ("\"pff_grade_offense\":", "\"pass_dropbacks\":", "\"snaps_offense\":", "\"grade_value\":", "\"pff_grade_pass_pctl_in_position\":")


def test_public_endpoints_gemini_contract():
    for path in ("/v1/schema", "/v1/public/pipeline/status", "/v1/public/benchmarks/QB",
                 "/v1/public/athletes/bf-demo-qb-001/benchmark", "/v1/public/athletes/pfr:CookBr03/benchmark",
                 "/v1/public/showcase", "/v1/public/players/featured"):
        assert c.get(path).status_code == 200, path
    for aid in ("bf-demo-qb-001", "pfr:CookBr03"):
        jsonschema.Draft202012Validator(SCHEMA).validate(c.get(f"/v1/public/athletes/{aid}/benchmark").json())


def test_public_responses_carry_no_pff_values():
    for path in ("/v1/public/athletes/pfr:CookBr03/benchmark", "/v1/public/showcase", "/v1/public/players/featured"):
        body = c.get(path).text
        assert not any(k in body for k in PFF_VALUE_KEYS), path
    d = c.get("/v1/public/athletes/pfr:CookBr03/benchmark").json()["pffContext"]
    assert d["redacted"] and d["playerSeasons"] == [] and all(r["distribution"] is None for r in d["positionReference"])


def test_private_requires_token():
    assert c.get("/v1/private/athletes/pfr:CookBr03/benchmark").status_code == 401
    assert c.get("/v1/private/athletes/pfr:CookBr03/benchmark", headers={"Authorization": "Bearer nope"}).status_code == 401
    r = c.get("/v1/private/athletes/pfr:CookBr03/benchmark", headers={"Authorization": "Bearer test-token-not-real"})
    assert r.status_code == 200 and r.json()["pffContext"]["playerSeasons"]


def test_showcase_reports_exception_and_counts():
    s = c.get("/v1/public/showcase").json()
    assert s["pipeline"]["validated"] is True
    assert s["pipeline"]["dataQualityExceptions"][0]["check"].startswith("bronze.nfl_player_stats")
    assert s["headline"]["identityLinksByProviderId"] > 2000 and s["headline"]["pffGradeRows"] > 90000
    assert s["exampleAthlete"]["athleteId"] == "pfr:CookBr03" and s["lineage"]["assetCount"] >= 32
