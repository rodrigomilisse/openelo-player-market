# research

Offline Phase 1 tool: compares OpenElo against Transfermarkt market values to validate the rating model (Spec §2, §4). Never deployed and never imported by any service.

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python openelo_market.py --help
```
