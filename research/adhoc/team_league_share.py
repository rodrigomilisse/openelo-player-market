import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd, teamelo as te, candidate as c
matches = te.load_matches(); K = c.team_constants().with_(process_noise=3)
euro = {m.game_id for m in matches if m.competition_id in te.EUROPEAN}
def go(**kw):
    preds, _ = te.run(matches, K.with_(**kw)); s = te.score(te.scored_frame(preds))
    pool = pd.DataFrame([(p.match.season, (p.home_rating + p.away_rating) / 2) for p in preds], columns=["season", "r"]).groupby("season").r.mean()
    return s, pool
base, pool0 = go()
print(f"{'variant':<34} {'all Δ (95%)':<30} {'European Δ':<12} pool mean drift vs base: 2016 / 2020 / 2025")
for name, kw in [("share 0.3, not zero-sum", dict(league_share=0.3, league_zero_sum=False)),
                 ("share 0.3, zero-sum", dict(league_share=0.3)),
                 ("share 0.5, zero-sum", dict(league_share=0.5)),
                 ("share 0.3 zero-sum, noise 6", dict(league_share=0.3, process_noise=6)),
                 ("share 0.3 zero-sum, noise 1.5", dict(league_share=0.3, process_noise=1.5))]:
    s, pool = go(**kw)
    d, lo, hi = te.paired_difference(s.test_losses, base.test_losses)
    e = te.paired_difference(s.test_losses[s.test_losses.index.isin(euro)], base.test_losses[base.test_losses.index.isin(euro)])[0]
    drift = (pool - pool0)
    print(f"{name:<34} {d:+.5f} [{lo:+.5f}, {hi:+.5f}]   {e:+.5f}     {drift.get(2016, 0):+.1f} / {drift.get(2020, 0):+.1f} / {drift.get(2025, 0):+.1f}", flush=True)
print(f"base (noise 3, no share) test log loss {base.test_log_loss:.5f}")
