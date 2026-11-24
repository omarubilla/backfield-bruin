"""Builds data/serving.duckdb: only the gold/status tables the API reads (no bronze PFF rows).

    uv run --python 3.12 --with duckdb python scripts/build_serving_db.py
"""
import os

import duckdb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "data", "scouting.duckdb")
DST = os.path.join(ROOT, "data", "serving.duckdb")
TABLES = [
    "gold.athlete_benchmark_results", "gold.combine_benchmarks", "bronze.provider_status",
    "gold.pff_position_grade_distributions", "gold.pff_player_context",
    "gold.player_benchmark_results", "gold.lineage_row_counts", "gold.pipeline_quality",
    "gold.live_reference_catalog", "gold.live_reference_values",
]

if os.path.exists(DST):
    os.remove(DST)
con = duckdb.connect(DST)
con.execute(f"ATTACH '{SRC}' AS src (READ_ONLY)")
for t in TABLES:
    schema, name = t.split(".")
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    con.execute(f"CREATE TABLE {t} AS SELECT * FROM src.{t}")
    print(t, con.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
con.execute("DETACH src")
con.close()
print("wrote", DST, os.path.getsize(DST) // 1024, "KB")
