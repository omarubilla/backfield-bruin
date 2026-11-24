"""Live athlete combine assessments: input contract, normalization and defensible comparison.

Schema: docs/live_assessment.schema.json (live-assessment 1.0.0). The comparison reads the Bruin gold
tables gold.live_reference_catalog and gold.live_reference_values; the same rules are implemented in
SQL by gold.live_assessment_comparisons (a test checks both agree).

Status vocabulary per metric:
  verified     comparable timing method + verified quality -> percentile vs the reference cohort
  provisional  reference exists but timing method / quality is not equivalent -> descriptive band only
  unavailable  no legitimate reference cohort (e.g. 10-yard split)            -> no percentile, explicit reason
  rejected     capture quality failed                                          -> not compared
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from bruin_export import payload as P

LIVE_SCHEMA_VERSION = "1.0.0"

DRILL_METRIC = {
    "10_yard_dash": "ten_yd_split_sec", "40_yard_dash": "forty_sec", "20_yard_shuttle": "shuttle_sec",
    "three_cone": "cone_sec", "vertical_jump": "vertical_in", "broad_jump": "broad_jump_in",
}
UNIT_FACTORS = {  # -> canonical unit of the metric
    "seconds": ("s", 1.0), "second": ("s", 1.0), "sec": ("s", 1.0), "s": ("s", 1.0),
    "milliseconds": ("s", 0.001), "ms": ("s", 0.001),
    "inches": ("in", 1.0), "in": ("in", 1.0), "cm": ("in", 1 / 2.54), "centimeters": ("in", 1 / 2.54),
}
# Timing methods considered equivalent to the NFL Combine's electronic timing.
COMPARABLE_METHODS = {"electronic_laser", "electronic_timing", "freelap", "laser"}
KNOWN_METHODS = COMPARABLE_METHODS | {"arkit_assisted", "video_timed", "hand_timed", "self_reported"}
BANDS = [("p10", "below p10"), ("p25", "p10-p25"), ("p50", "p25-p50"), ("p75", "p50-p75"), ("p90", "p75-p90")]


class Measurement(BaseModel):
    value: float = Field(gt=0)
    unit: str
    method: str
    calibrationStatus: Literal["calibrated", "uncalibrated", "pending"]
    qualityStatus: Literal["verified", "unverified", "failed"]
    appConfidence: dict | None = None  # e.g. AR dash {score, label, reasons}

    @field_validator("unit")
    @classmethod
    def unit_known(cls, v):
        if v.lower() not in UNIT_FACTORS:
            raise ValueError(f"unsupported unit '{v}'")
        return v.lower()

    @field_validator("method")
    @classmethod
    def method_known(cls, v):
        if v.lower() not in KNOWN_METHODS:
            raise ValueError(f"unsupported method '{v}' (use one of {sorted(KNOWN_METHODS)})")
        return v.lower()


class MotionObservation(BaseModel):
    name: str
    value: float | str | None = None
    unit: str | None = None
    source: str = "modal_video_to_motion"
    validated: bool = False


class Assessment(BaseModel):
    evaluationId: str = Field(min_length=3, max_length=80)
    athleteId: str = Field(min_length=1, max_length=128)
    sport: Literal["football"] = "football"
    position: str = Field(min_length=1, max_length=8)
    drill: Literal["10_yard_dash", "40_yard_dash", "20_yard_shuttle", "three_cone", "vertical_jump", "broad_jump"]
    measurement: Measurement
    capturedAt: datetime | None = None
    videoAssetId: str | None = None
    modalJobId: str | None = None
    glbAssetId: str | None = None
    motionObservations: list[MotionObservation] = []
    isSample: bool = False


def from_ar_dash(raw: dict, athlete_id: str, position: str, evaluation_id: str | None = None) -> Assessment:
    """Adapter for the Backfield Flutter AR dash result map (lib/services/ar_dash_service.dart / ArDashViewController)."""
    yards = int(raw.get("distanceYards") or 10)
    label = str(raw.get("confidenceLabel") or "Low")
    return Assessment(
        evaluationId=evaluation_id or f"ardash-{uuid.uuid4().hex[:10]}",
        athleteId=athlete_id, position=position, drill=f"{yards}_yard_dash",
        measurement=Measurement(
            value=float(raw["elapsedSec"]), unit="seconds", method="arkit_assisted",
            calibrationStatus="calibrated" if raw.get("calibrated") else "uncalibrated",
            qualityStatus="unverified",  # app confidence is not an official verification
            appConfidence={"score": raw.get("confidence"), "label": label, "reasons": raw.get("reasons", []),
                           "fps": raw.get("fps"), "framesWithPose": raw.get("framesWithPose"),
                           "framesAnalyzed": raw.get("framesAnalyzed"), "cameraTravelM": raw.get("cameraTravelM"),
                           "calibrationErrorPct": raw.get("calibrationErrorPct"), "camera": raw.get("camera")}),
        videoAssetId=raw.get("videoAssetId") or raw.get("play_id"),
    )


def _band(value: float, ref: dict, lower_is_better: bool) -> str:
    """Interval of the reference distribution the value falls in (descriptive, not a percentile)."""
    for key, label in BANDS:
        if value <= ref[key]:
            return label
    return "above p90"


def compare(a: Assessment) -> dict:
    metric = DRILL_METRIC[a.drill]
    canon_unit, factor = UNIT_FACTORS[a.measurement.unit]
    value = round(a.measurement.value * factor, 3)
    pos = a.position.upper()
    cat = P._rows("SELECT * FROM gold.live_reference_catalog WHERE metric = ? AND position_group = ?", [metric, pos])
    c = cat[0] if cat else None
    method = a.measurement.method
    caveats = []
    if a.measurement.calibrationStatus != "calibrated":
        caveats.append(f"Capture calibration is '{a.measurement.calibrationStatus}'; distances may be off and the time is an estimate.")
    if a.measurement.qualityStatus != "verified":
        caveats.append("Measurement quality is not verified by an official timer or reviewer.")
    if method not in COMPARABLE_METHODS:
        caveats.append(f"Timing method '{method}' is not equivalent to the electronic timing used at the NFL Combine; "
                       "no validated conversion exists, so no percentile is reported.")

    result = {"metric": metric, "drill": a.drill, "value": value, "unit": canon_unit, "method": method,
              "calibrationStatus": a.measurement.calibrationStatus, "qualityStatus": a.measurement.qualityStatus,
              "appConfidence": a.measurement.appConfidence, "percentile": None, "descriptiveBand": None,
              "reference": None, "caveats": caveats}

    if a.measurement.qualityStatus == "failed":
        return result | {"status": "rejected", "reason": "Capture quality failed; the measurement is not compared."}
    if c is None or not c["reference_available"]:
        return result | {"status": "unavailable",
                         "reason": (c or {}).get("unavailable_reason") or f"No reference cohort for {metric} at position {pos}."}
    ref = {"population": c["reference_population"], "positionGroup": c["position_group"], "sampleSize": c["n"],
           "seasons": {"from": c["season_min"], "to": c["season_max"]}, "timingMethod": c["reference_timing_method"],
           "source": c["source"], "sourceRef": f"bruin:gold.live_reference_catalog/{pos}/{metric}",
           "distribution": {k: c[k] for k in ("p10", "p25", "p50", "p75", "p90")},
           "label": "Professional reference population (NFL Combine invitees) - not a high-school recruiting percentile."}
    result["reference"] = ref
    interval = _band(value, c, c["lower_is_better"])
    result["descriptiveBand"] = {
        "interval": interval,
        "interpretation": (f"The value lies in the {interval} interval of the reference values ("
                           + ("for times, higher intervals are slower" if c["lower_is_better"] else "higher intervals are better")
                           + "). Descriptive placement only; not a percentile unless status is 'verified'."),
    }
    if method in COMPARABLE_METHODS and a.measurement.qualityStatus == "verified":
        vals = [r["value"] for r in P._rows("SELECT value FROM gold.live_reference_values WHERE position_group = ? AND metric = ?", [pos, metric])]
        beats = sum((v > value) if c["lower_is_better"] else (v < value) for v in vals)
        result["percentile"] = round(100.0 * beats / len(vals), 1)
        return result | {"status": "verified", "reason": None}
    return result | {"status": "provisional",
                     "reason": "Reference exists, but the capture method/quality is not equivalent; descriptive placement only."}


def evaluate(a: Assessment, assessment_id: str | None = None) -> dict:
    """Full live-assessment evaluation (private form). Use public_view() for unauthenticated responses."""
    cmp_ = compare(a)
    st = P.pipeline_status()
    aid = assessment_id or "la-" + hashlib.sha256(f"{a.athleteId}|{a.evaluationId}".encode()).hexdigest()[:16]
    motion = [m.model_dump() | {"basis": "model_estimated", "comparable_to_reference": False} for m in a.motionObservations]
    film_warnings = list(cmp_["caveats"])
    conf = a.measurement.appConfidence or {}
    film_warnings += [f"App capture note: {r}" for r in (conf.get("reasons") or [])]
    if not a.videoAssetId:
        film_warnings.append("No source video referenced; no mechanics can be observed from this assessment.")
    if a.motionObservations:
        film_warnings.append("Motion observations are model-estimated from video (not directly measured) and unvalidated.")
    return {
        "schemaVersion": LIVE_SCHEMA_VERSION,
        "assessmentId": aid,
        "evaluationId": a.evaluationId,
        "athlete": {"athleteId": a.athleteId, "position": a.position.upper(), "sport": a.sport, "isSample": a.isSample},
        "capture": {"capturedAt": a.capturedAt.isoformat() if a.capturedAt else None,
                    "receivedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "assets": {"videoAssetId": a.videoAssetId, "modalJobId": a.modalJobId, "glbAssetId": a.glbAssetId,
                   "storage": "existing Backfield storage (Firebase Storage / Modal); Bruin stores references only"},
        "comparison": cmp_,
        "motionObservations": motion,
        "agentViews": {
            "scout": {"metric": cmp_["metric"], "status": cmp_["status"], "value": cmp_["value"], "unit": cmp_["unit"],
                      "percentile": cmp_["percentile"], "descriptiveBand": cmp_["descriptiveBand"],
                      "reference": cmp_["reference"], "reason": cmp_["reason"],
                      "guidance": "Only cite a percentile when status is 'verified'. Say 'no reference cohort' when 'unavailable'."},
            "positionCoach": {"result": {"drill": a.drill, "value": cmp_["value"], "unit": cmp_["unit"], "method": cmp_["method"]},
                              "motionObservations": motion,
                              "guidance": "Coach from the sprint result. Motion observations are model estimates; do not present them as measured or as observed mechanics unless video evidence is reviewed."},
            "filmAnalyst": {"captureQuality": {"calibrationStatus": cmp_["calibrationStatus"], "qualityStatus": cmp_["qualityStatus"],
                                               "appConfidence": conf or None, "videoReferenced": bool(a.videoAssetId),
                                               "reconstructionReferenced": bool(a.modalJobId or a.glbAssetId)},
                            "warnings": film_warnings,
                            "guidance": "Flag capture limitations; request a calibrated or electronically timed retest before strong conclusions."},
        },
        "methodology": [
            "Units normalized to seconds / inches; drill mapped to a combine metric.",
            "Percentile only for electronically timed, verified measurements vs same-position NFL Combine invitees (direction-aware).",
            "AR-assisted, video or hand timing: descriptive band only; no validated conversion to electronic timing is applied.",
            "No 10-yard split reference exists in the ingested sources; such results are reported as unavailable.",
        ],
        "sources": ["bruin:gold.live_reference_catalog", "bruin:gold.live_reference_values", "nflverse NFL Combine (public)"],
        "pipeline": {k: st.get(k) for k in ("status", "validated", "finished_at", "bruin_version")}
                    | {"dataQualityExceptions": st.get("dataQualityExceptions")},
    }


def public_view(doc: dict) -> dict:
    """Unauthenticated form: no athlete identifier, no asset references, no app internals."""
    d = json.loads(json.dumps(doc))
    d["athlete"] = {"athleteId": None, "athleteRef": "redacted", "position": doc["athlete"]["position"],
                    "sport": doc["athlete"]["sport"], "isSample": doc["athlete"]["isSample"]}
    d["assets"] = {k: (None if k != "storage" else v) for k, v in doc["assets"].items()} | {
        "videoReferenced": bool(doc["assets"]["videoAssetId"]), "reconstructionReferenced": bool(doc["assets"]["modalJobId"] or doc["assets"]["glbAssetId"])}
    d["evaluationId"] = None
    d["redacted"] = True
    return d
