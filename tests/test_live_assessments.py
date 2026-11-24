"""Live athlete assessment tests: contract, comparison rules, SQL/Python parity, auth, redaction."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
os.environ["BRUIN_DUCKDB"] = os.path.join(ROOT, "data", "serving.duckdb")
os.environ["BRUIN_API_TOKEN"] = "test-token-not-real"
os.environ["LIVE_LANDING_DIR"] = os.path.join(ROOT, "data", "test_landing")

import duckdb  # noqa: E402
import jsonschema  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.serving_api import app  # noqa: E402
from bruin_export import live as L  # noqa: E402

c = TestClient(app)
SCHEMA = json.load(open(os.path.join(ROOT, "docs", "live_assessment.schema.json")))
SAMPLES = json.load(open(os.path.join(ROOT, "seeds", "live_assessment_samples.json")))["assessments"]
AUTH = {"Authorization": "Bearer test-token-not-real"}


def validate(doc):
    jsonschema.Draft202012Validator(SCHEMA).validate(json.loads(json.dumps(doc, default=str)))


def test_samples_match_contract_and_rules():
    out = {s["evaluationId"]: L.evaluate(L.Assessment(**s)) for s in SAMPLES}
    for d in out.values():
        validate(d)
    ten, ar40, el40 = (out[f"sample-live-combine-00{i}"]["comparison"] for i in (1, 2, 3))
    assert ten["status"] == "unavailable" and ten["percentile"] is None and ten["reference"] is None and ten["descriptiveBand"] is None
    assert ar40["status"] == "provisional" and ar40["percentile"] is None and ar40["descriptiveBand"]["interval"] == "p75-p90"
    assert ar40["reference"]["sampleSize"] == 413 and "not a high-school" in ar40["reference"]["label"]
    assert el40["status"] == "verified" and el40["percentile"] is not None


def test_python_matches_bruin_gold_sql():
    con = duckdb.connect(os.path.join(ROOT, "data", "scouting.duckdb"), read_only=True)
    gold = {r[0]: r[1:] for r in con.execute(
        "SELECT evaluation_id, status, percentile, descriptive_band FROM gold.live_assessment_comparisons WHERE is_sample").fetchall()}
    for s in SAMPLES:
        cmp_ = L.evaluate(L.Assessment(**s))["comparison"]
        band = (cmp_["descriptiveBand"] or {}).get("interval")
        assert gold[s["evaluationId"]] == (cmp_["status"], cmp_["percentile"], band), s["evaluationId"]


def test_never_derives_ten_yard_from_forty():
    s = dict(SAMPLES[0], measurement=dict(SAMPLES[0]["measurement"], method="electronic_laser", qualityStatus="verified"))
    cmp_ = L.evaluate(L.Assessment(**s))["comparison"]
    assert cmp_["status"] == "unavailable" and cmp_["percentile"] is None


def test_ingest_requires_auth_and_public_view_redacts():
    body = SAMPLES[1]
    assert c.post("/v1/assessments", json=body).status_code == 401
    assert c.post("/v1/assessments", json=body, headers={"Authorization": "Bearer forged"}).status_code == 401
    r = c.post("/v1/assessments", json=body, headers=AUTH)
    assert r.status_code == 201
    aid = r.json()["assessmentId"]
    pub = c.get(f"/v1/public/assessments/{aid}/comparison").json()
    validate(pub)
    assert pub["redacted"] and pub["athlete"]["athleteId"] is None and pub["evaluationId"] is None
    assert pub["assets"]["videoAssetId"] is None and pub["assets"]["videoReferenced"] is True
    assert "SAMPLE-athlete-001" not in json.dumps(pub)
    assert c.get(f"/v1/private/assessments/{aid}").status_code == 401
    assert c.get(f"/v1/private/assessments/{aid}", headers=AUTH).json()["athlete"]["athleteId"] == "SAMPLE-athlete-001"
    assert c.get("/v1/public/assessments/la-0000000000000000/comparison").status_code == 404


def test_ar_dash_adapter_matches_flutter_result_map():
    result = {"elapsedSec": 1.74, "startCrossSec": 2.1, "finishCrossSec": 3.84, "distanceM": 9.144, "distanceYards": 10,
              "calibrated": True, "isEstimate": False, "confidence": 0.81, "confidenceLabel": "High", "reasons": [],
              "fps": 60, "framesAnalyzed": 300, "framesWithPose": 288, "camera": "back"}
    r = c.post("/v1/assessments/ar-dash", json={"position": "QB", "result": result, "athleteId": "SAMPLE-athlete-002"}, headers=AUTH)
    assert r.status_code == 201
    d = r.json()
    validate(d)
    assert d["comparison"]["drill"] == "10_yard_dash" and d["comparison"]["method"] == "arkit_assisted"
    assert d["comparison"]["status"] == "unavailable" and d["comparison"]["appConfidence"]["label"] == "High"


def test_motion_observations_are_labelled_estimates():
    s = dict(SAMPLES[1], motionObservations=[{"name": "peak_hip_flexion", "value": 78, "unit": "deg"}])
    d = L.evaluate(L.Assessment(**s))
    validate(d)
    m = d["agentViews"]["positionCoach"]["motionObservations"][0]
    assert m["basis"] == "model_estimated" and m["validated"] is False and m["comparable_to_reference"] is False
    assert any("model-estimated" in w for w in d["agentViews"]["filmAnalyst"]["warnings"])


def test_reference_catalog_public():
    r = c.get("/v1/public/live/reference-catalog?position=QB").json()["references"]
    ten = [x for x in r if x["metric"] == "ten_yd_split_sec"][0]
    assert ten["reference_available"] is False and ten["n"] is None
