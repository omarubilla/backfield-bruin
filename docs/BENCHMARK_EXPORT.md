# Bruin athlete benchmark export — integration contract (v1.1.0)

The Bruin pipeline publishes validated athlete benchmark results for the coaching agents
(Gemini repo). Consume them over HTTP **or** as portable JSON files — same payload either way.

| | |
|---|---|
| Schema | [`docs/athlete_benchmark.schema.json`](athlete_benchmark.schema.json) (JSON Schema 2020-12) |
| Sample | [`docs/sample_payload.json`](sample_payload.json) |
| Portable files | `exports/<athleteId>.json` (public, PFF values redacted) · `exports/internal/<athleteId>.json` (full, git-ignored). Regenerate with `python -m bruin_export.payload --all [--redact-pff] --out <dir>` |
| API base | `http://127.0.0.1:8787` (start: `scripts/run_bruin_api.sh`; set `HOST=0.0.0.0` to expose on the LAN) |

## Endpoints (read-only, CORS open, GET only)

| Method | Path | Returns |
|---|---|---|
| GET | `/v1/health` | `{ok, schemaVersion, pipelineValidated, lastRunFinishedAt}` |
| GET | `/v1/athletes` | athletes in the gold layer + their benchmark URLs |
| GET | **`/v1/athletes/{athleteId}/benchmark`** | **evaluation payload** (main integration point) |
| GET | `/v1/evaluations/{evaluationId}` | same payload by id; `410` if the id is from an older data version |
| GET | `/v1/pipeline/status` | latest Bruin run: assets, quality checks, providers |
| GET | `/v1/benchmarks/{position}` | raw cohort distributions (`gold.combine_benchmarks`) |
| GET | `/v1/schema` | the JSON Schema |
| GET | `/v1/pff/players?name=&league=&season=` | PFF player lookup (stats, snaps, PFF grades, within-position grade percentile, identity links) |
| GET | `/v1/pff/players/{pffPlayerId}` | all PFF seasons for one player |
| GET | `/v1/pff/distributions/{position}?league=&season=` | PFF grade distributions within a position |

```bash
curl http://127.0.0.1:8787/v1/athletes/bf-demo-qb-001/benchmark
```

## Payload fields

| Requirement | Field |
|---|---|
| evaluationId | `evaluationId` — deterministic hash of athlete + validated measurements + pipeline run (`bfe-<athleteId>-<12 hex>`) |
| athlete identity & position | `athlete.{athleteId, displayName, position, level, gradYear, isSynthetic, identityProvider}` |
| measurements, units, source | `measurements[].{metric, definition, value, unit, lower_is_better, source.{provider, record_id, capture_method, capture_confidence, observed_on, license_category}}` |
| benchmark cohort & sample size | `measurements[].benchmark.{cohort, position_group, reference_population, sample_size, missing_in_cohort, seasons, distribution.p10..p90, source_ref}` |
| percentile (only when calculable) | `measurements[].percentile` + `percentile_status` ∈ `calculated · not_measured · no_reference_cohort · insufficient_cohort` |
| missing-data indicators | `measurements[].missing.{value_missing, cohort_missing, percentile_withheld, reason}`, `summary.missing_values`, `summary.missing_cohorts` |
| source references | `sourceReferences[]`, `measurements[].benchmark.source_ref`, `measurements[].source.record_id` |
| pipeline execution status | `pipeline.{status, validated, bruin_version, git_commit, started_at, finished_at, exit_code, assets, quality_checks, providers}` |

### `pffContext` (new in 1.1.0)
| Field | Meaning |
|---|---|
| `status` | `available` when the PFF key authenticates and is entitled (PFF Pro) |
| `labeling` | PFF grades are PFF's proprietary 0-100 evaluations, `gradeSource: "PFF"`; not Backfield evaluations |
| `athleteMatch` | provider-id match only (`pffPlayerId`); HS athletes are unmatched by design |
| `playerSeasons[]` | `gold.pff_player_context` rows for a matched athlete: stats (`pass_*`, `rush_*`, `rec_*`), snaps, `pff_grade_*`, `*_pctl_in_position` (PFF vs PFF, same league/season/position, qualified players), `gsis_id`/`pfr_id`/`combine_athlete_key` |
| `positionReference[]` | PFF grade distributions for the athlete's position: league, season, `gradeMetric`, cohort qualifier + `sampleSize`, `distribution` p10-p90 |
| `redacted` | `true` in committed/public copies (values removed); the LAN API serves full values |
| `license` | PFF Pro, internal analysis only; raw rows never exported; redistribution not confirmed |

### Rules the agents can rely on
- PFF grades are **never** mixed into `measurements[]` or averaged with combine percentiles; they only appear under `pffContext` and `/v1/pff/*`.
- `percentile` is non-null **only** when `percentile_status == "calculated"` (measured value, position cohort with n ≥ 20). Enforced by a Bruin custom check and by the tests.
- Percentile = share of the cohort the athlete beats, direction-aware (`lower_is_better`). Descriptive, **not** a grade or projection.
- `comparability: "caveat"` means the capture method is not like-for-like with electronic combine timing (hand-timed, self-reported, uncalibrated); read `comparability_note`.
- Metrics with a cohort that the athlete has not recorded are still listed (`measured: false`), so gaps are explicit.
- `ten_yd_split_sec` never gets a percentile: the nflverse combine data has no 10-yard split, and nothing is imputed.
- `athlete.isSynthetic: true` = demo record. The current athlete `bf-demo-qb-001` is synthetic.
- `pipeline.validated` is `true` when all assets ran and no **blocking** quality check failed. Current known non-blocking failure: 130 upstream nflverse weekly-stat rows lack a player id (excluded in silver).

## Refresh
```bash
scripts/run_pipeline.sh                      # bruin run + logs/bruin_run_latest.{log,json}
python -m pytest tests                       # export contract tests
python -m bruin_export.payload --all --out exports/
```
New athletes: add records to `seeds/backfield_demo_athletes.json` (or replace the Source D provider with the authorised Backfield API) and re-run.
