"""Club Elo sets how many goal points a club gives out: a club whose goal points exceed what its Elo predicts
pays the excess back from its squad in proportion to minutes (scorers keep their goals, so attackers gain on
defenders); a club below its prediction hands the shortfall to its squad by minutes (defenders of a defensive
team gain). Prediction: linear fit of club goal points on club level across these 10 clubs.
Uses the components saved by nt_players_zero_sum.py (current national term).
    python adhoc/goal_pot.py   # from research/, seconds
"""
import sys, html; sys.path.insert(0, ".")
import numpy as np, pandas as pd
d = pd.read_csv("adhoc/nt_players_zero_sum.csv")
club = d.groupby("club").agg(level=("base", "max"), goal_points=("goals", "sum"), minutes=("club_minutes", "sum"))
b = np.polyfit(club.level, club.goal_points, 1); club["expected"] = np.polyval(b, club.level); club["excess"] = club.goal_points - club.expected
# split by minutes not backed by goals: minutes x (1 - his goal points / the club's top goal points), times STRENGTH
STRENGTH = 2.0
pos = d.player_id.map(__import__("store").players().set_index("player_id").position)
regular = (d.club_minutes >= 900) & (pos != "Goalkeeper")
med = d[regular].groupby("club").goals.median()
nb = (d.club_minutes * ((d.club.map(med) - d.goals) / d.club.map(med)).clip(lower=0)).where(pos != "Goalkeeper", 0.0)
w = nb / nb.groupby(d.club).transform("sum")
d["transfer"] = -STRENGTH * w * d.club.map(club.excess)
d["new"] = d.current + d.transfer
print(club.round(0).sort_values("excess").to_string())
d["rk_cur"] = d.current.rank(ascending=False).astype(int); d["rk_new"] = d.new.rank(ascending=False).astype(int)
ids = d.index[(d.groupby("club").current.rank(ascending=False, method="first") <= 7) | (d.groupby("club").new.rank(ascending=False, method="first") <= 7)]
x = d.loc[ids].copy()
x["#"] = x.new.rank(ascending=False, method="min").astype(int); x["# current"] = x.current.rank(ascending=False, method="min").astype(int)
x["TM rank"] = x.TM.rank(ascending=False, method="min")
x = x.sort_values("new", ascending=False)
cols = ["#", "# current", "name", "club", "new", "current", "base", "minutes", "goals", "nt_clubs", "transfer", "TM", "TM rank"]
print(x[cols].round(0).to_string(index=False))
hdr = ["#", "# before", "Player", "Club", "Rating", "Before", "Club level", "Minutes", "Goals + assists", "National", "Goal pot transfer", "TM €m", "TM rank"]
rows = "".join("<tr>" + "".join(f"<td{' class=n' if i not in (2, 3) else ''}>{html.escape(str(v)) if i in (2, 3) else ('' if pd.isna(v) else f'{v:.0f}' if i != 11 else f'{v:g}')}</td>"
                                for i, v in enumerate(r)) + "</tr>" for r in x[cols].itertuples(index=False))
crow = "".join(f"<tr><td>{c}</td><td class=n>{r.level:.0f}</td><td class=n>{r.goal_points:.0f}</td><td class=n>{r.expected:.0f}</td><td class=n>{r.excess:+.0f}</td></tr>" for c, r in club.sort_values("excess").iterrows())
css = open("adhoc/decision_tables.py").read().split('css = """')[1].split('"""')[0]
page = (f"<title>Goal Pot By Club Elo</title><meta name=\"claude:viewport-fit-sides\" content=\"cover\">"
        f"<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Space+Grotesk:wght@500;600&display=swap\">"
        f"<style>{css}.wide{{overflow-x:auto}}.narrow{{max-width:620px}}</style><h1>Club Elo sets the goal points a club gives out</h1>"
        f"<p>Each club's total goal-and-assist points are compared with what its club level predicts (straight-line fit across these 10 clubs). "
        f"A club above its prediction pays twice the excess back from the players whose minutes are not backed by goals (minutes × how far his goal points sit below the squad median, outfield players only), so scorers gain on the rest; "
        f"a club below it hands twice the shortfall to those same players, so its defenders gain. Everything else as the current rating "
        f"(assists in, no absence, national term from club ratings). Snapshot 7 July 2026. Top 7 of each club under either version; ranks count only the players listed.</p>"
        f"<h2>Clubs</h2><div class=narrow><table><tr><th>Club</th><th>Club level</th><th>Goal points</th><th>Expected from Elo</th><th>Excess</th></tr>{crow}</table></div>"
        f"<h2>Players</h2><div class=wide><table><tr>{''.join(f'<th>{h}</th>' for h in hdr)}</tr>{rows}</table></div>")
open("adhoc/goal_pot.html", "w").write(page); print("written")
