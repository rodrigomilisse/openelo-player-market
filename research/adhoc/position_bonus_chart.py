import sys, pickle; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ctx = pickle.loads((store.RAW_DIR / "cache" / "context_process_noise3.pkl").read_bytes())
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
TOP5 = {"GB1", "ES1", "L1", "IT1", "FR1"}
league = store.teams().set_index("team_id").domestic_competition_id
pos = store.players().set_index("player_id").position
V = {"B": "none", "B + goals": "goals", "B + G+A": "ga", "B + G+A by position": "ga_position"}
r = ctx.club_rows
cand = r[(r.day >= snap - 120) & (r.day < snap) & r.team_id.map(lambda t: league.get(t) in TOP5)].player_id.unique()
rows = []
for pid in cand:
    L = ctx.listings(int(pid), True)
    L = L[L.day < snap].tail(50)
    if len(L) < 15 or league.get(int(L.team_id.iloc[-1])) not in TOP5:
        continue
    m = (np.minimum(L.minutes, L.length) / L.length).to_numpy()
    if m.mean() < 0.6:          # regulars: at least 60% of the minutes when in the squad
        continue
    team = int(L.team_id.iloc[-1]); keeper = pos.get(pid) == "Goalkeeper"
    rec = {"position": pos.get(pid)}
    p = v2.Player(v2.Variant(share_rule="starter", gk_reference=True))
    shares = [p.share_of(ms, None if s not in (0, 1) else bool(s), mi > 0) for ms, s, mi in zip(m, L.starter, L.minutes)]
    ref = 1.0 if keeper else ctx.squad_mean_at(team, snap, 16, "starter", 0.25)
    bonus = 400 * (np.mean(shares) - ref)
    for name, output in V.items():
        q = v2.Player(v2.Variant(output=output)); q.keeper = keeper; q.player_id = int(pid)
        q.output_window.extend(zip(L.minutes, L.goals, L.assists))
        rec[name] = bonus + q.output_points(ctx)
    rows.append(rec)
d = pd.DataFrame(rows)
order = ["Goalkeeper", "Defender", "Midfield", "Attack"]
t = d.groupby("position")[list(V)].mean().reindex(order).round(0)
t.insert(0, "regulars", d.position.value_counts().reindex(order))
print(t.to_string())
labels = ["Keepers", "Defenders", "Midfielders", "Attackers"]
cols = ["#eda100", "#2a78d6", "#008300", "#e34948"]
rules = ["B\nno goal term", "B + goals", "B + goals and assists", "B + goals and assists\nscaled by position"]
fig, ax = plt.subplots(figsize=(8, 4.8), dpi=200, facecolor="#fcfcfb"); ax.set_facecolor("#fcfcfb")
x = np.arange(len(V)); w = 0.19
for i, (position, label, c) in enumerate(zip(order, labels, cols)):
    vals = t.loc[position, list(V)].values
    bars = ax.bar(x + (i - 1.5) * w, vals, w * 0.9, color=c, label=label, edgecolor="#fcfcfb", linewidth=1)
ax.axhline(0, color="#6b6a64", linewidth=1)
ax.set_xticks(x, rules, color="#2b2a27", fontsize=8)
ax.set_ylabel("Mean minutes bonus + goal term (Elo points)", color="#55544e")
ax.set_title("Minutes bonus + goal term by position, top-5-league regulars, 2026-07-07", loc="left", color="#2b2a27", fontsize=11)
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.spines["left"].set_color("#c9c8c1"); ax.spines["bottom"].set_visible(False)
ax.grid(axis="y", color="#e6e5df", linewidth=0.8); ax.set_axisbelow(True)
ax.tick_params(colors="#55544e")
ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=4)
fig.tight_layout(); fig.savefig(sys.argv[1])
