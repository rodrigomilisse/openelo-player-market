import sys; sys.path.insert(0,'.')
exec(open("adhoc/availability_check.py").read().split("for label, (snap")[0]); src2=open("adhoc/nt_cutoff.py").read(); exec(src2[src2.index("def predicted"):src2.rindex("for label, (snap")])
for label,(snap,comps) in {"2024":("2024-06-01",["EURO","COPA"]),"2026":("2026-06-01",["FIWC"])}.items():
    c=spells(snapshot(snap,comps),snap)
    fr=(c.band<=10)&(c.rank2>=13)&c.recent; mid=(c.band>10)&(c.band<=40)&(c.rank2<=6)&c.recent
    print(label,"actual fringe %.2f mid %.2f"%(c.selected[fr].mean(),c.selected[mid].mean()))
    for cs in (1.0,0.75,0.5):
        for k in (160,250,400):
            s=cs*c.club+k*c.order2+200*c.avail2; p=predicted(c,s)
            print(f"  club x{cs} k={k}: fringe {p[fr].mean():.2f} mid {p[mid].mean():.2f} precision {(p&c.selected).sum()/p.sum():.3f}")
