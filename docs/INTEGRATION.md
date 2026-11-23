# Bruin Benchmark API — integration guide for Gemini/BAND and LingCode

**Base URL (HTTPS, Modal):** `https://omar-ubilla--backfield-bruin-api.us-east.modal.run`
**Schema:** 1.1.0 — [`docs/athlete_benchmark.schema.json`](athlete_benchmark.schema.json) (also `GET /v1/schema`)
**Public sample payload:** [`docs/sample_payload.json`](sample_payload.json) (live response of the public benchmark endpoint)
**Field guide:** [`docs/BENCHMARK_EXPORT.md`](BENCHMARK_EXPORT.md)

## Authentication
| Tier | Paths | Auth | Who may call it |
|---|---|---|---|
| Public | `/v1/health`, `/v1/schema`, `/v1/public/*` | none | anyone, including browser code (LingCode frontend) |
| Private | `/v1/private/*` | `Authorization: Bearer <BRUIN_API_TOKEN>` | **server-side only** (Gemini/BAND backend, LingCode backend) |

- `BRUIN_API_TOKEN` is held in the Modal secret `backfield-bruin-api` and in the owner's git-ignored `.env`.
  Share it with backend services through their own secret stores. **Never ship it in a browser bundle, a URL,
  a log line or a repo.**
- Wrong/missing token → `401` with `WWW-Authenticate: Bearer`.
- CORS: `GET` from any origin.

## Endpoints
### Public (no auth) — combine benchmarks + redacted PFF section
| Path | Returns |
|---|---|
| `GET /v1/health` | `{ok, schemaVersion, pipelineValidated, lastRunFinishedAt}` |
| `GET /v1/schema` | JSON Schema 1.1.0 |
| `GET /v1/public/athletes` | athlete ids + benchmark URLs |
| **`GET /v1/public/athletes/{athleteId}/benchmark`** | evaluation payload; NFL Combine measurements/percentiles in full; `pffContext.redacted = true`, every PFF `distribution = null`, `playerSeasons = []`, `statusDetail` explains the redaction |
| `GET /v1/public/benchmarks/{position}` | NFL Combine distributions for a position (nflverse public data) |
| `GET /v1/public/pipeline/status` | Bruin run status, quality checks, providers, `dataQualityExceptions` |
| `GET /v1/public/showcase` | public-safe Bruin sponsor showcase: status, stages, row counts, checks, lineage edges, QB distribution, example athlete, freshness, methodology |
| `GET /v1/public/players/featured` | real combine athletes linked to PFF by provider id (ids + coverage) |

**Athlete ids:** `bf-demo-qb-001` (synthetic demo QB) or `pfr:<pfr_id>` for any of the 1,288 real combine athletes linked to PFF
(e.g. `pfr:CookBr03`, Brady Cook). Real-player sample: [`docs/evidence/real_player_demo_public.json`](evidence/real_player_demo_public.json).

### Private (Bearer token) — full licensed PFF context
| Path | Returns |
|---|---|
| **`GET /v1/private/athletes/{athleteId}/benchmark`** | same schema 1.1.0 payload with `pffContext.redacted = false` and PFF distributions / player seasons |
| `GET /v1/private/pff/players?name=&league=&season=&limit=` | PFF player lookup: stats, snaps, PFF grades, within-position grade percentiles, identity links (gsis/pfr/combine) |
| `GET /v1/private/pff/players/{pffPlayerId}` | all PFF seasons for one player |
| `GET /v1/private/pff/distributions/{position}?league=&season=` | PFF grade distributions within a position |

```bash
B=https://omar-ubilla--backfield-bruin-api.us-east.modal.run
curl $B/v1/public/athletes/bf-demo-qb-001/benchmark                                   # public
curl -H "Authorization: Bearer $BRUIN_API_TOKEN" $B/v1/private/athletes/bf-demo-qb-001/benchmark   # server-side
```

### Which to use
- **LingCode frontend (browser):** public endpoints only.
- **Gemini/BAND agents (server):** private benchmark endpoint for agent evidence; render to end users only what the
  PFF licence permits. Cite `sourceReferences`, `benchmark.source_ref` and `pffContext.sourceRefs`.
- PFF grades live only in `pffContext` / `/v1/private/pff/*`, labelled `gradeSource: "PFF"`; they are not Backfield
  evaluations and must not be averaged with combine percentiles.

## Data-quality exception (open, non-blocking)
| Check | `bronze.nfl_player_stats: player_id.not_null` |
|---|---|
| Finding | 130 rows in nflverse weekly player stats (2019–2024) have no `player_id` (GSIS id) |
| Severity | non-blocking (`blocking: false` in the asset); pipeline `validated = true` |
| Handling | rows kept in bronze for lineage, excluded from `silver.nfl_qb_season_stats` |
| Impact | none on NFL Combine benchmarks, athlete percentiles or PFF data; NFL season stat totals may omit those 130 unattributed rows |
| Where reported | every payload: `pipeline.dataQualityExceptions[]`; `GET /v1/public/pipeline/status` |
| Status | open — upstream nflverse issue; not imputed or name-matched |

## Security posture (verified 2026-11-23)
- HTTPS with a Let's Encrypt certificate for `*.us-east.modal.run`; reachable from outside the local network (fetched externally).
- Public responses: no PFF values (0 non-null distributions, no player seasons, no PFF stat fields), no credentials.
- The PFF API key is **not** deployed (the server reads a prebuilt gold-table snapshot); the Modal image holds no `.env`
  and no raw bronze PFF rows.
- Repository (all history), local logs, Modal logs and the local web bundle were scanned: no PFF key or API token found;
  no DuckDB file or internal export is tracked.

## Refreshing the deployment
```bash
scripts/run_pipeline.sh                                              # Bruin run (+ PFF via .env)
uv run --python 3.12 --with duckdb python scripts/build_serving_db.py  # gold-only serving snapshot
modal deploy deploy/modal_app.py                                     # same URL
```
