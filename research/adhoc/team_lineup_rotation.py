import sys; sys.path.insert(0, ".")
from collections import deque, Counter
import numpy as np, pandas as pd, teamelo as te, candidate as c, store
games = store.query("select game_id, date from game where national = 0").set_index("game_id").date
lin = store.query("select game_id, team_id, player_id from lineup where starter = 1")
lin = lin[lin.game_id.isin(games.index)]
lin["date"] = lin.game_id.map(games)
reg = {}
for team, g in lin.sort_values(["date", "game_id"]).groupby("team_id"):
    recent, counts = deque(), Counter()
    for game, starters in g.groupby("game_id", sort=False).player_id:
        starters = set(starters)
        if len(recent) >= 10:
            usual = {p for p, _ in counts.most_common(11)}
            reg[(int(game), int(team))] = len(starters & usual) / min(11, len(starters))
        recent.append(starters); counts.update(starters)
        if len(recent) > 30:
            counts.subtract(recent.popleft())
te.LINEUP_REGULARITY.update(reg)
r = np.array(list(reg.values()))
print(f"line-ups scored: {len(reg)}; regularity mean {r.mean():.2f}, 10th pct {np.percentile(r, 10):.2f}")
matches = te.load_matches(); K = c.team_constants().with_(process_noise=3)
base = te.score(te.scored_frame(te.run(matches, K)[0]))
top5 = {g for g, in store.query("select game_id from game where competition_id in ('GB1','ES1','L1','IT1','FR1')").values}
print("regularity, top-5-league matches:", round(np.mean([v for (g, _), v in reg.items() if g in top5]), 2))
for shift in (50, 100, 200):
    s = te.score(te.scored_frame(te.run(matches, K.with_(lineup_shift=shift))[0]))
    d, lo, hi = te.paired_difference(s.test_losses, base.test_losses)
    print(f"lineup shift {shift}: test log loss Δ {d:+.5f} [{lo:+.5f}, {hi:+.5f}]", flush=True)
