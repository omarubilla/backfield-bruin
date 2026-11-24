"""Live athlete assessment routes (mounted by api/serving_api.py).

  POST /v1/assessments                      submit a live-assessment 1.0.0 record      (auth required)
  POST /v1/assessments/ar-dash              submit the Flutter AR dash result map      (auth required)
  GET  /v1/private/assessments/{id}         full evaluation incl. athlete id + assets   (service token)
  GET  /v1/public/assessments/{id}/comparison   public-safe comparison (identity + assets redacted)
  GET  /v1/public/live/reference-catalog?position=QB

Auth for writes: either the server token (Authorization: Bearer <BRUIN_API_TOKEN>, trusted backends)
or a Firebase ID token from the Backfield app (project backfield-17607); with a Firebase token the
athleteId is forced to the token's uid so a user can only submit for themselves.
"""
import json
import os
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from bruin_export import live as L
from bruin_export import payload as P

LANDING = os.environ.get("LIVE_LANDING_DIR", os.path.join(P.ROOT, "data", "landing", "assessments"))
FIREBASE_PROJECT = os.environ.get("FIREBASE_PROJECT_ID", "backfield-17607")
ID_RE = re.compile(r"^la-[0-9a-f]{16}$")
router = APIRouter()
_volume = None  # set by the Modal app so writes are committed to the volume


def set_volume(v):
    global _volume
    _volume = v


def _caller(authorization: str | None = Header(default=None)) -> dict:
    import hmac
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    expected = os.environ.get("BRUIN_API_TOKEN")
    if expected and hmac.compare_digest(token.encode(), expected.encode()):
        return {"kind": "service", "uid": None}
    try:  # Firebase ID token from the Backfield app
        from google.auth.transport import requests as greq
        from google.oauth2 import id_token
        claims = id_token.verify_firebase_token(token, greq.Request(), audience=FIREBASE_PROJECT)
        if not claims or not claims.get("sub"):
            raise ValueError("no subject")
        return {"kind": "firebase", "uid": claims["sub"]}
    except Exception:  # noqa: BLE001
        raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})


def _service_only(caller: dict = Depends(_caller)):
    if caller["kind"] != "service":
        raise HTTPException(403, "service token required")
    return caller


def _store(doc: dict, inp: dict):
    os.makedirs(LANDING, exist_ok=True)
    with open(os.path.join(LANDING, f"{doc['assessmentId']}.json"), "w") as f:
        json.dump({"input": inp, "evaluation": doc}, f, default=str)
    if _volume is not None:
        _volume.commit()


def _load(assessment_id: str) -> dict:
    if not ID_RE.match(assessment_id):
        raise HTTPException(404, "unknown assessment")
    if _volume is not None:
        _volume.reload()
    p = os.path.join(LANDING, f"{assessment_id}.json")
    if not os.path.exists(p):
        raise HTTPException(404, "unknown assessment")
    return json.load(open(p))


def _submit(a: L.Assessment, caller: dict) -> dict:
    if caller["kind"] == "firebase":
        a.athleteId = caller["uid"]
        a.isSample = False
    doc = L.evaluate(a)
    _store(doc, json.loads(a.model_dump_json()))
    return doc


@router.post("/v1/assessments", status_code=201)
def submit(a: L.Assessment, caller: dict = Depends(_caller)):
    return _submit(a, caller)


class ArDashIn(BaseModel):
    position: str
    result: dict
    athleteId: str | None = None
    evaluationId: str | None = None


@router.post("/v1/assessments/ar-dash", status_code=201)
def submit_ar_dash(body: ArDashIn, caller: dict = Depends(_caller)):
    if "elapsedSec" not in body.result:
        raise HTTPException(422, "result.elapsedSec missing (expected the AR dash result map)")
    a = L.from_ar_dash(body.result, body.athleteId or caller.get("uid") or "unknown", body.position, body.evaluationId)
    return _submit(a, caller)


@router.get("/v1/private/assessments/{assessment_id}")
def private_assessment(assessment_id: str, caller: dict = Depends(_service_only)):
    return _load(assessment_id)["evaluation"]


@router.get("/v1/public/assessments/{assessment_id}/comparison")
def public_assessment(assessment_id: str):
    return L.public_view(_load(assessment_id)["evaluation"])


@router.get("/v1/public/live/reference-catalog")
def reference_catalog(position: str | None = None):
    sql = "SELECT * FROM gold.live_reference_catalog"
    params = []
    if position:
        sql += " WHERE position_group = ?"
        params.append(position.upper())
    return {"source": "bruin:gold.live_reference_catalog", "audit": "docs/evidence/ten_yard_split_audit.md",
            "references": P._rows(sql + " ORDER BY position_group, metric", params)}


@router.post("/v1/public/live/preview")
def preview(a: L.Assessment):
    """Stateless, public-safe comparison preview (nothing stored, identity redacted)."""
    doc = L.evaluate(a, assessment_id="la-" + uuid.uuid4().hex[:16])
    return L.public_view(doc)
