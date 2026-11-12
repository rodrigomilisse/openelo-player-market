# research

Offline Phase 1 tool: researches the OpenElo formula, validates it against public
data and Transfermarkt values, and holds the exact integer reference the Java
port must match (Spec §2, §4). Never deployed and never imported by any service.
Findings: [FINDINGS.md](FINDINGS.md).

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Data

Raw downloads and everything derived from them live under `data/raw/`, which is
gitignored: the repository is public and the data is scraped. `data/openelo_market.sqlite3`
and `outputs/` are tracked from before and are left as they are.

```
.venv/bin/python -I ingest.py --fetch     # download once (~300 MB), then build data/raw/openelo_research.sqlite3
```

`ingest.py` imports nothing from this directory, so it runs in isolated mode
(`-I`): raw files are parsed as data, never executed.

## Regenerating every number in FINDINGS.md

Run in this order; each step caches what the next reads under `data/raw/results/`.

```
.venv/bin/python evaluate.py team            # §4.1–4.5, C2, C5      ~10 min
.venv/bin/python evaluate.py hindsight       # §4.4, C4               ~1–2 h, 5 processes
.venv/bin/python evaluate.py replay          # §4.4 diagnostics       ~1 h
.venv/bin/python evaluate.py benchmarks      # §4.6, C3
.venv/bin/python evaluate.py players         # §5.2, C6, bonus        ~30 min, 3 processes
.venv/bin/python evaluate.py rate            # §5.3 as-of player series
.venv/bin/python evaluate.py transfermarkt   # §5.4, C7
.venv/bin/python evaluate.py convergence     # §5.5, C8
.venv/bin/python evaluate.py collinearity    # §5.8, C10
.venv/bin/python evaluate.py confounds       # §5.9
.venv/bin/python evaluate.py positions       # §5.10
.venv/bin/python evaluate.py national        # §5.11
.venv/bin/python evaluate.py exact           # §6, C1, C9, C11, C12   ~2 h
.venv/bin/python evaluate.py scale-zero      # §6.6
```

## Transfermarkt comparison (the original tool)

`openelo(tm_player_id, as_of)` returns the integer reference's published rating
in milli-Elo, so these need `evaluate.py exact` first. Charts go to
`data/raw/charts/`.

```
.venv/bin/python openelo_market.py compare "Lionel Messi"
.venv/bin/python openelo_market.py average --set a          # the original 100 (set A)
.venv/bin/python openelo_market.py average --set b          # the diagnostic set (set B)
.venv/bin/python openelo_market.py correlation --set b --max-lag 24
```

## Files

| File | Role |
|---|---|
| `ingest.py` | Raw data to the research store |
| `store.py` | Read access to the research store |
| `teamelo.py` | Team Elo, float: fixed-K baseline and Elo with uncertainty |
| `hindsight.py` | Hindsight correction of opponent strength, float |
| `playerelo.py` | Player ratings from team swings, float |
| `national.py` | National-team line-ups 2014–26 and all internationals into `nt_*` tables (`--fetch` to download) |
| `exact.py` | Exact integer reference of the final candidate |
| `team_checks.py`, `player_checks.py`, `exact_checks.py` | The evaluations behind each criterion |
| `evaluate.py` | Command line for all of the above |
| `players.py` | Set A (the original 100) and set B (diagnostic cases) |
| `openelo.py`, `analysis.py`, `openelo_market.py`, `db.py`, `tm_client.py` | The original Transfermarkt comparison tool |

`OPENELO_TM_AGE_ADJUST=linear:2` (or `linear:R`, `exp:R`) runs the Transfermarkt comparisons against age-adjusted values (RESULTS-communication.md §8).
