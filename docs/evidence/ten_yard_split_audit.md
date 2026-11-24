# 10-yard split reference audit (2026-11-23)

**Conclusion: no legitimate 10-yard split reference data exists in any dataset this pipeline ingests.**
Live 10-yard dash results therefore receive an explicit `unavailable` benchmark — no percentile, no derived split,
no 40-yard substitution, no fabricated college distribution.

| Dataset (as ingested) | 10-yard split field? | Evidence |
|---|---|---|
| nflverse combine (`bronze.nfl_combine`, 8,968 rows, 2000–2026) | **No** | Columns: season, draft_*, pfr_id, cfb_id, player_name, pos, school, ht, wt, `forty`, bench, vertical, broad_jump, cone, shuttle. The source publishes no split times. |
| nflverse players / weekly stats | **No** | Identity and game statistics only. |
| PFF season reports (passing/rushing/receiving/offense, NFL+NCAA 2024–25) | **No** | Column scan of all 733 pipeline columns for split/ten/10yd/sprint/speed/dash/accel: only `forty` (combine), `avg_time_to_throw`, `big_time_throws`. |
| PFF Developer API spec (71 operations) | **No** | `forty_*` fields are 40–49-yard **field goals**; "split" refers to production splits (play concept, coverage scheme, pocket). `players.speed` is undocumented and returned `null` for every player sampled (NCAA and NFL). |
| CollegeFootballData | not audited (provider key not configured) | No CFBD data is ingested; no claim is made. |

## What *is* available for sprint comparison
| Drill | Reference | Timing method | QB cohort | Seasons | College vs NFL |
|---|---|---|---|---|---|
| 40-yard dash | `gold.combine_benchmarks` forty_sec | electronic (NFL Scouting Combine) | n = 413 (63 invitees missing) | 2000–2026 | NFL Combine invitees only (draft-eligible college players); no separate NCAA or high-school cohort exists |
| 10-yard split | none | — | 0 | — | — |

## Rules applied to live athletes
- 10-yard dash → `status: unavailable`, `reason: no 10-yard split reference cohort exists in the ingested sources`.
- 40-yard dash timed with ARKit, video or hand timing → `status: provisional`: a **descriptive band** against the electronic
  NFL Combine distribution is returned, but **no percentile**, because no validated conversion between timing methods exists.
- 40-yard dash timed electronically with verified quality → `status: verified` with a percentile vs NFL Combine invitees at the
  position (labelled as a professional reference population, not a high-school percentile).
