# OpenElo research: warm up the model once, then update ratings periodically.
#
#   make warmup     first time: venv, download (~300 MB), build the store, fit team constants (~3 min),
#                   build the model context, publish (about 30-60 min in all)
#   make update     periodic:   re-download the Transfermarkt tables, rebuild the store, publish as of today
#   make publish    only recompute ratings from the store as it is
#   make history    once, optional: also publish every month start since 2013
#   make status     what is in the store and the newest published run
#
# Output: data/raw/published/latest.csv, ratings_<date>.csv and published.sqlite3 (see publish.py).
# Everything under data/raw/ is gitignored.

PY      := .venv/bin/python
RAW     := data/raw
STORE   := $(RAW)/openelo_research.sqlite3
PROCS   ?= 4

.PHONY: warmup update publish history status setup fetch store constants

warmup: setup fetch store constants publish

setup: .venv/bin/activate

.venv/bin/activate: requirements.txt
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt
	@touch $@

# Missing raw files only.
fetch: setup
	$(PY) -I ingest.py --fetch --no-build
	$(PY) national.py --fetch --no-build

# Build the store, then add the national-team tables to it. Keeps the old store if either step fails.
store: setup
	@test ! -f $(STORE) || cp $(STORE) $(STORE).bak
	$(PY) -I ingest.py && $(PY) national.py \
		&& rm -f $(STORE).bak \
		|| { test ! -f $(STORE).bak || mv $(STORE).bak $(STORE); echo "build failed: previous store restored"; exit 1; }

# Fit the team model's constants (about 3 minutes). They are fitted on the 2014/15-2018/19 seasons
# only, so they are fitted once and not on every update. Delete the file to refit.
CONSTANTS := $(RAW)/results/team_constants.json
constants: $(CONSTANTS)
$(CONSTANTS): | setup
	$(PY) evaluate.py team

update: setup
	$(PY) -I ingest.py --refresh --no-build
	$(PY) national.py --fetch --no-build
	$(MAKE) store
	$(MAKE) publish

publish: setup
	$(PY) publish.py --processes $(PROCS)

history: setup
	$(PY) publish.py --processes $(PROCS) --history

status:
	@$(PY) -c "import store; print(store.query('SELECT MAX(date) AS newest_club_match, COUNT(*) AS club_matches FROM game WHERE national = 0').to_string(index=False))"
	@$(PY) -c "import sqlite3,sys; p='$(RAW)/published/published.sqlite3'; c=sqlite3.connect(p); print('\n'.join(map(str, c.execute('SELECT as_of, ran_at, newest_match, players FROM run ORDER BY as_of DESC LIMIT 5'))))" 2>/dev/null || echo "nothing published yet"
