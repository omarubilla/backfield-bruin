# Live athlete combine assessments — integration guide (live-assessment 1.0.0)

**Base URL:** `https://omar-ubilla--backfield-bruin-api.us-east.modal.run` · **Schema:** [`docs/live_assessment.schema.json`](live_assessment.schema.json)
The existing benchmark endpoints and schema 1.1.0 are unchanged; this is a separate, versioned extension.

## Flow
```
Backfield iPhone app (AR 10-yard dash) ──POST /v1/assessments/ar-dash (Firebase ID token)──►  Bruin API (Modal)
                                                     │ validates contract, normalizes units, compares vs Bruin gold
                                                     │ references, stores raw record in Modal volume (landing)
                                                     ▼
                         201 evaluation (private form: athlete id + asset refs + agentViews)
Gemini/BAND agents ◄── GET /v1/private/assessments/{assessmentId} (service token)  or
LingCode UI        ◄── GET /v1/public/assessments/{assessmentId}/comparison (no auth, identity + assets redacted)

scripts/sync_live_assessments.sh → data/landing/assessments → bruin run →
bronze.live_assessments → silver.live_assessments → gold.live_assessment_comparisons (same rules, audited by checks)
```

## 10-yard split: what the athlete will see
There is **no legitimate 10-yard split reference** in any ingested source ([audit](evidence/ten_yard_split_audit.md)).
A 10-yard dash returns `status: "unavailable"` with the reason, the athlete's measured time, capture-quality metadata and caveats —
**no percentile, no band, no 40-yard substitution**. The only sprint reference is the electronically timed 40-yard dash
(NFL Combine invitees; QB n = 413, seasons 2000–2026).

## Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/assessments` | Firebase ID token **or** service token | submit a live-assessment 1.0.0 input record |
| POST | `/v1/assessments/ar-dash` | Firebase ID token **or** service token | submit the Flutter AR dash result map as-is: `{position, result, athleteId?, evaluationId?}` |
| GET | `/v1/private/assessments/{assessmentId}` | service token | full evaluation (athlete id, asset refs, agent views) |
| GET | `/v1/public/assessments/{assessmentId}/comparison` | none | public-safe evaluation (`athleteId`, `evaluationId`, asset ids removed; `redacted: true`) |
| GET | `/v1/public/live/reference-catalog?position=QB` | none | which drills have a reference cohort (10-yard: unavailable) |
| POST | `/v1/public/live/preview` | none | stateless public-safe comparison preview (nothing stored) |

**Auth.** Firebase ID tokens are verified against project `backfield-17607`; the `athleteId` is then forced to the token's `uid`
(a user can only submit for themselves). The service token (`BRUIN_API_TOKEN`, Modal secret `backfield-bruin-api`) is for trusted
backends only — never in the app bundle or browser. No unauthenticated write endpoint exists. `assessmentId` =
`la-` + 16 hex chars of sha256(athleteId|evaluationId), not guessable without the athlete id.

## Input (POST /v1/assessments)
```json
{
  "evaluationId": "live-combine-001",
  "athleteId": "athlete-001",
  "sport": "football",
  "position": "QB",
  "drill": "10_yard_dash",
  "measurement": {"value": 1.85, "unit": "seconds", "method": "arkit_assisted",
                  "calibrationStatus": "pending", "qualityStatus": "unverified",
                  "appConfidence": {"score": 0.81, "label": "High", "reasons": []}},
  "capturedAt": "2026-11-23T22:00:00Z",
  "videoAssetId": null, "modalJobId": null, "glbAssetId": null,
  "motionObservations": []
}
```
(values fictional) · `drill`: `10_yard_dash | 40_yard_dash | 20_yard_shuttle | three_cone | vertical_jump | broad_jump` ·
`method`: `arkit_assisted | video_timed | hand_timed | self_reported | electronic_laser | electronic_timing | freelap | laser` ·
`calibrationStatus`: `calibrated | uncalibrated | pending` · `qualityStatus`: `verified | unverified | failed`.

**AR dash adapter** (matches the app's actual result map from `ArDashViewController` / `ar_dash_service.dart`):
`elapsedSec → measurement.value`, `distanceYards → drill`, `calibrated → calibrationStatus`, method `arkit_assisted`,
`qualityStatus = unverified` (app confidence is not official verification), `confidence/confidenceLabel/reasons/fps/framesWithPose/...
→ measurement.appConfidence`, `videoAssetId` or `play_id → videoAssetId`.

## Output (evaluation)
| Field | Meaning |
|---|---|
| `assessmentId`, `evaluationId`, `athlete` | identifiers (public form: athlete id + evaluation id removed) |
| `comparison.status` | `verified` · `provisional` · `unavailable` · `rejected` |
| `comparison.percentile` | only when `verified` (electronic timing + verified quality) |
| `comparison.descriptiveBand` | `{interval, interpretation}` for verified/provisional: which p10…p90 interval the value falls in (for times, higher = slower) |
| `comparison.reference` | population, position group, `sampleSize`, seasons, timing method, source, `sourceRef`, distribution p10–p90, and the label *"Professional reference population (NFL Combine invitees) - not a high-school recruiting percentile."* |
| `comparison.reason`, `comparison.caveats[]` | why a percentile is absent; timing-method and calibration discrepancies |
| `assets` | `videoAssetId`, `modalJobId`, `glbAssetId` references only — files stay in Firebase Storage / Modal |
| `motionObservations[]` | model-derived kinematics with `basis: "model_estimated"`, `validated: false`, `comparable_to_reference: false` |
| `agentViews.scout` | comparison, reference cohort, guidance: cite a percentile only when `verified` |
| `agentViews.positionCoach` | actual sprint result + labelled motion estimates; must not present estimates as observed mechanics |
| `agentViews.filmAnalyst` | capture quality (calibration, quality, app confidence, video/reconstruction referenced) and warnings |
| `pipeline` | Bruin run status + `dataQualityExceptions` (130-row nflverse player_id exception) |

## Gemini integration example
```python
import os, requests
B = "https://omar-ubilla--backfield-bruin-api.us-east.modal.run"
H = {"Authorization": f"Bearer {os.environ['BRUIN_API_TOKEN']}"}          # server-side only
ev = requests.get(f"{B}/v1/private/assessments/{assessment_id}", headers=H, timeout=10).json()

scout_ctx  = ev["agentViews"]["scout"]          # status, percentile|None, descriptiveBand, reference{sampleSize,...}, reason
coach_ctx  = ev["agentViews"]["positionCoach"]  # result {drill,value,unit,method}, motionObservations (estimates)
film_ctx   = ev["agentViews"]["filmAnalyst"]    # captureQuality, warnings
ledger_ref = {"assessmentId": ev["assessmentId"], "sources": ev["sources"], "pipelineValidated": ev["pipeline"]["validated"]}
# Prompt rule for all three agents: if scout_ctx["status"] != "verified", say there is no percentile and why (scout_ctx["reason"]).
```
Real end-to-end example responses (sample athlete, clearly labelled): [`docs/evidence/live_e2e/`](evidence/live_e2e).

## Integration status (honest)
- **Working and tested in production:** ingest (service token), AR-dash adapter, public/private reads, reference catalog, Bruin sync + gold audit table.
- **Implemented, not exercised with a real app token yet:** Firebase ID-token auth (verification code path is live; needs a real app user token).
- **Not integrated yet:** the Flutter app does not call these endpoints today; the Modal video-to-3D job and GLB references are accepted as ids but no live reconstruction has been submitted.
