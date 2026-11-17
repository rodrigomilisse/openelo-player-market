import sys; sys.path.insert(0, ".")
import numpy as np, teamelo as te, candidate as c
matches = te.load_matches(); base = None
for q in (6, 3, 1.5, 0.75):
    k = c.team_constants().with_(process_noise=q)
    preds, _ = te.run(matches, k); s = te.score(te.scored_frame(preds))
    swing = np.mean([abs(p.home_swing) for p in preds if p.match.season >= 2019])
    if base is None: base = s
    d, lo, hi = te.paired_difference(s.test_losses, base.test_losses)
    print(f"process noise {q:<5} mean |swing| {swing:5.1f}  test log loss {s.test_log_loss:.5f}  vs fitted {d:+.5f} [{lo:+.5f}, {hi:+.5f}]", flush=True)
