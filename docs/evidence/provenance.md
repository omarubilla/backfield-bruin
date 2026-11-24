# Provenance: outputs are produced by Bruin, not read from precomputed JSON

- Run: `2026-11-24T00:14:41Z` → `2026-11-24T00:15:00Z` · Bruin `Current: v0.11.832 (3590ddcdf90425e609ceb8e0e2c352fb4de995b6)` · git `8349e7d` · exit code 1
- Assets executed: 32/32 · quality checks passed 102, failed 1 (blocking 0)
- Bronze Python assets are loaded by Bruin's ingestr materialization, which stamps every row: `bronze.nfl_combine._ingestr_loaded_at = 2026-11-23 16:14:45.002777-08`, `bronze.pff_offense_summary._ingestr_loaded_at = 2026-11-23 16:15:00.034415-08` (local time, PST) - inside the run window above (UTC times).
- Silver and gold are `duckdb.sql` assets that Bruin materializes as tables in `data/scouting.duckdb`; their checks are executed by Bruin after each build (see `bruin_run_evidence.log`).
- The API reads those gold tables (`scripts/build_serving_db.py` copies them into a gold-only snapshot); the only JSON it reads is the run-status record parsed from the Bruin log.
- Known non-blocking exception: bronze.nfl_player_stats — player_id.not_null - column 'player_id' has 130 null values

Captured 2026-11-24T00:15:37+00:00 by `scripts/capture_evidence.py`.
