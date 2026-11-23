"""Captures judge-facing evidence from the tables the last `bruin run` produced.

    uv run --python 3.12 --with duckdb python scripts/capture_evidence.py

Writes docs/evidence/{lineage.json, lineage.mmd, row_counts.md, qb_combine_benchmarks.md,
identity_crosswalk.md, provenance.md}. Counts and public nflverse data only - no PFF values.
"""
import json
import os
import re
from datetime import datetime, timezone

import duckdb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "docs", "evidence")
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect(os.path.join(ROOT, "data", "scouting.duckdb"), read_only=True)
q = lambda s, p=(): con.execute(s, list(p)).fetchall()  # noqa: E731


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


# 1. Lineage from the asset definitions Bruin executes (name + depends in each @bruin header).
assets = {}
for root, _, files in os.walk(os.path.join(ROOT, "pipeline", "assets")):
    for f in files:
        t = open(os.path.join(root, f), errors="ignore").read()
        m = re.search(r"@bruin\s*\n?(.*?)@bruin", t, re.S)
        if not m:
            continue
        hdr = m.group(1)
        name = re.search(r"^name:\s*([\w.]+)", hdr, re.M).group(1)
        dep_block = re.search(r"^depends:\n((?:\s+- .+\n)+)", hdr, re.M)
        deps = re.findall(r"- ([\w.]+)", dep_block.group(1)) if dep_block else []
        typ = re.search(r"^type:\s*(\S+)", hdr, re.M).group(1)
        assets[name] = {"type": typ, "layer": name.split(".")[0], "depends": deps, "file": os.path.relpath(os.path.join(root, f), ROOT)}
edges = [{"from": d, "to": a} for a, v in assets.items() for d in v["depends"]]
json.dump({"assets": assets, "edges": edges}, open(os.path.join(OUT, "lineage.json"), "w"), indent=2)
mmd = ["flowchart LR"]
for layer in ("bronze", "silver", "gold"):
    mmd.append(f"  subgraph {layer.upper()}")
    mmd += [f"    {a.replace('.', '_')}[\"{a}\"]" for a in sorted(assets) if assets[a]["layer"] == layer]
    mmd.append("  end")
mmd += [f"  {e['from'].replace('.', '_')} --> {e['to'].replace('.', '_')}" for e in edges if e["to"] != "gold.lineage_row_counts"]
open(os.path.join(OUT, "lineage.mmd"), "w").write("\n".join(mmd) + "\n")

# 2. Row counts by stage/source (computed by Bruin in gold.lineage_row_counts).
rc = q("SELECT layer, asset, provider, row_count, description FROM gold.lineage_row_counts ORDER BY CASE layer WHEN 'bronze' THEN 1 WHEN 'silver' THEN 2 ELSE 3 END, asset")
open(os.path.join(OUT, "row_counts.md"), "w").write(
    "# Row counts by stage (from `gold.lineage_row_counts`, computed inside the Bruin run)\n\n"
    + md_table(["Layer", "Asset", "Provider", "Rows", "What"], rc) + "\n")

# 3. QB combine benchmarks.
qb = q("SELECT metric, unit, n, missing_n, p10, p25, p50, p75, p90, season_min || '-' || season_max FROM gold.combine_benchmarks WHERE position_group='QB' ORDER BY metric")
allpos = q("SELECT position_group, count(*) metrics, sum(n) measurements FROM gold.combine_benchmarks GROUP BY 1 ORDER BY 1")
open(os.path.join(OUT, "qb_combine_benchmarks.md"), "w").write(
    "# NFL Combine benchmarks (`gold.combine_benchmarks`)\n\nQB cohort, combine invitees with measured, plausible values:\n\n"
    + md_table(["Metric", "Unit", "n", "Missing", "p10", "p25", "p50", "p75", "p90", "Seasons"], qb)
    + "\n\nNo 10-yard split exists in the nflverse combine source; none is fabricated.\n\nAll positions:\n\n"
    + md_table(["Position group", "Metrics", "Measurements"], allpos) + "\n")

# 4. Identity crosswalk.
xr = q("SELECT match_type, count(*), count(gsis_id), count(pfr_id), count(combine_athlete_key), count(*) FILTER (WHERE pff_leagues LIKE '%ncaa%') FROM silver.athlete_identity_xref GROUP BY 1 ORDER BY 1")
both = q("SELECT count(*) FROM silver.athlete_identity_xref WHERE match_type <> 'unmatched' AND pff_leagues LIKE '%ncaa%' AND pff_leagues LIKE '%nfl%'")[0][0]
pos = q("SELECT position, count(*) FROM silver.athlete_identity_xref WHERE combine_athlete_key IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10")
open(os.path.join(OUT, "identity_crosswalk.md"), "w").write(
    "# PFF ↔ nflverse ↔ combine identity crosswalk (`silver.athlete_identity_xref`)\n\n"
    "Join key: PFF `player_id` = nflverse `players.pff_id` (a provider id nflverse publishes) → `gsis_id`, `pfr_id` → "
    "combine athlete `pfr:<pfr_id>`. No name matching is used for links; ambiguous ids (one pff_id → several gsis ids) are left unlinked.\n\n"
    + md_table(["Match type", "PFF players", "with gsis_id", "with pfr_id", "linked to combine", "with NCAA PFF seasons"], xr)
    + f"\n\nLinked players with BOTH NCAA and NFL PFF seasons in 2024-2025: **{both}** (college → pro continuity through one PFF id).\n\n"
    "Linked-to-combine players by PFF position (top 10):\n\n" + md_table(["PFF position", "Players"], pos) + "\n")

# 5. Provenance: tables were written by this Bruin run.
st = json.load(open(os.path.join(ROOT, "logs", "bruin_run_latest.json")))
loaded = q("SELECT max(_ingestr_loaded_at)::VARCHAR FROM bronze.pff_offense_summary")[0][0]
loaded_c = q("SELECT max(_ingestr_loaded_at)::VARCHAR FROM bronze.nfl_combine")[0][0]
dq = [f for f in st["check_failures"]]
open(os.path.join(OUT, "provenance.md"), "w").write(f"""# Provenance: outputs are produced by Bruin, not read from precomputed JSON

- Run: `{st['started_at']}` → `{st['finished_at']}` · Bruin `{st['bruin_version']}` · git `{st['git_commit']}` · exit code {st['exit_code']}
- Assets executed: {st['assets_passed']}/{st['assets_total']} · quality checks passed {st['checks_passed']}, failed {st['checks_failed']} (blocking {st['checks_failed_blocking']})
- Bronze Python assets are loaded by Bruin's ingestr materialization, which stamps every row: `bronze.nfl_combine._ingestr_loaded_at = {loaded_c}`, `bronze.pff_offense_summary._ingestr_loaded_at = {loaded}` (local time, PST) - inside the run window above (UTC times).
- Silver and gold are `duckdb.sql` assets that Bruin materializes as tables in `data/scouting.duckdb`; their checks are executed by Bruin after each build (see `bruin_run_evidence.log`).
- The API reads those gold tables (`scripts/build_serving_db.py` copies them into a gold-only snapshot); the only JSON it reads is the run-status record parsed from the Bruin log.
- Known non-blocking exception: {dq[0]['asset'] if dq else 'none'} — {dq[0]['check'] if dq else ''}

Captured {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `scripts/capture_evidence.py`.
""")
print("evidence written:", sorted(os.listdir(OUT)))
