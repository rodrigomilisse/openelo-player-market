# Ad hoc analyses

The one-off scripts behind the tables and charts in the 2026-11 sessions, kept as
written. Run from `research/` (`.venv/bin/python adhoc/<script>.py`). Most load
the cached context from `data/raw/cache/` (built by `fit_light.py`; set
`FIT_TEAM='{"process_noise": 3}'` for the current team settings). The variant
settings inside each script are those of the session that used it, not
necessarily the current candidate (see `NEXT.md`).

| Script | Produced |
|---|---|
| `squad_parts.py TEAM_ID YYYY-MM-DD OUT.csv` | One club's players: rating, minutes bonus, national points, absence, shares |
| `mixed_list.py` | The mixed list of seven clubs (top 5 and ranks 15–20) across variants |
| `position_bonus_chart.py OUT.png` | Mean bonus of top-5-league regulars by position and rule |
| `club_ratings.py` | Club Elos: Champions League clubs, mid and bottom club of ten leagues |
| `player_series.py` | Olise and Bruno: rating every 3 months against Transfermarkt values, raw and age-adjusted |
| `national_points.py VARIANTS_JSON` | National-team points of named players under several national rules |
| `big_game_top10.py` | Top ten of Bayern, City and Arsenal with and without big-game trust |
| `squad_values.py` | Bayern: rating against Transfermarkt value and age-adjusted value |
| `team_league_share.py` | Team log loss for the league share of European results, zero-sum and not, and pool drift |
| `team_lineup_rotation.py` | Line-up regularity and team log loss with rotation in the expected result |
| `team_process_noise.py` | Team log loss and mean swing for process noise 6, 3, 1.5, 0.75 |
