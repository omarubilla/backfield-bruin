# Row counts by stage (from `gold.lineage_row_counts`, computed inside the Bruin run)

| Layer | Asset | Provider | Rows | What |
|---|---|---|---|---|
| bronze | bronze.backfield_athlete_records | backfield-demo | 7 | synthetic demo athlete evidence |
| bronze | bronze.cfbd_player_season_passing | collegefootballdata | 0 | NCAA passing/rosters/recruiting (key not configured) |
| bronze | bronze.nfl_combine | nflverse | 8968 | NFL Scouting Combine results |
| bronze | bronze.nfl_player_stats | nflverse | 110390 | weekly player stats 2019-2024 |
| bronze | bronze.nfl_players | nflverse | 24871 | player identity + cross-provider ids |
| bronze | bronze.pff_ncaa_rosters | pff | 615 | PFF NCAA rosters, 6 FBS teams 2025 |
| bronze | bronze.pff_offense_summary | pff | 29572 | PFF offense snaps/grades NFL+NCAA 2024-25 |
| bronze | bronze.pff_passing_summary | pff | 2651 | PFF passing season reports NFL+NCAA 2024-25 |
| bronze | bronze.pff_receiving_summary | pff | 11568 | PFF receiving season reports NFL+NCAA 2024-25 |
| bronze | bronze.pff_rushing_summary | pff | 8209 | PFF rushing season reports NFL+NCAA 2024-25 |
| bronze | bronze.provider_status | all | 6 | provider availability probe |
| silver | silver.athlete_identity_xref | pff x nflverse | 21297 | PFF players with identity resolution |
| silver | silver.athlete_identity_xref [linked to combine] | pff x nflverse x combine | 1288 | linked through to a combine athlete |
| silver | silver.athlete_identity_xref [linked] | pff x nflverse | 2245 | linked by provider id (nflverse pff_id) |
| silver | silver.athletes | nflverse | 8950 | Athlete entity keyed on provider ids |
| silver | silver.nfl_qb_season_stats | nflverse | 476 | QB season rollups (null-id rows excluded) |
| silver | silver.pff_grades | pff | 99003 | PFF grades long form |
| silver | silver.pff_player_seasons | pff | 29572 | PFF reports joined per player-league-season |
| silver | silver.physical_measurements | nflverse | 54968 | long-form measurements with units/lineage |
| gold | gold.athlete_benchmark_results | backfield-demo | 9 | contract table (demo athlete) |
| gold | gold.athlete_evidence | backfield-demo | 7 | demo athlete evidence |
| gold | gold.combine_benchmarks | nflverse | 88 | position x metric combine distributions |
| gold | gold.ncaa_qb_context | collegefootballdata | 0 | CFBD context (unavailable) |
| gold | gold.pff_player_context | pff | 29572 | PFF player lookup |
| gold | gold.pff_position_grade_distributions | pff | 58 | PFF grade distributions within position |
| gold | gold.player_benchmark_results | nflverse x pff | 10128 | contract table (real linked players) |
| gold | gold.qb_physical_comparables | nflverse | 10 | descriptive QB comparables |
