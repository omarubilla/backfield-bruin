# PFF ↔ nflverse ↔ combine identity crosswalk (`silver.athlete_identity_xref`)

Join key: PFF `player_id` = nflverse `players.pff_id` (a provider id nflverse publishes) → `gsis_id`, `pfr_id` → combine athlete `pfr:<pfr_id>`. No name matching is used for links; ambiguous ids (one pff_id → several gsis ids) are left unlinked.

| Match type | PFF players | with gsis_id | with pfr_id | linked to combine | with NCAA PFF seasons |
|---|---|---|---|---|---|
| provider_id_nflverse_pff_id | 2245 | 2245 | 2221 | 1288 | 599 |
| unmatched | 19052 | 0 | 0 | 0 | 18964 |

Linked players with BOTH NCAA and NFL PFF seasons in 2024-2025: **269** (college → pro continuity through one PFF id).

Linked-to-combine players by PFF position (top 10):

| PFF position | Players |
|---|---|
| WR | 287 |
| HB | 177 |
| T | 167 |
| G | 155 |
| TE | 147 |
| QB | 121 |
| C | 64 |
| LB | 48 |
| S | 31 |
| ED | 24 |
