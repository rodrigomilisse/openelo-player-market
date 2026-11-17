import sys, pickle, json; sys.path.insert(0, ".")
import pandas as pd, player_v2 as v2, store
ctx = pickle.loads((store.RAW_DIR / "cache" / "context.pkl").read_bytes())
BASE = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs", bonus_scale=400.0)
VARS = json.loads(sys.argv[1])
pl = store.players().merge(store.query("select player_id, count(*) n from appearance group by player_id"), on="player_id")
names = ["Harry Kane", "Cole Palmer", "Phil Foden", "Bukayo Saka", "Bart Verbruggen", "Kai Havertz", "Michael Olise", "Dayot Upamecano", "Joshua Kimmich", "Gonçalo Inácio"]
ids = {n: int(pl[pl.name == n].sort_values("n").iloc[-1].player_id) for n in names}
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
got = {}
orig = v2.Player.published
def published(self, day, context):
    got["nt"] = self.national_points(day, context); return orig(self, day, context)
v2.Player.published = published
out = {}
for vname, over in VARS.items():
    var = v2.Variant(**{**BASE, **over}); col = {}
    for n, pid in ids.items():
        v2.series(pid, var, ctx, [snap]); col[n] = round(got.get("nt", 0))
    out[vname] = col
print(pd.DataFrame(out).to_string())
