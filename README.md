# Backfield AI Scouting Combine — Bruin data pipeline

Reproducible Bronze → Silver → Gold football analytics pipeline built with [Bruin](https://github.com/bruin-data/bruin) + DuckDB,
publishing validated athlete benchmark results for the Backfield coaching agents.

**Integration contract:** [docs/BENCHMARK_EXPORT.md](docs/BENCHMARK_EXPORT.md) · schema [docs/athlete_benchmark.schema.json](docs/athlete_benchmark.schema.json) · sample [docs/sample_payload.json](docs/sample_payload.json)

## Quick start
```bash
curl -LsSf https://getbruin.com/install/cli | sh       # Bruin CLI
scripts/run_pipeline.sh                                 # runs the pipeline, records execution status
scripts/run_bruin_api.sh                                # http://127.0.0.1:8787/v1/athletes/bf-demo-qb-001/benchmark
uv run --python 3.12 --with duckdb --with pytest --with jsonschema python -m pytest tests
```
Needs `uv` (Python 3.12 is fetched automatically). Optional: `CFBD_API_KEY` enables CollegeFootballData.

## Pipeline (`pipeline/`, 15 assets, ~49 quality checks)
| Layer | Asset | What |
|---|---|---|
| Bronze | `bronze.nfl_combine` | nflverse combine results 2000–2026 (nflreadpy) |
| | `bronze.nfl_players` | nflverse identity table with cross-provider ids (gsis, pfr, pff, espn) |
| | `bronze.nfl_player_stats` | weekly passing/rushing stats 2019–2024 |
| | `bronze.cfbd_player_season_passing` | CollegeFootballData rosters, passing stats, recruiting (needs `CFBD_API_KEY`; otherwise a status row) |
| | `bronze.backfield_athlete_records` | Backfield athlete evidence — **synthetic demo records** in this build |
| | `bronze.provider_status` | availability of nflverse, CFBD, PFF, Backfield, MaxPreps, Hudl (no credentials stored) |
| Silver | `silver.athletes` | Athlete entity keyed on provider ids; provisional keys otherwise; never merged by name |
| | `silver.physical_measurements` | long-form measurements with unit, definition, lineage, capture method, licence, plausibility flag |
| | `silver.nfl_qb_season_stats` | QB season rollups (null-id rows excluded) |
| Gold | `gold.combine_benchmarks` | position × metric distributions (n, missing, p10–p90, seasons) |
| | `gold.athlete_evidence` | athlete metrics placed in cohorts with comparability caveats |
| | `gold.athlete_benchmark_results` | **integration contract table** behind the JSON export |
| | `gold.qb_physical_comparables` | descriptive nearest combine QBs, NFL stats joined by provider id |
| | `gold.ncaa_qb_context` | CFBD context (empty with status when unavailable) |
| | `gold.pipeline_quality` | row counts, missing ids, implausible values, freshness |

Quality checks cover missing identifiers, duplicates, unit vocabularies, implausible values, ordered percentiles,
cohort existence, source lineage and the percentile-only-when-calculable rule.

## Data sources & licensing
- **nflverse** (combine, players, stats) — public open data, attribution required.
- **CollegeFootballData** — provider implemented; requires a free API key; small subset; respects rate limits.
- **PFF** — provider marked unavailable: no licensed key. PFF grades are never invented or scraped.
- **MaxPreps / Hudl** — interface only; no scraping. Hudl URLs are attribution references.
- **Backfield athlete data** — synthetic demo athlete (`isSynthetic: true`), never used as a reference cohort.
- No 10-yard split exists in the combine source; none is fabricated.
